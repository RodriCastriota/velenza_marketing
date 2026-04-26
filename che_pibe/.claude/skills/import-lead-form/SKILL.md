---
name: import-lead-form
description: Importa leads desde un CSV exportado del Lead Form de Meta a la sheet `leads`. Usar cuando el usuario diga "importa el csv de leads", "metele este export del form", "subi los leads de tal campania", o entregue un archivo de export del lead form.
---

# Import Lead Form

Parsea un CSV exportado del Lead Ads Manager de Meta e inserta leads nuevos en la sheet.

## Input

- `path_csv`: ruta al CSV (el usuario lo sube o lo pega).

Columnas esperadas en el CSV (formato Meta Lead Ads):
`id, created_time, ad_id, ad_name, adset_id, adset_name, campaign_id, campaign_name, form_id, form_name, id_organic, platform, <pregunta del form>, email, full_name, phone_number, lead_status`

(El nombre exacto de la columna "pregunta del form" varia por formulario — capturarlo dinamicamente.)

## Mapeo a la sheet

| CSV Meta | Sheet `leads` |
|---|---|
| `id` | `meta_lead_id` |
| `created_time` | `created_time` |
| `ad_id`, `ad_name`, etc. | igual nombre |
| `email` | `email` |
| `full_name` | `nombre` |
| `phone_number` | `telefono` (normalizar a E.164) |
| `<pregunta del form>` | `respuesta_form` |
| (fijo) | `fuente=lead_form` |
| (fijo) | `stage_actual=nuevo` |
| (generado) | `lead_id` interno (`L-YYYY-NNNN`) |
| (ahora) | `last_update` |

## Comportamiento

1. Lee el CSV.
2. Para cada fila, dedupe por `meta_lead_id`: si ya existe en la sheet, **saltea** (no sobreescribe).
3. Inserta los nuevos en bloque (batch update).
4. Reporta: total filas en CSV, insertadas, salteadas por dedup, errores.

## Errores

- Si falta una columna esperada, avisa que columna falta y pide confirmacion para continuar (puede ser un export viejo o de otro form).
- Si una fila trae datos invalidos (telefono malformado, email invalido), la marca con un flag pero igual la inserta — mejor tener el lead que perderlo.
