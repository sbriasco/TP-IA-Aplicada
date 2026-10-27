# Data Model: Evaluación de posible compra

Extiende el cierre de un análisis de archivo. No se reescriben `scene_events`, `shop_metrics`, `shop_funnels`, `visit_pattern_reports` ni sus hijas, `analysis_measures`, `line_crossings` ni `trajectory.jsonl`.

## possible_purchase_reports

Una fila por trabajo de archivo completado. Un trabajo webcam no la tiene.

| Campo | Tipo | Regla |
|---|---|---|
| `job_id`, `session_id` | UUID | único `job_id` |
| `minimum_seconds` | decimal | `1` |
| `visit_count` | integer ≥ 0 | visitas distintas que cumplieron el umbral. Cero es disponible |
| `availability` | enum `available` | siempre `available` cuando la fila existe |
| `precision_uncommitted` | boolean | `true` |

## possible_purchase_members

Cada visita que contó una vez en ese informe.

| Campo | Tipo | Regla |
|---|---|---|
| `track_id` | integer | identificador temporal de esa sesión y esa cámara |

Único `(report_id, track_id)`. La cantidad de filas coincide con `visit_count`. Una visita que vuelve a mostrar la bolsa después de un corte no inserta una segunda fila.

## Observaciones en memoria (no persistidas)

Durante el análisis, el módulo puro conserva por `track_id` el tramo de solape exclusivo en curso. No se escribe un recuadro por fotograma. Al cerrar, solo pasan al informe las visitas cuyo tramo acumulado alcanzó 1 segundo de video.

Un recuadro de bolsa es `(x1, y1, x2, y2)` en píxeles del fotograma. Una visita aporta su `Detection.bbox`. Hay solape si el área de intersección es mayor que cero. El solape es exclusivo cuando exactamente una visita lo cumple para esa bolsa.

## Consulta

- Métricas, hechos, funnel, patrones y chat: sin cambio de forma.
- `GET /sessions/{session_id}/possible-purchases` lee esta fila y sus integrantes. No acepta tramo ni local.
- Webcam y análisis no completado: sin fila consultable. El `409` está en [contracts/openapi.yaml](./contracts/openapi.yaml).
