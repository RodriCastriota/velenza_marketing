---
name: daily-report
description: Genera el reporte diario de paid media Velenza (snapshot Meta + push a Sheets + analisis Codex + push a Notion). Usar cuando el usuario pida "el reporte de hoy", "como viene el dia", "el reporte de ayer", "reporte del <fecha>", o cualquier variacion sobre el reporte diario.
---

# Daily Report Velenza

Cuando el usuario pida el reporte diario, ejecuta directamente:

```bash
python scripts/daily_report.py [YYYY-MM-DD]
```

- Sin fecha: usa ayer en horario AR.
- Con fecha: usa esa fecha (formato `YYYY-MM-DD`).

El script hace:
1. Pull snapshot Meta (campaigns/adsets/ads ACTIVE) del dia.
2. Push a Google Sheets (upsert por date+entity_id).
3. Pull baseline 7 dias previos.
4. Analisis con Codex Opus 4.7 (adaptive thinking).
5. Push del markdown del analisis a Notion (unica salida persistente).

Despues de correr el script, le mostras al usuario:
- Resumen de filas pusheadas a cada tab de Sheets.
- URL de la pagina de Notion generada.
- El contenido del markdown del analisis (lo imprime el script entre marcadores `----- ANALISIS -----`).

Si el script falla:
- Verifica que existan `.meta_token`, `.gcp_sa.json`, `.sheet_url`, `.anthropic_key`, `.notion_token` (o sus env vars).
- No asumas otra cosa, mostra el error real al usuario.
