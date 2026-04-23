"""Orchestrator del reporte diario Velenza.

Flujo:
  1. Pull snapshot del dia desde Meta (campaigns/adsets/ads ACTIVE).
  2. Pull baseline 7 dias previos.
  3. Push snapshot a Google Sheets (upsert).
  4. Llamar a Claude para analisis experto.
  5. Guardar markdown en reports/YYYY-MM-DD.md.

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

REPORTS_DIR = ROOT / "reports"


def yesterday_ar() -> str:
    """Fecha de ayer en horario AR (UTC-3)."""
    ar_now = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
    return (ar_now.date() - datetime.timedelta(days=1)).isoformat()


def run(target_date: str) -> Path:
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

    REPORTS_DIR.mkdir(exist_ok=True)
    out_file = REPORTS_DIR / f"{target_date}.md"
    header = f"# Reporte diario Velenza - {target_date}\n\n"
    full_md = header + analysis_md
    out_file.write_text(full_md, encoding="utf-8")
    print(f"      reporte guardado en {out_file.relative_to(ROOT)}")

    print(f"[5/5] Push a Notion...")
    try:
        notion_url = notion_upsert(target_date, snapshot, full_md)
        print(f"      pagina Notion: {notion_url}")
    except Exception as e:
        print(f"      ERROR Notion (no critico): {e}")

    return out_file


def main() -> None:
    if len(sys.argv) >= 2:
        target = sys.argv[1]
    else:
        target = yesterday_ar()
        print(f"(sin fecha pasada, uso ayer AR = {target})")

    run(target)


if __name__ == "__main__":
    main()
