# Velenza Marketing Agent

Agente de analisis automatizado para paid media de Velenza Outdoor (muebles outdoor premium).

## Proposito

Generar reportes diarios que combinen:
- Metricas de performance de Meta Ads (Graph API v21.0)
- Analisis visual de creativos (Gemini API)
- Recomendaciones accionables en espaniol rioplatense

## Contexto de negocio

- **Marca:** Velenza Outdoor — muebles de exterior premium, ticket alto, mercado AR
- **Zona foco:** Zona Norte GBA (San Isidro y radio 38km)
- **Cuenta publicitaria Meta:** `act_1130383065959763` (ARS, timezone Buenos Aires)
- **Business Manager:** `24735564356053214`
- **Pagina Facebook:** `857189310805133` (Velenza Outdoor)
- **Instagram Business:** `17841476998730846`
- **Campania activa abril 2026:** `VLZ_LEADS_WSP_ABR_2026` (id `120241612259900265`)
  - Adset `VLZ_ADSET_SHOWROOM_SANISIDRO` (id `120241612632110265`): Lead Form Messenger, radio 38km San Isidro
  - Adset `VLZ_ADSET_AMPLIA_ABR` (id `120241612259890265`): WhatsApp, Argentina broad

## Credenciales (nunca commitear)

- `.meta_token` — System User Access Token de Business Manager (sin expiracion)
- `.gemini_key` — API key de Google AI Studio

Ambos archivos viven en la raiz del folder y estan en `.gitignore`.

## Convenciones

- Responder siempre en espaniol rioplatense (vos, dale).
- Nivel tecnico: peer de paid media manager, no entry-level.
- Respetar umbrales estadisticos: no sacar conclusiones sobre ads con <1000-3000 impresiones o <50 link clicks.
- Learning phase dura ~7 dias o 50 eventos/adset. Durante ese periodo no pausar ads ni reasignar budget.
- Distinguir explicitamente "senial temprana" (hipotesis) vs "conclusion" (data suficiente).
- Salidas persistentes del reporte: Google Sheets (data) + Notion (analisis). No se generan archivos `.md` por dia en el repo.
- **Nunca inventar.** Si hay duda con un dato, id, metrica, comportamiento de API o cualquier otra cosa, levantarlo y preguntar antes de seguir. Mejor frenar y chequear que asumir y meter ruido en el reporte.

## Estructura

```
velenza_marketing/                raiz del repo (multi-agente)
├── .git/
├── .github/workflows/            workflows GitHub Actions (deben vivir aca)
├── .gitignore
└── meta_analyst/                 ESTE agente (paid media analysis)
    ├── CLAUDE.md                 este archivo
    ├── AGENTS.md                 espejo para Codex
    ├── .meta_token               System User Token Meta (gitignored)
    ├── .gcp_sa.json              service account Google (gitignored)
    ├── .anthropic_key            API key Anthropic (gitignored)
    ├── .notion_token             token Notion (gitignored)
    ├── .sheet_url                URL de la sheet (gitignored)
    ├── .claude/skills/           skills reutilizables (Claude Code)
    ├── .agents/skills/           skills reutilizables (Codex)
    ├── requirements.txt
    └── scripts/                  helpers Python
```

## Roadmap de skills

1. `meta-insights` — pull de insights (acumulado + por dia) para campaign/adset/ad
2. `meta-ad-creatives` — extrae URLs e imagenes de los ads activos
3. `gemini-analyze` — envia imagenes + prompt a Gemini y devuelve analisis
4. `daily-report` — orquesta las 3 anteriores y escribe el reporte
5. `wsp-config-check` — verifica que la conexion WhatsApp Business este OK

## Usuario

Roro Castriota (agustinrcastriota@gmail.com) — paid media manager de Velenza.
