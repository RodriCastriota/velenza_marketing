---
name: add-lead
description: Agrega un lead nuevo a la sheet `leads`. Usar cuando el usuario diga "sumá un lead", "entró fulano por WSP", "che, agregá a juana al CRM", o cualquier variacion sobre cargar un lead manualmente.
---

# Add Lead

Inserta una fila nueva en el tab `leads` del Google Sheet de CRM.

## Inputs (lo que pide al usuario si no estan)

Obligatorios:
- `nombre`
- `telefono` (normalizar a E.164: +54...)
- `fuente` (`lead_form` / `wsp_directo` / `ig_dm` / `referido` / `otro`)

Opcionales:
- `email`
- `campaign_id` / `campaign_name`
- `adset_id` / `adset_name`
- `ad_id` / `ad_name`
- `platform` (`fb` / `ig` / `wa`)
- `link_ad_origen` (link al ad cuando viene de WSP)
- `notas`

## Comportamiento

1. Genera `lead_id` interno con esquema `L-YYYY-NNNN` (correlativo del año).
2. `created_time` = ahora (timezone AR).
3. `stage_actual` = `nuevo`.
4. `last_update` = ahora.
5. Inserta fila al final del tab.
6. Confirma en una linea: lead_id + nombre + fuente.

## Errores

- Si ya existe un lead con el mismo telefono activo (no perdido/comprado), avisa y pregunta si quiere updatear ese o forzar uno nuevo.
- Si falta dato obligatorio, lo pide. No inventa.
