"""Cliente Graph API para el agente Velenza.

Lee el token desde variable de entorno META_TOKEN o desde .meta_token local.
No depende de librerias externas (solo stdlib).
"""

import datetime
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = "v21.0"
AD_ACCOUNT_ID = "act_1130383065959763"

ROOT = Path(__file__).resolve().parent.parent

INSIGHTS_FIELDS = [
    "impressions", "reach", "frequency", "spend",
    "clicks", "ctr", "cpc", "cpm",
    "inline_link_clicks", "inline_link_click_ctr", "cost_per_inline_link_click",
    "actions", "cost_per_action_type",
    "video_play_actions",
    "video_thruplay_watched_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p100_watched_actions",
    "video_avg_time_watched_actions",
    "cost_per_thruplay",
    "quality_ranking",
    "engagement_rate_ranking",
    "conversion_rate_ranking",
]


# ---------- Token + HTTP ----------

def load_token() -> str:
    token = os.environ.get("META_TOKEN")
    if token:
        return token.strip()
    token_file = ROOT / ".meta_token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    raise RuntimeError("No se encontro META_TOKEN (env var ni .meta_token).")


def graph_get(path: str, params: dict | None = None, token: str | None = None) -> dict:
    if token is None:
        token = load_token()
    params = dict(params or {})
    params["access_token"] = token

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    query = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{url}?{query}"

    ctx = ssl.create_default_context()
    req = urllib.request.Request(full_url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph API HTTP {e.code}: {body}") from e


def graph_get_paged(path: str, params: dict | None = None, token: str | None = None) -> list[dict]:
    if token is None:
        token = load_token()
    params = dict(params or {})
    all_data: list[dict] = []
    cursor = None
    while True:
        page_params = dict(params)
        if cursor:
            page_params["after"] = cursor
        resp = graph_get(path, page_params, token)
        all_data.extend(resp.get("data", []))
        paging = resp.get("paging", {})
        cursor = paging.get("cursors", {}).get("after")
        if not paging.get("next"):
            break
    return all_data


# ---------- Listados de entities ACTIVE ----------

def _active_filter() -> str:
    return json.dumps([{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}])


def list_active_campaigns(account_id: str = AD_ACCOUNT_ID) -> list[dict]:
    fields = "id,name,objective,effective_status,status,daily_budget,lifetime_budget,start_time,stop_time"
    return graph_get_paged(
        f"{account_id}/campaigns",
        {"fields": fields, "filtering": _active_filter(), "limit": 100},
    )


def list_active_adsets(campaign_id: str) -> list[dict]:
    fields = "id,name,effective_status,status,optimization_goal,destination_type,daily_budget,lifetime_budget"
    return graph_get_paged(
        f"{campaign_id}/adsets",
        {"fields": fields, "filtering": _active_filter(), "limit": 100},
    )


def list_active_ads(adset_id: str) -> list[dict]:
    fields = "id,name,effective_status,status,adset_id,creative{id}"
    return graph_get_paged(
        f"{adset_id}/ads",
        {"fields": fields, "filtering": _active_filter(), "limit": 100},
    )


# ---------- Parseo de insights ----------

def _int(x, default=0):
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return default


def _float(x, default=0.0):
    try:
        return float(x)
    except (ValueError, TypeError):
        return default


def _action_value(actions: list | None, action_type: str) -> int:
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return _int(a.get("value"))
    return 0


def _first_list_value(items: list | None) -> int:
    if not items:
        return 0
    try:
        return _int(items[0].get("value"))
    except (AttributeError, IndexError):
        return 0


def pick_primary_conversion(actions: list | None, destination_type: str | None) -> tuple[int, str]:
    """Segun destination_type del adset, elige que evento contar como conversion."""
    if destination_type == "WHATSAPP":
        event = "onsite_conversion.messaging_conversation_started_7d"
        return _action_value(actions, event), event
    # default: leads (form en FB/IG/Messenger)
    event = "lead"
    return _action_value(actions, event), event


def parse_insights_row(row: dict, destination_type: str | None = None) -> dict:
    out = {
        "spend": round(_float(row.get("spend")), 2),
        "impressions": _int(row.get("impressions")),
        "reach": _int(row.get("reach")),
        "frequency": round(_float(row.get("frequency")), 3),
        "ctr": round(_float(row.get("ctr")), 3),
        "link_ctr": round(_float(row.get("inline_link_click_ctr")), 3),
        "link_clicks": _int(row.get("inline_link_clicks")),
        "cpc_link": round(_float(row.get("cost_per_inline_link_click")), 2),
        "cpm": round(_float(row.get("cpm")), 2),
        "video_views": _first_list_value(row.get("video_play_actions")),
        "thruplays": _first_list_value(row.get("video_thruplay_watched_actions")),
        "video_p25_watched": _first_list_value(row.get("video_p25_watched_actions")),
        "video_p50_watched": _first_list_value(row.get("video_p50_watched_actions")),
        "video_p75_watched": _first_list_value(row.get("video_p75_watched_actions")),
        "video_p100_watched": _first_list_value(row.get("video_p100_watched_actions")),
        "video_avg_time_watched_sec": round(_float(_first_list_value(row.get("video_avg_time_watched_actions"))), 2),
        "cost_per_thruplay": round(_float(row.get("cost_per_thruplay")), 2),
    }

    actions = row.get("actions", [])
    if destination_type:
        count, event = pick_primary_conversion(actions, destination_type)
    else:
        # Campaign-level: sumar lead + wsp
        leads = _action_value(actions, "lead")
        wsp = _action_value(actions, "onsite_conversion.messaging_conversation_started_7d")
        count = leads + wsp
        if leads and wsp:
            event = "mixed(lead+wsp)"
        elif leads:
            event = "lead"
        elif wsp:
            event = "messaging_conversation_started_7d"
        else:
            event = ""

    out["conversions"] = count
    out["conversion_type"] = event
    out["cpl"] = round(out["spend"] / count, 2) if count > 0 else None
    return out


def empty_parsed() -> dict:
    return {
        "spend": 0.0, "impressions": 0, "reach": 0, "frequency": 0.0,
        "ctr": 0.0, "link_ctr": 0.0, "link_clicks": 0,
        "cpc_link": 0.0, "cpm": 0.0,
        "conversions": 0, "conversion_type": "", "cpl": None,
        "video_views": 0, "thruplays": 0,
        "video_p25_watched": 0, "video_p50_watched": 0,
        "video_p75_watched": 0, "video_p100_watched": 0,
        "video_avg_time_watched_sec": 0.0, "cost_per_thruplay": 0.0,
    }


def _budget_to_ars(raw) -> float | None:
    """Meta devuelve budget en unidades menores (cents). Para ARS dividir por 100."""
    if raw is None or raw == "":
        return None
    try:
        return round(int(raw) / 100, 2)
    except (ValueError, TypeError):
        return None


# ---------- Pull diario (orquesta los tres niveles) ----------

def get_insights_for_campaign(campaign_id: str, level: str, since: str, until: str) -> list[dict]:
    fields_list = list(INSIGHTS_FIELDS)
    if level in ("adset", "ad"):
        fields_list += ["adset_id"]
    if level == "ad":
        fields_list += ["ad_id"]
    params = {
        "level": level,
        "fields": ",".join(fields_list),
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 500,
    }
    return graph_get_paged(f"{campaign_id}/insights", params)


def fetch_daily_snapshot(date_str: str) -> dict:
    """Devuelve dict con listas campaigns/adsets/ads para el dia dado.

    Incluye entities ACTIVE aunque no hayan tenido entrega (fila con 0s).
    """
    run_ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    result: dict = {"date": date_str, "campaigns": [], "adsets": [], "ads": []}

    campaigns = list_active_campaigns()

    for c in campaigns:
        cid = c["id"]
        cname = c.get("name", "")

        # Campaign-level insights
        camp_rows = get_insights_for_campaign(cid, "campaign", date_str, date_str)
        camp_parsed = parse_insights_row(camp_rows[0]) if camp_rows else empty_parsed()
        result["campaigns"].append({
            "date": date_str,
            "campaign_id": cid,
            "campaign_name": cname,
            "objective": c.get("objective"),
            "effective_status": c.get("effective_status"),
            "daily_budget": _budget_to_ars(c.get("daily_budget")),
            **camp_parsed,
            "run_timestamp": run_ts,
        })

        # Adsets meta
        adsets = list_active_adsets(cid)
        adsets_by_id = {a["id"]: a for a in adsets}

        # Adset-level insights
        adset_rows = get_insights_for_campaign(cid, "adset", date_str, date_str)
        insights_by_adset = {r.get("adset_id"): r for r in adset_rows}

        for a in adsets:
            aid = a["id"]
            dest = a.get("destination_type")
            row = insights_by_adset.get(aid)
            parsed = parse_insights_row(row, dest) if row else empty_parsed()
            if not row:
                parsed["conversion_type"] = (
                    "onsite_conversion.messaging_conversation_started_7d" if dest == "WHATSAPP" else "lead"
                )
            result["adsets"].append({
                "date": date_str,
                "campaign_id": cid,
                "campaign_name": cname,
                "adset_id": aid,
                "adset_name": a.get("name", ""),
                "effective_status": a.get("effective_status"),
                "optimization_goal": a.get("optimization_goal"),
                "destination_type": dest,
                "daily_budget": _budget_to_ars(a.get("daily_budget")),
                **parsed,
                "run_timestamp": run_ts,
            })

        # Ads meta (iteramos por adset para mantener el adset_id asociado)
        ads_all: list[dict] = []
        for a in adsets:
            for ad in list_active_ads(a["id"]):
                ad["_adset_id"] = a["id"]
                ads_all.append(ad)

        # Ad-level insights
        ad_rows = get_insights_for_campaign(cid, "ad", date_str, date_str)
        insights_by_ad = {r.get("ad_id"): r for r in ad_rows}

        for ad in ads_all:
            adid = ad["id"]
            adset_id = ad["_adset_id"]
            parent_adset = adsets_by_id.get(adset_id, {})
            dest = parent_adset.get("destination_type")
            row = insights_by_ad.get(adid)
            parsed = parse_insights_row(row, dest) if row else empty_parsed()
            if not row:
                parsed["conversion_type"] = (
                    "onsite_conversion.messaging_conversation_started_7d" if dest == "WHATSAPP" else "lead"
                )
            creative = ad.get("creative") or {}
            result["ads"].append({
                "date": date_str,
                "campaign_id": cid,
                "campaign_name": cname,
                "adset_id": adset_id,
                "adset_name": parent_adset.get("name", ""),
                "ad_id": adid,
                "ad_name": ad.get("name", ""),
                "creative_id": creative.get("id"),
                "effective_status": ad.get("effective_status"),
                **parsed,
                "quality_ranking": (row or {}).get("quality_ranking"),
                "engagement_rate_ranking": (row or {}).get("engagement_rate_ranking"),
                "conversion_rate_ranking": (row or {}).get("conversion_rate_ranking"),
                "run_timestamp": run_ts,
            })

    return result


# ---------- CLI ----------

def _cli_print_campaigns(campaigns: list[dict]) -> None:
    if not campaigns:
        print("  (sin campanias ACTIVE)")
        return
    for c in campaigns:
        budget = c.get("daily_budget") or c.get("lifetime_budget") or "adset-level"
        print(f"  [{c['id']}] {c['name']}  objective={c.get('objective')}  budget={budget}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/meta_api.py <comando> [args]")
        print("Comandos:")
        print("  list-active-campaigns")
        print("  list-active-adsets <campaign_id>")
        print("  list-active-ads <adset_id>")
        print("  fetch-daily <YYYY-MM-DD>               # imprime JSON completo")
        print("  fetch-daily-summary <YYYY-MM-DD>       # imprime resumen legible")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list-active-campaigns":
        campaigns = list_active_campaigns()
        print(f"Campanias ACTIVE: {len(campaigns)}\n")
        _cli_print_campaigns(campaigns)

    elif cmd == "list-active-adsets":
        if len(sys.argv) < 3:
            print("Uso: list-active-adsets <campaign_id>")
            sys.exit(1)
        adsets = list_active_adsets(sys.argv[2])
        print(f"Adsets ACTIVE: {len(adsets)}\n")
        for a in adsets:
            print(f"  [{a['id']}] {a['name']}")
            print(f"      optim={a.get('optimization_goal')}  dest={a.get('destination_type')}  daily_budget={_budget_to_ars(a.get('daily_budget'))}")

    elif cmd == "list-active-ads":
        if len(sys.argv) < 3:
            print("Uso: list-active-ads <adset_id>")
            sys.exit(1)
        ads = list_active_ads(sys.argv[2])
        print(f"Ads ACTIVE: {len(ads)}\n")
        for ad in ads:
            creative_id = (ad.get("creative") or {}).get("id")
            print(f"  [{ad['id']}] {ad['name']}  creative_id={creative_id}")

    elif cmd == "fetch-daily":
        if len(sys.argv) < 3:
            print("Uso: fetch-daily <YYYY-MM-DD>")
            sys.exit(1)
        snapshot = fetch_daily_snapshot(sys.argv[2])
        print(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))

    elif cmd == "fetch-daily-summary":
        if len(sys.argv) < 3:
            print("Uso: fetch-daily-summary <YYYY-MM-DD>")
            sys.exit(1)
        date = sys.argv[2]
        snap = fetch_daily_snapshot(date)
        print(f"=== SNAPSHOT {date} ===\n")
        print(f"Campaigns ({len(snap['campaigns'])}):")
        for r in snap["campaigns"]:
            print(f"  {r['campaign_name']}  spend={r['spend']}  impr={r['impressions']}  conv={r['conversions']}  cpl={r['cpl']}")
        print(f"\nAdsets ({len(snap['adsets'])}):")
        for r in snap["adsets"]:
            print(f"  {r['adset_name']}  [{r['destination_type']}]  spend={r['spend']}  impr={r['impressions']}  conv={r['conversions']}  cpl={r['cpl']}")
        print(f"\nAds ({len(snap['ads'])}):")
        for r in snap["ads"]:
            print(f"  {r['ad_name']}  spend={r['spend']}  impr={r['impressions']}  conv={r['conversions']}  cpl={r['cpl']}")

    else:
        print(f"Comando desconocido: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
