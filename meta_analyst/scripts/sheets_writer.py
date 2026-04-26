"""Writer de filas a Google Sheets para el agente Velenza.

Auth via Service Account: env var GOOGLE_SA_JSON o archivo .gcp_sa.json local.
URL de la sheet via env SHEET_URL o archivo .sheet_url local.

Upsert por (date + entity_id). Si la combinacion ya existe en la tab,
actualiza la fila; si no, la appendea.
"""

import json
import os
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # para importar meta_api


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Clave de upsert por tab
TAB_KEYS = {
    "campaigns": ("date", "campaign_id"),
    "adsets": ("date", "adset_id"),
    "ads": ("date", "ad_id"),
}


# ---------- Auth + Sheet open ----------

def load_credentials() -> Credentials:
    raw = os.environ.get("GOOGLE_SA_JSON")
    if raw:
        info = json.loads(raw)
    else:
        sa_file = ROOT / ".gcp_sa.json"
        if not sa_file.exists():
            raise RuntimeError("No se encontro GOOGLE_SA_JSON (env) ni .gcp_sa.json (local).")
        info = json.loads(sa_file.read_text(encoding="utf-8"))
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def load_sheet_url() -> str:
    url = os.environ.get("SHEET_URL")
    if url:
        return url.strip()
    url_file = ROOT / ".sheet_url"
    if url_file.exists():
        return url_file.read_text(encoding="utf-8").strip()
    raise RuntimeError("No se encontro SHEET_URL (env) ni .sheet_url (local).")


def open_sheet(url: str | None = None) -> gspread.Spreadsheet:
    if url is None:
        url = load_sheet_url()
    creds = load_credentials()
    client = gspread.authorize(creds)
    return client.open_by_url(url)


# ---------- Upsert ----------

def _values_for_row(row: dict, headers: list[str]) -> list:
    """Arma lista de valores alineados a los headers, convirtiendo None a ''."""
    out = []
    for h in headers:
        v = row.get(h, "")
        out.append("" if v is None else v)
    return out


def upsert_rows(tab: gspread.Worksheet, rows: list[dict], key_cols: tuple[str, ...]) -> dict:
    if not rows:
        return {"appended": 0, "updated": 0}

    all_values = tab.get_all_values()
    if not all_values:
        raise RuntimeError(f"Tab '{tab.title}' sin headers. Agrega la fila 1 con nombres de columnas.")
    headers = all_values[0]

    # Indice (key_tuple) -> row_number (1-indexed, row 2 = primera data)
    existing: dict[tuple, int] = {}
    for idx, row_vals in enumerate(all_values[1:], start=2):
        row_dict = dict(zip(headers, row_vals))
        key = tuple(str(row_dict.get(k, "")) for k in key_cols)
        existing[key] = idx

    to_append: list[list] = []
    updated = 0
    for row in rows:
        key = tuple(str(row.get(k, "")) for k in key_cols)
        values = _values_for_row(row, headers)
        if key in existing:
            row_num = existing[key]
            tab.update(range_name=f"A{row_num}", values=[values])
            updated += 1
        else:
            to_append.append(values)

    appended = 0
    if to_append:
        tab.append_rows(to_append, value_input_option="USER_ENTERED")
        appended = len(to_append)

    return {"appended": appended, "updated": updated}


def push_snapshot(snapshot: dict) -> dict:
    sh = open_sheet()
    existing_tabs = {w.title for w in sh.worksheets()}

    results: dict[str, dict] = {}
    for tab_name, key_cols in TAB_KEYS.items():
        rows = snapshot.get(tab_name, [])
        if tab_name not in existing_tabs:
            results[tab_name] = {"error": "tab no existe"}
            continue
        tab = sh.worksheet(tab_name)
        results[tab_name] = upsert_rows(tab, rows, key_cols)
    return results


# ---------- CLI ----------

def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/sheets_writer.py <comando> [args]")
        print("Comandos:")
        print("  test-auth                       Verifica auth y muestra tabs de la sheet")
        print("  push-daily <YYYY-MM-DD>         Pulla snapshot via meta_api y pushea a las 3 tabs")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test-auth":
        sh = open_sheet()
        print(f"OK abriendo Sheet: '{sh.title}'")
        print(f"URL: {sh.url}")
        print(f"Tabs disponibles: {[w.title for w in sh.worksheets()]}")

    elif cmd == "push-daily":
        if len(sys.argv) < 3:
            print("Uso: push-daily <YYYY-MM-DD>")
            sys.exit(1)
        date = sys.argv[2]
        from meta_api import fetch_daily_snapshot
        print(f"Pulling snapshot {date}...")
        snap = fetch_daily_snapshot(date)
        print(f"  campaigns={len(snap['campaigns'])}  adsets={len(snap['adsets'])}  ads={len(snap['ads'])}")
        print(f"Pusheando a Sheets...")
        results = push_snapshot(snap)
        for tab, r in results.items():
            if "error" in r:
                print(f"  {tab}: ERROR {r['error']}")
            else:
                print(f"  {tab}: appended={r['appended']}  updated={r['updated']}")

    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
