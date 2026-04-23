"""Analyzer experto de paid media via Claude API.

Toma el snapshot del dia + baseline de los 7 dias previos y pide a Claude
(Opus 4.7, adaptive thinking) un analisis tipo experto con deteccion de
anomalias y recomendaciones accionables.

Auth: env ANTHROPIC_API_KEY o archivo .anthropic_key local.
"""

import datetime
import json
import os
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_api import (
    fetch_daily_snapshot,
    get_insights_for_campaign,
    list_active_campaigns,
    parse_insights_row,
)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 6000

BUSINESS_CONTEXT = """# Contexto del negocio

- Marca: **Velenza Outdoor** (muebles outdoor, Argentina).
- Cuenta publicitaria: act_1130383065959763.
- Campana activa: VLZ_LEADS_WSP_ABR_2026 (OUTCOME_LEADS, CTWA).
- Destino principal: WhatsApp Business (mensajes).
- Moneda: ARS. Budget diario en ARS (ya convertido desde minor units).
- Pais: Argentina, horario AR (UTC-3).

## Adsets conocidos
- SHOWROOM_SANISIDRO (audiencia local San Isidro + intereses muebles).
- AMPLIA_ABR (audiencia amplia Argentina).

## Evento primario por adset
- Si destination_type = WHATSAPP -> `onsite_conversion.messaging_conversation_started_7d`.
- Si LEAD_FORM_MESSENGER -> `lead`.
- A nivel campana sumamos ambos.

## Disciplina de analisis (IMPORTANTE)

1. **Learning phase**: un adset no sale de learning hasta ~50 conversiones / 7 dias.
   Mientras este en learning, el CPA y el volumen son inestables por diseno.
2. **Volumen estadistico**: no rankees ads ni adsets con < 1000 impresiones diarias.
   Con menos datos las diferencias son ruido, no senal.
3. **No saques conclusiones prematuras**: si una campana recien arranco (menos de 3-4 dias)
   o un ad tiene pocas impresiones, explicitalo y evita recomendar pausar/duplicar.
4. **Compara contra baseline**: el target day siempre contra el promedio de los 7 dias previos,
   no contra 1 solo dia.
5. **Anomalias relevantes**: pico/caida >30% en CPM, CTR, CPC, CPL con volumen suficiente.
   Cambios de frequency significativos (>3). Rankings en below_average.
6. **Recomendaciones**: accionables, especificas (que adset/ad, que accion). Si no hay
   nada claro que recomendar, decilo. No inventes recomendaciones de relleno.

## Formato de salida

Markdown estructurado asi:

```
## Resumen ejecutivo
<2-3 bullets: como viene el dia vs baseline>

## Nivel campana
<comparativa target_day vs 7d_avg, flags de atencion>

## Nivel adsets
<un bloque por adset: estado, flags, notas>

## Nivel ads
<top performers + alertas de ads con ranking malo o CTR bajo>

## Recomendaciones
<lista accionable. Si no hay, decir "sin cambios sugeridos para hoy">

## Dudas / revision manual
<cosas que no puedo juzgar solo con metricas (copy, creatividad, WSP config)>
```

Sin emojis. Tono tecnico rioplatense (voseo, "campana", "conjunto de anuncios").
"""


# ---------- Auth ----------

def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    key_file = ROOT / ".anthropic_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    raise RuntimeError("No se encontro ANTHROPIC_API_KEY (env) ni .anthropic_key (local).")


# ---------- Baseline 7 dias ----------

def _agg_numeric(rows: list[dict], keys: list[str]) -> dict:
    out = {}
    for k in keys:
        out[k] = sum((r.get(k) or 0) for r in rows)
    return out


def build_baseline(target_date: str) -> dict:
    """Agrega 7 dias previos (target-7 a target-1) en totales + promedios diarios."""
    d = datetime.date.fromisoformat(target_date)
    since = (d - datetime.timedelta(days=7)).isoformat()
    until = (d - datetime.timedelta(days=1)).isoformat()

    campaigns = list_active_campaigns()
    baseline = {
        "window": {"since": since, "until": until, "days": 7},
        "campaigns": [],
        "adsets": [],
        "ads": [],
    }

    for c in campaigns:
        cid = c["id"]
        cname = c.get("name", "")

        # Campaign totals en la ventana (1 sola call)
        camp_rows = get_insights_for_campaign(cid, "campaign", since, until)
        camp_parsed = parse_insights_row(camp_rows[0]) if camp_rows else None
        if camp_parsed:
            baseline["campaigns"].append({
                "campaign_id": cid,
                "campaign_name": cname,
                "totals_7d": camp_parsed,
                "daily_avg": _per_day(camp_parsed, 7),
            })

        # Adset totals
        adset_rows = get_insights_for_campaign(cid, "adset", since, until)
        for r in adset_rows:
            parsed = parse_insights_row(r)
            baseline["adsets"].append({
                "campaign_id": cid,
                "adset_id": r.get("adset_id"),
                "totals_7d": parsed,
                "daily_avg": _per_day(parsed, 7),
            })

        # Ad totals
        ad_rows = get_insights_for_campaign(cid, "ad", since, until)
        for r in ad_rows:
            parsed = parse_insights_row(r)
            baseline["ads"].append({
                "campaign_id": cid,
                "adset_id": r.get("adset_id"),
                "ad_id": r.get("ad_id"),
                "totals_7d": parsed,
                "daily_avg": _per_day(parsed, 7),
            })

    return baseline


def _per_day(parsed: dict, days: int) -> dict:
    """Divide metricas acumulables por dias para obtener promedio diario."""
    if days <= 0:
        return {}
    accumulable = {
        "spend", "impressions", "reach", "link_clicks", "conversions",
        "video_views", "thruplays",
        "video_p25_watched", "video_p50_watched", "video_p75_watched", "video_p100_watched",
    }
    out = {}
    for k, v in parsed.items():
        if k in accumulable and isinstance(v, (int, float)):
            out[k] = round(v / days, 2)
    # CPL promedio recalculado
    if out.get("conversions", 0) > 0:
        out["cpl"] = round(out["spend"] / out["conversions"], 2)
    else:
        out["cpl"] = None
    return out


# ---------- Llamada a Claude ----------

def build_user_message(target_date: str, snapshot: dict, baseline: dict) -> str:
    return (
        f"# Reporte diario - {target_date}\n\n"
        f"## Snapshot del dia\n\n```json\n{json.dumps(snapshot, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Baseline 7 dias previos ({baseline['window']['since']} a {baseline['window']['until']})\n\n"
        f"```json\n{json.dumps(baseline, indent=2, ensure_ascii=False)}\n```\n\n"
        f"Hace el analisis siguiendo el formato del system prompt."
    )


def analyze(target_date: str, snapshot: dict | None = None, baseline: dict | None = None) -> str:
    if snapshot is None:
        snapshot = fetch_daily_snapshot(target_date)
    if baseline is None:
        baseline = build_baseline(target_date)

    client = anthropic.Anthropic(api_key=load_api_key())

    system = [
        {
            "type": "text",
            "text": BUSINESS_CONTEXT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    user_msg = build_user_message(target_date, snapshot, baseline)

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        final = stream.get_final_message()

    parts = []
    for block in final.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


# ---------- CLI ----------

def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/claude_analyzer.py <comando> [args]")
        print("Comandos:")
        print("  analyze <YYYY-MM-DD>   Pulls snapshot + baseline y printea analisis")
        print("  baseline <YYYY-MM-DD>  Solo printea el baseline (debug)")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "analyze":
        if len(sys.argv) < 3:
            print("Uso: analyze <YYYY-MM-DD>")
            sys.exit(1)
        date = sys.argv[2]
        print(f"Pulling snapshot {date}...", file=sys.stderr)
        snapshot = fetch_daily_snapshot(date)
        print(f"Pulling baseline 7d...", file=sys.stderr)
        baseline = build_baseline(date)
        print(f"Llamando a Claude {MODEL}...", file=sys.stderr)
        out = analyze(date, snapshot, baseline)
        print(out)

    elif cmd == "baseline":
        if len(sys.argv) < 3:
            print("Uso: baseline <YYYY-MM-DD>")
            sys.exit(1)
        date = sys.argv[2]
        baseline = build_baseline(date)
        print(json.dumps(baseline, indent=2, ensure_ascii=False))

    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
