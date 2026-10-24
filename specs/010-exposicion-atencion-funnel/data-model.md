# Data Model: Exposición, detención, atención estimada y funnel comercial

Extiende [specs/006](../006-eventos-metricas/data-model.md). No se reescribe `shop_metrics`, `traffic_buckets`, `analysis_measures` ni `line_crossings`.

La vidriera sigue siendo `zone_role=window`. El editor la llama vidriera; el hecho no usa otra palabra.

## scene_events

Se agrega un valor al enum `scene_event_kind`: `showcase_stop`.

| Campo | Regla nueva |
|---|---|
| `kind=showcase_stop` | Detención frente a la vidriera. Una fila por estadía cerrada que dura al menos 3 segundos de video. |
| `zone_role` | `window`. Obligatorio en este `kind`. |
| `duration_seconds` | Obligatorio, `>= 3`. Segundos de video, no de procesamiento. |
| `frame_index`, `video_timestamp_seconds` | Fotograma e instante de la salida de la vidriera. |
| `source_crossing_id` | Null. |

Reglas que no cambian:

- `dwell` sigue solo con `zone_role=front`. Interior y vidriera no generan permanencia ni ocupación.
- `zone_enter` y `zone_exit` de `window` se siguen insertando como hasta ahora, también si hay varias por oscilación. Esta feature no las borra.
- Perder el identificador dentro de la vidriera, o terminar el video con el pie adentro, no inserta `showcase_stop`.
- Una estadía de vidriera de menos de 3 segundos no inserta `showcase_stop`.
- Se insertan en la misma transacción que pasa el trabajo a `completed`. Un trabajo `failed`, `cancelled` o de webcam no las deja consultables como funnel.

El check de duración pasa a exigir `duration_seconds` en `dwell` y en `showcase_stop`, y a prohibirlo en el resto. El check de rol exige `window` en `showcase_stop` y sigue exigiendo `front` en `dwell`.

## shop_funnels

Una fila por local del trabajo completado que no es webcam.

| Campo | Tipo | Regla |
|---|---|---|
| `job_id`, `session_id`, `shop_id` | UUID | único el par trabajo + local |
| `stop_threshold_seconds` | decimal | `3` |
| `attention_threshold_seconds` | decimal | `8` |
| `excluded_window_only` | integer ≥ 0 | identificadores con entrada a `window` y sin entrada a `front` |
| `precision_uncommitted` | boolean | `true` en esta feature |

## shop_funnel_stages

Cinco filas por cada `shop_funnels`.

| Campo | Tipo | Regla |
|---|---|---|
| `stage` | enum | `observed_pass` \| `exposure` \| `stop` \| `attention` \| `linked_entry` |
| `count` | integer nullable | null si no disponible; si no, ≥ 0 |
| `availability` | enum | `available` \| `unavailable` |
| `label` | enum | `attention_estimate` solo en `attention` cuando está disponible; `none` en el resto |
| `unavailable_reason` | string nullable | `no_showcase` |

Único `(job_id, shop_id, stage)`.

Con vidriera, las cinco están disponibles y cumplen `attention ≤ stop ≤ exposure ≤ observed_pass` y `linked_entry ≤ attention`. Sin vidriera, `observed_pass` sigue disponible y las otras cuatro llevan `no_showcase` y `count` null.

Definiciones, siempre por `track_id` distinto de ese local:

- `observed_pass`: al menos un `zone_enter` de `front`. Incluye a quienes tienen `store_enter`. No es el código `store_pass` de `shop_metrics`.
- `exposure`: paso observado y al menos un `zone_enter` de `window`.
- `stop`: exposición y al menos un `showcase_stop`.
- `attention`: detención y al menos un `showcase_stop` con duración ≥ 8.
- `linked_entry`: atención y un `store_enter` del mismo local con instante posterior al inicio de la atención. El inicio es el instante de la detención menos su duración. Si hay varias detenciones de 8 segundos o más, se usa la de inicio más temprano.

## shop_funnel_rates

Cuatro filas por cada `shop_funnels`.

| Campo | Tipo | Regla |
|---|---|---|
| `code` | enum | `observed_pass_to_exposure` \| `exposure_to_stop` \| `stop_to_attention` \| `attention_to_linked_entry` |
| `value` | decimal nullable | etapa posterior / etapa anterior |
| `availability` | enum | `available` \| `unavailable` |
| `unavailable_reason` | string nullable | `no_previous_stage` o `no_showcase` |

Único `(job_id, shop_id, code)`. Ningún código es `entry_rate`. Si la etapa anterior vale 0 o no está disponible, `value` es null.

## Consulta

- Métricas y hechos: sin cambio de forma. El funnel no viaja en ese cuerpo.
- Funnel: solo si el trabajo de esa sesión está `completed`, `result_complete=true` y el origen no es `webcam`.
- No acepta tramo. El tramo sigue filtrando `GET /sessions/{id}/events`.
- Dos sesiones no comparten filas.
