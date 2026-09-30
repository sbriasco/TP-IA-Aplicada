# Data model: Dashboard e historial

No hay tablas ni migración. Esta feature lee filas que specs/002, specs/004, specs/005 y specs/006 ya guardan.

## Fila de historial

Una por sesión que tiene al menos un análisis. Sale de `GET /processed-sessions`. No se persiste.

| Campo | Origen | Regla |
|---|---|---|
| `session_id`, `name` | `sessions` | |
| `video_filename` | `video_sources.original_filename` | Vacío si la sesión no es de video |
| `video_availability` | la disponibilidad que ya calcula el detalle de sesión | `available`, `missing`, `mismatch` o ausente |
| `job_id` | el `processing_jobs` más reciente de esa sesión, por `created_at` | |
| `status` | `processing_jobs.status` | `pending`, `processing`, `completed`, `failed`, `cancelled` |
| `finished_at` | `processing_jobs.finished_at` | Es la fecha de procesamiento. Vacía si todavía no terminó |
| `failure_code`, `failure_message` | el análisis | Obligatorios en pantalla si el estado es `failed` o `cancelled` |
| `scene_version_id`, `version_number` | la versión guardada en ese análisis | No es la última versión de la cámara |
| `result_complete` | `processing_jobs.result_complete` | Solo un `completed` puede tenerlo en true |

Una sesión sin análisis no aparece. Dos sesiones no comparten fila.

## Resultado que se abre

No es una entidad nueva. Depende del análisis más reciente:

| Estado | Qué se lee | Qué se muestra |
|---|---|---|
| `pending` o `processing` | `GET /jobs/{id}/measures` | Solo entradas, salidas y ocupación visible, con `partial` |
| `completed` y `result_complete` | `GET /sessions/{id}/shops/{shop_id}/metrics` y los hechos | Los ocho indicadores de toda la sesión y el flujo |
| `failed` o `cancelled` | la fila de historial | El motivo. Sin los ocho indicadores |
| Análisis anterior completo y el más reciente no | el más reciente | No se muestran las cifras del anterior como resultado final |

El local inicial es el primero de la versión de ese análisis, por `position`. El tramo inicial es todo el video.

## Tramo

No se guarda. El navegador conserva `from_seconds` y `to_seconds`.

- Un minuto del flujo se muestra si `[start_seconds, start_seconds + 60)` se solapa con `[from_seconds, to_seconds)`. Se muestra entero.
- Los hechos usan el intervalo medio abierto que specs/006 ya aplica: `from_seconds` inclusive, `to_seconds` exclusive.
- Los ocho indicadores no cambian con el tramo.

## Mapa de calor

No se persiste. Cada punto es un `foot` ya escrito en el JSONL de specs/005. Si el archivo no está, la muestra queda no disponible y el frame de referencia igual se muestra.
