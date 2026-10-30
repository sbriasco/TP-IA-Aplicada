# Data Model: Chat analítico ampliado

No agrega tablas. Reutiliza sesiones, trabajos, métricas, funnel, patrones, posible compra y el documento en memoria de comparación (013).

## ChatRequest (entrada HTTP)

| Campo | Tipo | Regla |
|---|---|---|
| `question` | string | pregunta del analista; no vacía |
| `session_id` | UUID | sesión abierta del panel |
| `shop_id` | UUID \| null / omitido | zona/local elegido; vacío si no hay selección |

Sin historial de turnos en el body (US3 diferido).

## ChatFigure (cifra que respalda)

| Campo | Tipo | Regla |
|---|---|---|
| `code` | string | del catálogo cerrado |
| `label` | string | rótulo de producto |
| `availability` | `available` \| `unavailable` | |
| `value` | number \| null | null iff unavailable |
| `unavailable_reason` | string \| null | |
| `estimation` | boolean | true si tráfico / grupos / posible compra / atención u otro rótulo de estimación |

## SessionAnalyticsBundle (payload tool de una sesión)

Documento interno (no necesariamente expuesto 1:1 en HTTP) que la tool de sesión arma para el modelo:

| Familia | Códigos | Condición |
|---|---|---|
| shop_metrics | `traffic_total`, `entries`, `exits`, `store_pass`, `entry_rate`, `visible_occupancy`, `dwell_*` | zona resuelta; incomplete → bundle unavailable |
| peak | `peak_track_count` (+ `start_seconds`) | igual |
| funnel | etapa de entradas vinculadas ya expuesta por el producto | opcional |
| visit_patterns | `group_count` | opcional |
| possible_purchase | `visit_count` | opcional; siempre estimación |

Alcance: **toda la sesión**. Webcam / incomplete → no se entrega el catálogo como resultado final.

## ContrastToolRequest (args de tool)

| Campo | Tipo | Regla |
|---|---|---|
| `session_ids` | lista UUID | resueltos por backend (abierta + nombres / última); ≥2 elegibles |
| `zone_name` | string | nombre visible; obligatorio para métricas de zona |
| `axis` | enum | `session` \| `day` \| `time_of_day` \| `zone` |

## ContrastSnapshot

Copia de solo lectura del resultado de comparación (columnas, figures, insights) tal como lo produce 013. El chat cita números solo desde aquí cuando la pregunta es de contraste.

## ChatAnswer (salida)

| Campo | Tipo | Regla |
|---|---|---|
| `status` | enum | `answered` \| `refused` \| `needs_clarification` \| `unavailable` \| `error` |
| `message` | string | texto al usuario |
| `session_id` | UUID \| null | sesión usada (si aplica) |
| `shop_id` / nombre zona | según contrato 008 ampliado | |
| `scope` | `whole_session` \| `comparison` | comparación cuando hubo contraste |
| `figures` | lista ChatFigure | vacía en refused/error/clarification según reglas |
| `comparison` | object \| null | resumen opcional (axis, column labels, insight codes) sin secretos |

**Reglas**:

- Todo número en `message` MUST aparecer en `figures` o en celdas del contraste consultado de esa pregunta.
- Cero `available` es cero real; `unavailable` ≠ 0.
- Cambio de `session_id`/`shop_id` en el panel limpia UI local; no hay estado de cifras en servidor entre preguntas.
