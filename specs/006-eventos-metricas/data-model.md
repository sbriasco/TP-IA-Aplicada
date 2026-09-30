# Data Model: Eventos espaciales, métricas y persistencia

Extiende [specs/005](../005-procesamiento-tracking/data-model.md). No se reescribe `analysis_measures` ni `line_crossings`.

## scene_events

Un hecho de negocio. No hay una fila por fotograma.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | |
| `job_id`, `session_id` | UUID | el trabajo y la sesión; FK compuesta como en specs/005 |
| `shop_id` | UUID | local de la versión de escena de ese trabajo |
| `track_id` | integer | temporal, de esa sesión y cámara |
| `kind` | enum | `zone_enter` \| `zone_exit` \| `store_pass` \| `store_enter` \| `store_exit` \| `dwell` |
| `zone_role` | enum nullable | `front` \| `interior` \| `window`; solo en hechos de zona y en `dwell` (`front`) |
| `frame_index` | integer ≥ 0 | fotograma en que se cierra el hecho |
| `video_timestamp_seconds` | decimal ≥ 0 | instante de ese fotograma |
| `duration_seconds` | decimal nullable | solo `dwell`; segundos de video; null en el resto |
| `source_crossing_id` | UUID nullable | `store_enter` y `store_exit` apuntan al `line_crossings` confirmado; el resto null |

Índice `(session_id, shop_id, video_timestamp_seconds)`.

Reglas:

- `store_enter` / `store_exit` solo desde un cruce `confirmed`. Un cruce `oscillation` no genera fila.
- `dwell` solo con `zone_role=front` y `duration_seconds` no null. Desaparecer el identificador no inserta `dwell` ni `store_exit`.
- `store_pass` es un identificador con pie en la zona frontal y sin `store_enter` de ese local.
- Interior y vidriera pueden tener `zone_enter` / `zone_exit`. No generan `dwell` ni ocupación.
- Se insertan en la misma transacción que pasa el trabajo a `completed`. Un trabajo `failed` o `cancelled` no las deja consultables como resultado completo.

## shop_metrics

Una fila por medida y local del trabajo completado.

| Campo | Tipo | Regla |
|---|---|---|
| `job_id`, `session_id`, `shop_id` | UUID | único junto con `code` |
| `code` | enum | `traffic_total` \| `store_pass` \| `entries` \| `exits` \| `entry_rate` \| `dwell_mean_seconds` \| `dwell_median_seconds` \| `visible_occupancy` |
| `value` | decimal nullable | null si no disponible |
| `availability` | enum | `available` \| `unavailable` |
| `label` | enum | `visit_estimate` en tráfico; `visible` en ocupación; `observable` en las dos permanencias; `none` en el resto |
| `unavailable_reason` | string nullable | `no_passes` \| `no_closed_dwells` \| `scene_element_missing` \| `metrics_not_generated` |

`entries`, `exits` y `visible_occupancy` copian el valor de `analysis_measures` del mismo trabajo y local. No se actualiza la fila oficial.

## traffic_buckets

| Campo | Tipo | Regla |
|---|---|---|
| `job_id`, `session_id`, `shop_id` | UUID | |
| `bucket_index` | integer ≥ 0 | 0 es el primer minuto de video |
| `start_seconds` | decimal | `bucket_index * 60` |
| `track_count` | integer ≥ 0 | identificadores cuyo primer pie en la zona frontal cae en `[start, start+60)` |

La suma de `track_count` es `traffic_total`. El horario pico es la fila de mayor `track_count` y, si empatan, el menor `bucket_index`. No es una hora de reloj si el video no tiene fecha.

## Consulta

- Listado: `sessions` existente. No incluye métricas.
- Métricas y hechos: solo si el trabajo de esa sesión está `completed` y `result_complete=true`.
- Hechos filtrados por `shop_id` opcional y por instante de video `from_seconds` ≤ t < `to_seconds`.
