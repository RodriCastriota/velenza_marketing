---
name: update-lead
description: Actualiza el estado o un campo de un lead existente en la sheet `leads`. Usar cuando el usuario diga "pepito compro", "juana no contesta marcala perdida", "vino al showroom el sabado", "marca a fulano como calificado", o cualquier variacion sobre cambiar el estado de un lead.
---

# Update Lead

Busca un lead por identificador y actualiza el campo correspondiente.

## Inputs

Identificador (al menos uno):
- `telefono` (preferido, mas confiable)
- `nombre`
- `lead_id`

Accion (una de estas):
- `marcar_calificado` -> setea `stage_actual=calificado`, `fecha_calificado=ahora`.
- `marcar_visito_showroom` -> setea `stage_actual=visito_showroom`, `fecha_visito_showroom=ahora`. (Nota: este stage corresponde al evento `Schedule` de Meta en Opcion A.)
- `marcar_comprado` -> setea `stage_actual=comprado`, `fecha_compra=ahora`, requiere `monto_venta_ars`.
- `marcar_perdido` -> setea `stage_actual=perdido`, requiere `motivo_perdido` (`no_contesta` / `precio` / `timing` / `geo` / `competidor` / `otro`).
- `update_campo` -> generico, recibe nombre de campo y valor.

Siempre actualiza `last_update`.

## Comportamiento

1. Si la busqueda devuelve mas de un lead (ej. dos "Juan"), lista los matches y pregunta cual.
2. Si no encuentra, avisa y pregunta si quiere agregarlo (delegar a `add-lead`).
3. Si la accion no aplica al estado actual (ej. marcar comprado uno ya perdido), avisa y pide confirmacion.
4. Confirma en una linea: lead_id + accion ejecutada.

## Errores

- Nunca inventar datos. Si falta `monto_venta_ars` para marcar comprado, lo pide.
- Si la fecha viene en formato relativo ("ayer", "el sabado"), resolver a fecha absoluta y confirmar antes de escribir.
