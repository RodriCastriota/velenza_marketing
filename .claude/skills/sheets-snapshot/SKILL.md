---
name: sheets-snapshot
description: Push o backfill manual de un dia a Google Sheets (tabs campaigns/adsets/ads, upsert por date+entity_id). Usar cuando el usuario pida "subi a sheets el dia X", "backfill desde X a Y", "actualiza la sheet con tal fecha", o detectes que falta un dia en la sheet.
---

# Sheets Snapshot push

Para subir 1 dia puntual:

```bash
python scripts/sheets_writer.py push-daily <YYYY-MM-DD>
```

Es upsert por (`date`, `entity_id`): si la fila existe la actualiza, sino la appendea. Sirve tanto para subir el dia de hoy como para backfill historico.

Para verificar auth/conexion sin tocar datos:

```bash
python scripts/sheets_writer.py test-auth
```

Para backfill de varios dias seguidos, llamar el comando una vez por fecha (loopear desde bash).

Si el usuario pide "el reporte completo con analisis", usa la skill `daily-report` en vez de esta — esta solo pushea data, no llama a Claude.
