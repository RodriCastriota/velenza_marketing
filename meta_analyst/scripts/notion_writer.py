"""Writer del reporte diario a Notion (database "Reportes Velenza Diarios").

Cada dia = una pagina en la database. Si ya existe una pagina con la misma
fecha, la archiva y crea una nueva (idempotente).

Auth: env NOTION_TOKEN o archivo .notion_token local.
"""

import os
import re
import sys
from pathlib import Path

from notion_client import Client

ROOT = Path(__file__).resolve().parent.parent

# Database creada bajo la pagina Marketing.
# Notion API 2025-09 introdujo data_sources: las queries y page.create
# usan el data_source_id, no el database_id directamente.
DATABASE_ID = "65bfe062-097e-4c95-b3a0-b6fd367a3960"
DATA_SOURCE_ID = "4ee5c7fd-256b-4535-9cf9-8a5590c8fe26"

# Notion limita 2000 chars por rich_text y 100 bloques por request
RICH_TEXT_LIMIT = 1900
CHILDREN_BATCH = 90


def load_token() -> str:
    tok = os.environ.get("NOTION_TOKEN")
    if tok:
        return tok.strip()
    f = ROOT / ".notion_token"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    raise RuntimeError("No se encontro NOTION_TOKEN (env) ni .notion_token (local).")


# ---------- Markdown -> Notion blocks ----------

_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


def _rich_text(text: str) -> list:
    """Convierte un string con **bold** y `code` inline a rich_text array."""
    if not text:
        return []
    parts = []
    for chunk in _INLINE_RE.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**"):
            parts.append(
                {
                    "type": "text",
                    "text": {"content": chunk[2:-2]},
                    "annotations": {"bold": True},
                }
            )
        elif chunk.startswith("`") and chunk.endswith("`"):
            parts.append(
                {
                    "type": "text",
                    "text": {"content": chunk[1:-1]},
                    "annotations": {"code": True},
                }
            )
        else:
            for piece in _chunk_text(chunk, RICH_TEXT_LIMIT):
                parts.append({"type": "text", "text": {"content": piece}})
    return parts


def _chunk_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def md_to_blocks(md: str) -> list[dict]:
    """Conversor minimo: H1/H2/H3, bullets, paragraphs, code fences."""
    blocks: list[dict] = []
    lines = md.split("\n")
    i = 0
    in_code = False
    code_buf: list[str] = []
    code_lang = "plain text"

    while i < len(lines):
        line = lines[i]

        # Code fence
        if line.startswith("```"):
            if in_code:
                code_text = "\n".join(code_buf)
                for chunk in _chunk_text(code_text, RICH_TEXT_LIMIT):
                    blocks.append(
                        {
                            "object": "block",
                            "type": "code",
                            "code": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": chunk}}
                                ],
                                "language": code_lang,
                            },
                        }
                    )
                code_buf = []
                in_code = False
            else:
                in_code = True
                lang = line[3:].strip() or "plain text"
                code_lang = (
                    lang
                    if lang
                    in {
                        "python",
                        "javascript",
                        "json",
                        "bash",
                        "shell",
                        "markdown",
                        "html",
                        "css",
                        "yaml",
                        "sql",
                    }
                    else "plain text"
                )
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": _rich_text(stripped[2:])},
                }
            )
        elif stripped.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": _rich_text(stripped[3:])},
                }
            )
        elif stripped.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": _rich_text(stripped[4:])},
                }
            )
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _rich_text(stripped[2:])},
                }
            )
        else:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": _rich_text(stripped)},
                }
            )
        i += 1

    return blocks


# ---------- Resumen numerico ----------

def summary_from_snapshot(snapshot: dict) -> dict:
    camps = snapshot.get("campaigns", [])
    spend = round(sum(c.get("spend") or 0 for c in camps), 2)
    conv = sum(c.get("conversions") or 0 for c in camps)
    imps = sum(c.get("impressions") or 0 for c in camps)
    cpl = round(spend / conv, 2) if conv > 0 else None
    return {"spend": spend, "conversions": conv, "impressions": imps, "cpl": cpl}


# ---------- Upsert ----------

def find_existing_page(client: Client, target_date: str) -> str | None:
    res = client.data_sources.query(
        data_source_id=DATA_SOURCE_ID,
        filter={"property": "Date", "date": {"equals": target_date}},
        page_size=10,
    )
    results = res.get("results", [])
    return results[0]["id"] if results else None


def upsert_report(target_date: str, snapshot: dict, analysis_md: str) -> str:
    client = Client(auth=load_token())
    summary = summary_from_snapshot(snapshot)

    existing_id = find_existing_page(client, target_date)
    if existing_id:
        client.pages.update(page_id=existing_id, archived=True)

    properties = {
        "Fecha": {"title": [{"type": "text", "text": {"content": target_date}}]},
        "Date": {"date": {"start": target_date}},
        "Spend ARS": {"number": summary["spend"]},
        "Conversiones": {"number": summary["conversions"]},
        "Impresiones": {"number": summary["impressions"]},
    }
    if summary["cpl"] is not None:
        properties["CPL ARS"] = {"number": summary["cpl"]}

    blocks = md_to_blocks(analysis_md)
    first_batch = blocks[:CHILDREN_BATCH]
    rest = blocks[CHILDREN_BATCH:]

    page = client.pages.create(
        parent={"type": "data_source_id", "data_source_id": DATA_SOURCE_ID},
        properties=properties,
        children=first_batch,
    )
    page_id = page["id"]

    for i in range(0, len(rest), CHILDREN_BATCH):
        client.blocks.children.append(
            block_id=page_id,
            children=rest[i : i + CHILDREN_BATCH],
        )

    return page["url"]


# ---------- CLI ----------

def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/notion_writer.py <comando> [args]")
        print("Comandos:")
        print("  test-auth                     Verifica auth + database accesible")
        print("  push <YYYY-MM-DD>             Pull snapshot+analyzer y postea a Notion")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test-auth":
        client = Client(auth=load_token())
        ds = client.data_sources.retrieve(DATA_SOURCE_ID)
        title = (ds.get("name") or (ds.get("title") or [{}])[0].get("plain_text", "?"))
        props = list(ds.get("properties", {}).keys())
        print(f"OK data source: '{title}'")
        print(f"  database_id:    {DATABASE_ID}")
        print(f"  data_source_id: {DATA_SOURCE_ID}")
        print(f"  properties: {props}")

    elif cmd == "push":
        if len(sys.argv) < 3:
            print("Uso: push <YYYY-MM-DD>")
            sys.exit(1)
        date = sys.argv[2]
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from claude_analyzer import analyze, build_baseline
        from meta_api import fetch_daily_snapshot

        print(f"Pull snapshot {date}...")
        snap = fetch_daily_snapshot(date)
        print(f"Pull baseline 7d...")
        baseline = build_baseline(date)
        print(f"Analisis Claude...")
        md = analyze(date, snap, baseline)
        print("Push a Notion...")
        url = upsert_report(date, snap, md)
        print(f"OK pagina creada: {url}")

    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
