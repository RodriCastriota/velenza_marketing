---
name: meta-insights
description: Trae datos crudos de Meta Ads (campanas, conjuntos, anuncios activos, snapshot diario). Usar cuando el usuario pida "que campanas estan activas", "como viene tal adset", "los anuncios activos", "metricas crudas de Meta" o pida bajar datos sin querer el analisis Claude.
---

# Meta Insights crudo

Para data raw de Meta sin pasar por Claude/Sheets, ejecuta `scripts/meta_api.py` segun lo que pida el usuario:

```bash
# Listar campanas activas
python scripts/meta_api.py list-active-campaigns

# Listar adsets activos de una campana
python scripts/meta_api.py list-active-adsets <campaign_id>

# Listar ads activos de un adset
python scripts/meta_api.py list-active-ads <adset_id>

# Snapshot completo de un dia (json)
python scripts/meta_api.py fetch-daily <YYYY-MM-DD>

# Snapshot resumen de un dia (texto legible)
python scripts/meta_api.py fetch-daily-summary <YYYY-MM-DD>
```

Cuenta: `act_1130383065959763` (Velenza Outdoor).

Si el usuario solo quiere "ver como viene <adset>", usa `fetch-daily-summary` para hoy o ayer y filtralo en la respuesta.

Para reporte diario completo (con Sheets + analisis Claude) usa la skill `daily-report` en vez de esta.
