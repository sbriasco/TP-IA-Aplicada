# Data Model: Carga, configuración y editor visual de escenas

Extiende [el data-model de specs/002](../002-entorno-arquitectura-base/data-model.md) con la migración Alembic `0002_scene_configuration`. Siguen valiendo las reglas comunes de specs/002: UUIDs, momentos operativos en UTC, `video_timestamp_seconds` decimal y FK compuestas que incluyen sesión y cámara. Las decisiones de diseño están en [research.md](./research.md).

```text
Camera 1───* Session 1───0..1 VideoSource
   │            │  1───0..1 ReferenceFrame
   │            └──* ProcessingJob ──0..1→ SceneVersion
   ├──* Shop (identidad estable)
   └──* SceneVersion 1───* SceneVersionShop *───1 Shop
                                │ 1───1..3 SceneZone
                                └ 1───1  SceneEntryLine
```

## Normalización de nombres

`name_key = casefold(strip(name))`. Se usa para las cámaras (FR-002) y para los nombres de local dentro de una versión (FR-020). La migración `0002` la calcula en Python con una copia fija de la misma función, no en SQL: `lower(btrim())` no es equivalente (`casefold` convierte `ß` en `ss`; `strip` también quita tabs y saltos de línea).

## `camera_id` y `registered_camera_id`

- En `sessions`, en `processing_jobs` y en la API de sesiones y trabajos, `camera_id` es el **texto** heredado de specs/002 (clave de trazabilidad de sus FK compuestas) y `registered_camera_id` es el **UUID** de `cameras`. Los parámetros que reciben el UUID se llaman `registered_camera_id`. En las respuestas, el UUID se lee en `camera.id`.
- En las tablas y rutas de escena (`shops`, `scene_versions`, `scene_version_shops`, `/cameras/{camera_id}/…`, `SceneVersionSummary`), `camera_id` es el UUID de `cameras`: ahí no existe el texto de specs/002.

## Camera (nueva, `cameras`)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | PK |
| `name` | string(120) | 1–120 caracteres tras `strip`; se muestra tal cual |
| `name_key` | string(120) | UNIQUE; `casefold(strip(name))` |
| `created_at` | datetime UTC | obligatorio |

No se renombra ni se borra en el MVP. Crear un nombre con `name_key` existente → `camera_exists` (409) con el `id` existente.

## Session (extendida, `sessions`)

| Campo | Cambio | Regla |
|---|---|---|
| `source_kind` | enum + `video_file` | `synthetic` \| `video_file` |
| `registered_camera_id` | **nuevo**, UUID FK → `cameras.id`, NOT NULL | cámara dueña; no cambia después de creada |
| `camera_id` | sin cambios (string) | clave de trazabilidad de las FK compuestas de specs/002; en sesiones de video = `cameras.name` al registrar |

Nueva restricción: UNIQUE `(id, registered_camera_id)` como destino de FK compuestas.

**Migración de datos**: se agrupan las sesiones existentes por `name_key` de su `camera_id`, calculado en Python y cada `camera_id` original distinto genera una cámara. Si hay choque, la primera cámara del grupo (por `min(created_at)`) conserva el nombre y las demás reciben el sufijo ` (n)`. Se registra un `warning` por conflicto y no se fusionan sesiones ([R8](./research.md#r8-cámaras-registradas-y-migración-de-sesiones-sintéticas)).

## VideoSource (nueva, `video_sources`)

Uno por sesión `video_file`. No existe para las sintéticas.

| Campo | Tipo | Regla |
|---|---|---|
| `session_id` | UUID | PK y FK → `sessions.id` |
| `relative_path` | string(255) | generada por el servidor: `<session_id><ext>`; relativa a `FLOWSIGHT_VIDEOS_DIR`, sin `..` ni separadores iniciales |
| `original_filename` | string(255) | solo el nombre base enviado por el navegador; se muestra, nunca se usa como ruta |
| `size_bytes` | bigint | > 0 |
| `sha256` | char(64) | hex minúscula del contenido completo |
| `origin_machine_id` | string(40) | `FLOWSIGHT_MACHINE_ID` del equipo que registró |
| `width`, `height` | integer | > 0; del frame de referencia decodificado |
| `fps` | numeric(9,4) | > 0 |
| `fps_is_estimated` | boolean | `true` si no vino de un encabezado confiable |
| `frame_count` | integer | > 0; contado recorriendo el video |
| `declared_frame_count` | integer, nullable | > 0 o `NULL`; `CAP_PROP_FRAME_COUNT` del encabezado si es finito y > 0. Siempre `NULL` en `.mpg`/`.mpeg` (encabezado no confiable) y en las filas anteriores a la migración `0003`. Solo se usa para la advertencia de video incompleto |
| `duration_seconds` | numeric(12,6) | `frame_count / fps` |
| `registered_at` | datetime UTC | obligatorio |

Índice sobre `sha256`: se usa para avisar que el mismo video ya está registrado en otra sesión (caso borde "mismo hash dos veces").

**Video incompleto** (T051): `appears_incomplete` se calcula al responder y no se persiste. Es `true` si `declared_frame_count - frame_count > max(5, ceil(0.02 * declared_frame_count))` y `false` si `declared_frame_count` es `NULL`. Lo calcula una única función, `flowsight.video.probe.appears_incomplete`. Es solo una advertencia: el registro acepta el video igual ([R3](./research.md#r3-sondeo-del-video-fps-frames-duración-y-frame-de-referencia)).

**Disponibilidad**: se calcula al consultar y no se persiste (FR-009). Los valores posibles son `available`, `missing`, `mismatch` y `not_configured`.

## ReferenceFrame (nueva, `reference_frames`)

| Campo | Tipo | Regla |
|---|---|---|
| `session_id` | UUID | PK y FK → `sessions.id` |
| `frame_index` | integer | ≥ 0; primer frame decodificable |
| `video_timestamp_seconds` | numeric(12,6) | ≥ 0; `frame_index / fps` |
| `width`, `height` | integer | > 0; iguales a `video_sources` |
| `media_type` | string(40) | `image/jpeg` |
| `image` | bytea | JPEG, calidad 90, resolución original |

## Shop (nueva, `shops`)

Identidad estable de un local dentro de una cámara (FR-015).

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | PK |
| `camera_id` | UUID | FK → `cameras.id` |
| `created_at` | datetime UTC | obligatorio |

UNIQUE `(id, camera_id)`. No tiene nombre propio: el nombre vive en cada versión, así que renombrar no cambia la identidad. No se borra.

## SceneVersion (nueva, `scene_versions`, inmutable)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | PK |
| `camera_id` | UUID | FK → `cameras.id` |
| `version_number` | integer | ≥ 1; UNIQUE `(camera_id, version_number)`; `max + 1` bajo `FOR UPDATE` de la cámara |
| `reference_session_id` | UUID | FK compuesta `(reference_session_id, camera_id)` → `sessions(id, registered_camera_id)`: la sesión debe ser de la misma cámara (FR-022) |
| `frame_width`, `frame_height` | integer | > 0; copiados de `reference_frames` de esa sesión (FR-018) |
| `created_by_machine_id` | string(40) nullable | equipo que guardó; trazabilidad con base compartida (CHK005) |
| `created_at` | datetime UTC | obligatorio |

UNIQUE `(id, camera_id)`. Solo pueden ser sesión de referencia las sesiones con `reference_frames`, es decir, las de video.

## SceneVersionShop (nueva, `scene_version_shops`, inmutable)

Local tal como aparece en una versión.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | PK |
| `scene_version_id` | UUID | FK compuesta `(scene_version_id, camera_id)` → `scene_versions(id, camera_id)` |
| `shop_id` | UUID | FK compuesta `(shop_id, camera_id)` → `shops(id, camera_id)` |
| `camera_id` | UUID | contexto obligatorio del aislamiento (FR-029) |
| `position` | integer | ≥ 0; orden de la request; se usa para `shop_index` en errores |
| `name` | string(120) | 1–120 caracteres tras `strip` |
| `name_key` | string(120) | UNIQUE `(scene_version_id, name_key)` |

UNIQUE `(scene_version_id, shop_id)`: un local aparece a lo sumo una vez por versión. Un local que no figura en una versión nueva conserva sus filas en las versiones anteriores.

## SceneZone (nueva, `scene_zones`, inmutable)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | UUID | PK |
| `version_shop_id` | UUID | FK → `scene_version_shops.id` |
| `role` | enum `zone_role` | `interior` \| `front` \| `showcase` |
| `polygon` | JSONB | lista de 3 a 64 pares `[x, y]` normalizados en [0, 1], 6 decimales |

UNIQUE `(version_shop_id, role)`. `front` es obligatoria por local (se valida en la API, FR-016); `interior` y `showcase`, opcionales.

## SceneEntryLine (nueva, `scene_entry_lines`, inmutable)

| Campo | Tipo | Regla |
|---|---|---|
| `version_shop_id` | UUID | PK y FK → `scene_version_shops.id` (exactamente una por local) |
| `start_x`, `start_y`, `end_x`, `end_y` | double | en [0, 1], 6 decimales |
| `entry_direction` | enum `entry_direction` | `a_to_b` \| `b_to_a`; el opuesto es salida |

El lado A es el semiplano donde `cross(end − start, p − start) > 0` en coordenadas de imagen (y hacia abajo), es decir, a la derecha del vector inicio→fin. El lado B es donde `cross < 0` ([R11](./research.md#r11-geometría-coordenadas-tolerancias-y-convención-ab)).

## ProcessingJob (extendida, `processing_jobs`)

| Campo | Cambio | Regla |
|---|---|---|
| `kind` | enum + `video_analysis` | `synthetic_base_flow` \| `video_analysis` |
| `scene_version_id` | **nuevo**, UUID nullable | versión elegida; no cambia (FR-027) |
| `registered_camera_id` | **nuevo**, UUID nullable | contexto para las FK compuestas |

- **FK compuestas**: `(session_id, registered_camera_id)` → `sessions(id, registered_camera_id)` y `(scene_version_id, registered_camera_id)` → `scene_versions(id, camera_id)` (FR-026, FR-029).
- **CHECK**: `(kind = 'video_analysis') = (scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)`.

La máquina de estados de specs/002 no cambia. El worker actual solo reclama `synthetic_base_flow`; `video_analysis` queda en `pending` hasta #56.

## Inmutabilidad

Un trigger `flowsight_forbid_mutation()` `BEFORE UPDATE OR DELETE FOR EACH ROW` en `scene_versions`, `scene_version_shops`, `scene_zones` y `scene_entry_lines` lanza `raise exception 'scene configuration is immutable'`. La API no expone rutas de modificación ni de borrado (FR-023). La prueba de SC-006 compara el JSON canónico de una versión antes y después de guardar versiones nuevas e intenta un `UPDATE` directo, que debe fallar.

## Validación al guardar una versión

Se ejecuta en `flowsight/scene/validation.py` y rechaza la versión entera, devolviendo todos los errores (FR-021):

| Regla (`rule`) | Elemento | Condición de rechazo |
|---|---|---|
| `no_shops` | versión | cero locales |
| `duplicate_shop_name` | local | `name_key` repetido en la versión |
| `duplicate_shop_id` | local | mismo `shop_id` dos veces |
| `shop_other_camera` | local | `shop_id` inexistente o de otra cámara |
| `missing_front_zone` | local | sin zona `front` |
| `missing_entry_line` | local | sin línea |
| `out_of_range` | zona/línea | alguna coordenada fuera de [0, 1] |
| `too_few_vertices` / `too_many_vertices` | zona | < 3 / > 64 |
| `vertices_too_close` | zona | vértices consecutivos, incluido cierre, a ≤ 2 px |
| `self_intersection` | zona | aristas no adyacentes que se cruzan o se tocan |
| `area_too_small` | zona | área < 100 px² |
| `line_too_short` | línea | longitud < 10 px |
| `reference_session_other_camera` | versión | sesión de referencia de otra cámara |
| `reference_frame_missing` | versión | la sesión no tiene frame de referencia |

Advertencias (no bloquean ni se persisten): `line_not_touching_zones`, `zones_overlap` y `newer_version_exists`.
