"""Orchestrator del reporte diario Velenza.

Flujo:
  1. Pull snapshot del dia desde Meta (campaigns/adsets/ads ACTIVE).
  2. Push snapshot a Google Sheets (upsert).
  3. Pull baseline 7 dias previos.
  4. Llamar a Claude para analisis experto.
  5. Push analisis a Notion (unica salida persistente del markdown).

Usado por GitHub Actions cron (08:50 AR / 11:50 UTC) y tambien manual.
"""

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from claude_analyzer import analyze, build_baseline
from meta_api import fetch_daily_snapshot
from notion_writer import upsert_report as notion_upsert
from sheets_writer import push_snapshot


def yesterday_ar() -> str:
    """Fecha de ayer en horario AR (UTC-3)."""
    ar_now = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    return (ar_now.date() - datetime.timedelta(days=1)).isoformat()


def run(target_date: str) -> str:
    print(f"[1/5] Pulling snapshot Meta {target_date}...")
    snapshot = fetch_daily_snapshot(target_date)
    print(f"      campaigns={len(snapshot['campaigns'])} "
          f"adsets={len(snapshot['adsets'])} ads={len(snapshot['ads'])}")

    print(f"[2/5] Push a Google Sheets...")
    sheet_results = push_snapshot(snapshot)
    for tab, r in sheet_results.items():
        if "error" in r:
            print(f"      {tab}: ERROR {r['error']}")
        else:
            print(f"      {tab}: appended={r['appended']} updated={r['updated']}")

    print(f"[3/5] Pulling baseline 7d...")
    baseline = build_baseline(target_date)

    print(f"[4/5] Analisis Claude (Opus 4.7, adaptive thinking)...")
    analysis_md = analyze(target_date, snapshot, baseline)
    full_md = f"# Reporte diario Velenza - {target_date}\n\n" + analysis_md

    print("----- ANALISIS -----")
    print(full_md)
    print("----- /ANALISIS -----")

    print(f"[5/5] Push a Notion...")
    notion_url = notion_upsert(target_date, snapshot, full_md)
    print(f"      pagina Notion: {notion_url}")

    return notion_url


def main() -> None:
    if len(sys.argv) >= 2:
        target = sys.argv[1]
    else:
        target = yesterday_ar()
        print(f"(sin fecha pasada, uso ayer AR = {target})")

    run(target)


if __name__ == "__main__":
    main()
