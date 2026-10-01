# Data model: Chat analítico mínimo

No hay tablas ni migración. El chat lee filas que specs/006 ya guarda y el historial que specs/007 ya arma. El hilo no se persiste.

## Lectura de cifra

No se guarda. Es el resultado de una de las cinco lecturas para una sesión y un local.

| Campo | Origen | Regla |
|---|---|---|
| `code` | `shop_metrics.code` o el pico | Solo `traffic_total`, `entries`, `visible_occupancy`, `dwell_mean_seconds`, `dwell_median_seconds` o `peak` |
| `label` | el rótulo ya guardado | `visit_estimate`, `visible`, `observable`. El pico no lleva rótulo de reloj |
| `availability` | `shop_metrics.availability` | `available` o `unavailable`. No disponible no se reemplaza por cero |
| `value` | `shop_metrics.value` | Vacío si no está disponible |
| `unavailable_reason` | `shop_metrics.unavailable_reason` | Se cita si ya existía |
| `start_seconds`, `track_count`, `bucket_index` | el `traffic_buckets` del pico ya guardado | Solo en el pico. Se citan como tramo del video |

La pareja de permanencia viaja junta. El alcance de las cinco es toda la sesión. Un tramo pedido en la pregunta no cambia estos campos.

Salidas, pasos, tasa y los minutos que no son el pico no forman parte de esta lectura.

## Referencia de sesión

No se guarda. Se resuelve al recibir la pregunta.

| Caso | Qué se usa |
|---|---|
| La pregunta no nombra otra sesión | La sesión abierta en resultados |
| «La última» | La sesión procesada con mayor `finished_at`. Empate: el `job_id` mayor |
| Un nombre | La sesión procesada cuyo nombre coincide, sin distinguir mayúsculas |
| Más de una coincidencia | Ninguna. El estado queda `needs_clarification` |
| El análisis más reciente no tiene `result_complete` | Esa sesión igual, con estado `unavailable`. Sin las cinco cifras y sin las tres parciales |
| No hay sesiones procesadas | Ninguna. El mensaje lo dice y no inventa una |

El listado que puede consultar el modelo trae `session_id`, `name`, `finished_at` y `result_complete`. No trae métricas.

## Referencia de local

No se guarda.

| Caso | Qué se usa |
|---|---|
| Hay un local elegido en resultados y la pregunta no nombra otro | Ese local |
| La pregunta nombra un local de la escena de ese análisis | Ese, si el nombre coincide con uno solo |
| Hay varios y no hay uno elegido ni nombrado | Ninguno. El estado queda `needs_clarification` |

Los locales son los de la versión guardada en el análisis, no los de una versión posterior de la cámara.

## Respuesta de chat

No se guarda. La página la muestra y la descarta al cambiar de sesión.

| Campo | Regla |
|---|---|
| `status` | `answered`, `refused`, `needs_clarification`, `unavailable` o `error` |
| `message` | Lo que lee el usuario. En `error`, explica el fallo sin cifras y sin secretos |
| `session_id`, `shop_id`, `shop_name` | Los usados, o vacíos si no se llegó a elegir |
| `scope` | `whole_session` cuando hay cifras. Vacío si no |
| `figures` | Las lecturas que respaldan el texto. Vacías en rechazo, aclaración, análisis incompleto y error |
| `model_calls` | 0, 1 o 2. No es una cifra de la sesión y no se muestra como métrica |

Una respuesta `answered` nombra el local y deja explícito que las cifras son de toda la sesión. Todo número del mensaje tiene que estar en `figures`.
