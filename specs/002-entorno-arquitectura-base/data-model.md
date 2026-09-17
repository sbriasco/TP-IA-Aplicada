# Data Model: Entorno local reproducible y arquitectura base

## Reglas comunes

- Identificadores persistidos UUID; momentos operativos en UTC con zona.
- `video_timestamp_seconds` es decimal, no negativo y distinto del tiempo de procesamiento.
- Las relaciones incluyen sesión; ningún `track_id` es global.
- Las migraciones crean el esquema. Los fixtures se cargan de forma idempotente.

## Session

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `name` | string | 1–120 caracteres |
| `camera_id` | string | puede repetirse entre sesiones |
| `source_kind` | enum | `synthetic` |
| `created_at` | datetime UTC | obligatorio |

Tiene muchos trabajos, frames, observaciones y eventos.

## ProcessingJob

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `session_id` | UUID | FK a Session |
| `kind` | enum | `synthetic_base_flow` |
| `status` | enum | `pending`, `processing`, `completed`, `failed` |
| `created_at` | datetime UTC | obligatorio |
| `started_at` | datetime UTC nullable | obligatorio desde `processing` |
| `finished_at` | datetime UTC nullable | obligatorio en estado terminal |
| `claimed_by` | string nullable | identificador diagnóstico del worker |
| `failure_code` | string nullable | código estable sin secretos |
| `failure_message` | string nullable | explicación segura |
| `processing_duration_ms` | integer nullable | no negativo; tiempo operativo |

```text
pending -> processing -> completed
                      -> failed
```

No hay transición automática desde `failed`. Al arrancar, el worker pasa todo trabajo encontrado en `processing` a `failed` con `failure_code=worker_interrupted`.

## JobStatusTransition

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `job_id` | UUID | FK obligatoria |
| `from_status` | enum nullable | nulo solo en creación |
| `to_status` | enum | estado válido |
| `occurred_at` | datetime UTC | obligatorio |
| `reason_code` | string nullable | código seguro |

El orden por `occurred_at` debe ser compatible con el estado actual.

## SyntheticFrame

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `session_id` | UUID | FK obligatoria |
| `job_id` | UUID | FK obligatoria |
| `camera_id` | string | coincide con la sesión |
| `frame_index` | integer | no negativo |
| `video_timestamp_seconds` | decimal | no negativo y monótono por trabajo |

Único: `(session_id, job_id, camera_id, frame_index)`.

## Observation

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `session_id` | UUID | FK obligatoria |
| `job_id` | UUID | FK obligatoria |
| `frame_id` | UUID | FK obligatoria |
| `camera_id` | string | contexto obligatorio |
| `track_id` | integer | temporal; repetible en otra sesión |
| `kind` | string | `synthetic_person` |

Índice: `(session_id, camera_id, track_id)`. Ninguna consulta resuelve una observación solo por `track_id`.

## Event

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | clave primaria |
| `session_id` | UUID | FK obligatoria |
| `job_id` | UUID | FK obligatoria |
| `frame_id` | UUID | FK obligatoria |
| `observation_id` | UUID nullable | FK si deriva de observación |
| `camera_id` | string | contexto obligatorio |
| `video_timestamp_seconds` | decimal | coincide con el frame |
| `event_type` | string | tipo sintético documentado |

## PreviewUpdate

Mensaje efímero no persistido: `schema_version`, `session_id`, `job_id`, `frame_index`, `video_timestamp_seconds`, `progress_percent`, `image_media_type` e `image_base64`. Cada conexión conserva cero o uno pendiente. No confirma persistencia ni calcula métricas.

## EnvironmentEvidence

Artefacto JSON fuera de la base: `recorded_at`, sistema operativo, versiones de Python/Node/PostgreSQL, `execution_mode` (`cpu` o `gpu`), GPU detectada opcional, resultado (`passed`, `failed`, `not_evaluated`), checks y limitaciones. El informe completo es local y se ignora en Git. Un resumen versionable elimina nombre del equipo, usuario, rutas absolutas, direcciones de red y secretos; conserva versiones, modo, resultado, medianas y limitaciones generales.

## Integridad

La aplicación valida que sesión, trabajo, frame y cámara pertenezcan al mismo árbol. La base refuerza relaciones con FKs y restricciones compuestas. Las pruebas intentan insertar referencias cruzadas entre dos sesiones y deben fallar.
