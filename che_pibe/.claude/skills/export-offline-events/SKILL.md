---
name: export-offline-events
description: Genera un CSV de eventos offline para subir a Meta Events Manager. Usar cuando el usuario diga "armame el csv de eventos offline", "preparame los eventos de esta semana para subir a meta", o cualquier variacion sobre exportar conversiones offline.
---

# Export Offline Events

Lee la sheet `leads`, filtra por rango de fechas, y arma un CSV en el formato que pide Meta.

## Input

- `desde` (default: hace 7 dias)
- `hasta` (default: hoy, en horario AR)

## Comportamiento

1. Lee tab `leads`.
2. Para cada lead, genera filas en el CSV segun los timestamps que caigan en el rango:

| Stage Velenza | event_name de Meta | Tipo | Lleva value? |
|---|---|---|---|
| `fecha_calificado` en rango | `QualifiedLead` | custom (categoria Lead) | no |
| `fecha_visito_showroom` en rango | `Schedule` | estandar (Opcion A: Schedule = vino al showroom) | no |
| `fecha_compra` en rango | `Purchase` | estandar | si (`monto_venta_ars` + `currency=ARS`) |

Un mismo lead puede generar 1, 2 o 3 filas segun cuantos eventos cayeron en el rango.

3. Para cada fila, hashear PII con SHA256 (lowercase, trimmed):
   - `email` → SHA256(email.lower().strip())
   - `phone` → SHA256(phone_e164_sin_mas.strip())  ej. `5491155556666`

4. Output: archivo CSV en `che_pibe/exports/offline_events_YYYY-MM-DD_to_YYYY-MM-DD.csv`.

## Formato CSV

```
event_name,event_time,email,phone,value,currency,order_id
QualifiedLead,2026-04-20T15:30:00Z,abc123…,def456…,,,L-2026-0001
Schedule,2026-04-22T11:00:00Z,abc123…,def456…,,,L-2026-0001
Purchase,2026-04-25T18:45:00Z,abc123…,def456…,850000,ARS,L-2026-0001
```

- `event_time` en ISO 8601 UTC.
- `order_id` = `lead_id` interno (sirve para deduplicar si subis el CSV dos veces).
- `value` y `currency` solo en `Purchase`.

## Despues

Decile al usuario:
- Path al CSV generado.
- Cantidad de filas por evento.
- Pasos para subir: Events Manager → Data Sources → Offline Event Set → Upload Events → seleccionar CSV → mapear columnas → confirmar.

## Errores

- Si un lead `comprado` no tiene `monto_venta_ars`, avisa antes de generar el CSV (no inventes monto).
- Si email o phone estan vacios, salta esa fila Y avisa (Meta necesita al menos un identifier para matchear).
