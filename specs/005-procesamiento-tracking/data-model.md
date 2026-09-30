# Data Model: Procesamiento y seguimiento con vista en vivo

Extiende [specs/002](../002-entorno-arquitectura-base/data-model.md) y [specs/004](../004-configuracion-escenas/data-model.md). La traza sintética (`synthetic_frames`, `observations`, `events`) no se usa para el video real.

## ProcessingJob (extendida)

| Campo | Tipo | Regla |
|---|---|---|
| `status` | enum + `cancelled` | `pending` \| `processing` \| `completed` \| `failed` \| `cancelled` |
| `scene_version_id` | UUID | ya obligatorio para `video_analysis`; no cambia |
| `frames_analyzed` | integer nullable | fotogramas de video ya recorridos; 0 al pasar a `processing` |
| `frames_total` | integer nullable | conteo registrado del video; obligatorio en `video_analysis` |
| `analyzed_video_timestamp_seconds` | decimal nullable | instante del último fotograma recorrido |
| `result_complete` | boolean | `true` solo en `completed` |
| `detector_name` | string nullable | `yolov8n` o `fake` |
| `detector_version` | string nullable | versión del paquete o `fake` |
| `tracker_name` | string nullable | `bytetrack` o `fake` |
| `tracker_version` | string nullable | versión o archivo de configuración |
| `trajectory_relative_path` | string nullable | ruta relativa a `FLOWSIGHT_VIDEOS_DIR`; sin ruta absoluta en la API |

```text
pending -> processing -> completed
                      -> failed
                      -> cancelled
pending -> cancelled
```

No hay salida desde `completed`, `failed` ni `cancelled`. Al arrancar, un `processing` encontrado pasa a `failed` con `worker_interrupted` y `result_complete=false`. Cancelar no borra medidas ni la muestra ya escrita.

## AnalysisMeasure (nueva, `analysis_measures`)

Una fila por local y por medida del trabajo.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `job_id` | UUID | FK a `processing_jobs` |
| `session_id` | UUID | misma sesión que el trabajo |
| `shop_id` | UUID | identidad estable del local en la versión usada |
| `code` | enum | `entries` \| `exits` \| `visible_occupancy` |
| `value` | integer nullable | no negativo; nulo solo si `availability=unavailable` |
| `availability` | enum | `available` \| `unavailable` |
| `partial` | boolean | `true` mientras el trabajo no está `completed` |
| `video_timestamp_seconds` | decimal | instante de video al que corresponde el valor |

UNIQUE `(job_id, shop_id, code)`.

Al completar, las mismas filas pasan a `partial=false` y son los números oficiales de la sesión para ese trabajo. No se inserta una segunda fila «final». Una feature posterior los lee y no los recalcula. Un trabajo cancelado o fallido las deja en `partial=true`.

Definiciones:

- `entries` / `exits`: cruces confirmados del identificador, después de descartar la oscilación de 10 fotogramas. Un cambio de identificador no suma.
- `visible_occupancy`: identificadores distintos con el pie dentro de la zona frontal en el último fotograma analizado. No usa la zona interior.

## LineCrossing (nueva, `line_crossings`)

Hechos confirmados u oscilaciones, no una fila por fotograma.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `job_id` | UUID | FK |
| `session_id` | UUID | misma sesión |
| `shop_id` | UUID | local de la línea |
| `track_id` | integer | temporal; solo significa algo junto con la sesión |
| `frame_index` | integer | no negativo |
| `video_timestamp_seconds` | decimal | del fotograma |
| `direction` | enum | `entry` \| `exit` |
| `disposition` | enum | `confirmed` \| `oscillation` |
| `foot_x` | decimal | normalizado 0–1, centro inferior del recuadro |
| `foot_y` | decimal | normalizado 0–1 |

Solo `disposition=confirmed` entra en `entries` o `exits`. Índice `(session_id, shop_id, track_id)`.

## TrajectorySample (archivo, no tabla)

JSONL en `{FLOWSIGHT_VIDEOS_DIR}/{trajectory_relative_path}`. Una línea de encabezado y luego una línea cada 5 fotogramas por identificador presente:

- `session_id`, `job_id`, `frame_index`, `video_timestamp_seconds`
- `track_id`, `bbox` normalizado, `foot` normalizado
- `detector_name`, `detector_version`, `tracker_name`, `tracker_version` en el encabezado

La API devuelve la ruta relativa y si el archivo está en este equipo. No devuelve la ruta absoluta.

## Vista en vivo

No se persiste. El mensaje `schema_version` `2` lleva el JPEG del fotograma, el avance y una copia de las medidas parciales. El contrato está en [contracts/preview-websocket.md](./contracts/preview-websocket.md).

## Integridad

- Un `video_analysis` sigue exigiendo versión de escena de la misma cámara y proporción dentro del 1 % (specs/004).
- Medidas y cruces referencian la misma sesión que el trabajo. Una prueba con dos sesiones que reutilizan `track_id` no puede leer el cruce de la otra.
- `result_complete=true` solo si `status=completed` y todas las medidas de ese trabajo tienen `partial=false`.
