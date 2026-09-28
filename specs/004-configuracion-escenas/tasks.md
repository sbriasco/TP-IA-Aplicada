---

description: "Lista de tareas de la feature 004: carga, configuración y editor visual de escenas"
---

# Tasks: Carga, configuración y editor visual de escenas

**Input**: Documentos de diseño de `/specs/004-configuracion-escenas/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [contracts/video-registration.md](./contracts/video-registration.md), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #12 (Epic #1). US1 = #53, US2 = #54, US3 = #55. Cada tarea termina con la Task de Boards que la agrupa (#73–#82).

**Tests**: Se incluyen porque el plan los exige ("Testing" y "Verification Strategy") y la constitución pide pruebas de configuración, aislamiento por sesión y recorridos reales de interfaz. Dentro de cada historia, las pruebas se escriben primero y deben fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` a la que aporta (US1, US2, US3).
- Antes de instalar cualquier dependencia, presentar versiones y comandos y esperar aprobación (AGENTS.md). `opencv-python-headless==4.10.0.84` ya fue aprobada el 2026-09-26 ([R4](./research.md#r4-dependencia-nueva-del-backend)); igual se muestran los comandos antes de correrlos.
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno: se corrige la causa y se vuelve a correr `alembic upgrade head`.

---

## Phase 1: Setup

**Purpose**: Dependencia nueva y configuración opcional por equipo.

- [X] T001 Agregar `opencv-python-headless==4.10.0.84` (y el `numpy` que resuelva, fijado) a `backend/pyproject.toml` y regenerar `backend/requirements.lock` con el mismo procedimiento usado en specs/002; mostrar los comandos al usuario, reinstalar con `backend/.venv/bin/pip install -r backend/requirements.lock && backend/.venv/bin/pip install --no-deps -e backend` y confirmar que `python -c "import cv2; print(cv2.__version__)"` imprime `4.10.0`. No agregar `python-multipart` ([R1](./research.md#r1-transporte-del-video-desde-el-navegador)). · ADO #73
- [X] T002 [P] Extender `Settings` en `backend/src/flowsight/core/config.py` con dos campos **opcionales**: `videos_dir` (`FLOWSIGHT_VIDEOS_DIR`, ruta absoluta; `None` si falta) y `machine_id` (`FLOWSIGHT_MACHINE_ID`, patrón `^[a-z0-9][a-z0-9-]{2,39}$`; `None` si falta). La API y el worker DEBEN seguir arrancando sin ellas. Un `machine_id` presente pero inválido NO debe impedir el arranque: se expone como no configurado para que los endpoints de video respondan `machine_id_not_configured`. Agregar casos en `backend/tests/unit/test_config.py` (ausentes, válidas, `machine_id` inválido, ruta relativa rechazada, ningún mensaje repite el valor). Documentar ambas en `.env.example`, aclarando que `FLOWSIGHT_MACHINE_ID` no debe ser el nombre de la persona ni el usuario del sistema ([R6](./research.md#r6-identificador-del-equipo-y-carpeta-de-videos)). · ADO #73

**Checkpoint**: OpenCV instalado desde el lock; configuración existente del equipo sigue funcionando sin cambios en `.env`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0002`, modelos, cámaras registradas, clips de prueba y formato de errores compartido.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T003 [P] Crear `backend/src/flowsight/video/__init__.py` y `backend/src/flowsight/video/fixtures.py` con funciones puras que generen con `cv2.VideoWriter`, en un directorio recibido por parámetro, clips deterministas de 2 s: MJPG `.avi` y `mp4v` `.mp4`, en 1280×720 (16:9), 1920×1080 (16:9, otra resolución) y 640×480 (4:3), más un clip MPEG-1 `.mpg` (fourcc `PIM1`, 640×480, 2 s) porque MPEG es formato obligatorio y el caso de frames declarados poco confiables; si `VideoWriter` no abre el `.mpg` con el OpenCV del lock, la función lo informa (p. ej. `MpegUnavailable`) para que las pruebas que lo usan se salteen con motivo explícito, sin fallar; cada frame con contenido distinto (p. ej. número de frame dibujado) para que el JPEG de referencia no sea trivial. Exponer también un entrypoint CLI (`python -m flowsight.video.fixtures <dir> [--size WxH] [--codec mjpg|mp4v]`) que imprima la ruta generada, para que lo invoque `frontend/e2e/run-e2e.mjs` ([R14](./research.md#r14-video-de-prueba-sin-subir-videos-a-git)). Nunca escribir en el repo. · ADO #73
- [X] T050 Crear `backend/tests/conftest.py` con el helper `destructive_database_url()` para toda prueba que haga `downgrade`, `TRUNCATE` o inserte datos de prueba: usa `FLOWSIGHT_TEST_DATABASE_URL` si está definida; si no, acepta `FLOWSIGHT_DATABASE_URL` solo cuando el host es `localhost`, `127.0.0.1` o `::1`. Rechaza siempre hosts `*.postgres.database.azure.com`, aunque vengan en `FLOWSIGHT_TEST_DATABASE_URL`. En todos los rechazos, `pytest.fail` explica qué variable configurar sin repetir la URL ni la contraseña. Migrar a este helper `backend/tests/integration/test_migrations.py`, `backend/tests/contract/test_sessions_jobs_api.py`, `backend/tests/integration/test_worker_lifecycle.py` y `backend/tests/integration/test_session_isolation.py`, sin cambiar sus aserciones; T004, T012 y T025–T028 lo usan desde el inicio. Pruebas en `backend/tests/unit/test_database_guard.py`: local aceptado, Azure rechazado incluso como URL de test, host remoto sin `FLOWSIGHT_TEST_DATABASE_URL` rechazado, mensaje sin secretos. Documentar `FLOWSIGHT_TEST_DATABASE_URL` (comentada) en `.env.example`. CI no cambia: usa `127.0.0.1`. · ADO #73
- [X] T004 Escribir `backend/tests/integration/test_migration_0002.py` (PostgreSQL, mismo patrón `downgrade base` / `upgrade head` que `backend/tests/integration/test_migrations.py`), que primero aplique `0001`, inserte sesiones sintéticas con `camera_id` `Cam01`, `cam01 `, `Otra`, `Straße`, `STRASSE` y `\tTab01\n`, aplique `0002` y verifique: (a) se crean 6 cámaras; en cada choque (`Cam01`/`cam01 ` y `Straße`/`STRASSE`, que solo chocan con `casefold`) la de `min(created_at)` conserva el nombre y la otra recibe el sufijo ` (2)`; `\tTab01\n` recibe `name_key = "tab01"`; y `normalize_name_key` de T007 aplicado a cada nombre de cámara migrada da su `name_key` guardado; (b) ninguna sesión cambia su `camera_id` de texto ni se fusiona; (c) se emite un `warning` con los nombres del conflicto; (d) `source_kind` admite `video_file` y `job_kind` admite `video_analysis`; (e) el CHECK de `processing_jobs` rechaza `video_analysis` sin `scene_version_id`/`registered_camera_id` y `synthetic_base_flow` con ellos; (f) existe el trigger `flowsight_forbid_mutation` en las cuatro tablas de escena; (g) `upgrade head` es repetible y el `downgrade` de `0002` a `0001` funciona solo como fixture de test. · ADO #74
- [X] T005 Crear `backend/alembic/versions/0002_scene_configuration.py` según [data-model.md](./data-model.md) y [R8](./research.md#r8-cámaras-registradas-y-migración-de-sesiones-sintéticas)/[R9](./research.md#r9-enums-de-postgresql-y-migración-reversible-en-tests)/[R10](./research.md#r10-modelo-de-versiones-locales-con-identidad-estable-e-inmutabilidad): (1) dentro de `op.get_context().autocommit_block()`, `ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'video_file'` y `ALTER TYPE job_kind ADD VALUE IF NOT EXISTS 'video_analysis'`; (2) tabla `cameras` (`name` string(120), `name_key` string(120) UNIQUE = `name.strip().casefold()`, `created_at` UTC); (3) migración de datos que lee los `camera_id` distintos y los agrupa por `name_key` calculado en Python con una copia fija de `normalize_name_key` dentro de la migración (sin importar código de la app ni usar `lower`/`btrim` de SQL), sufijo ` (n)` truncado a 120 caracteres y `logger.warning` por conflicto; (4) `sessions.registered_camera_id` UUID FK → `cameras.id` NOT NULL (agregar nullable, poblar, luego NOT NULL) + UNIQUE `(id, registered_camera_id)`; (5) `video_sources`, `reference_frames`, `shops`, `scene_versions`, `scene_version_shops`, `scene_zones`, `scene_entry_lines` con todos los tipos, CHECKs (`> 0`, `≥ 0`, `≥ 1`), UNIQUEs (`(camera_id, version_number)`, `(id, camera_id)`, `(scene_version_id, name_key)`, `(scene_version_id, shop_id)`, `(version_shop_id, role)`) y FK compuestas del data-model; índice sobre `video_sources.sha256`; enums `zone_role` (`interior|front|showcase`) y `entry_direction` (`a_to_b|b_to_a`); (6) `processing_jobs.scene_version_id` y `registered_camera_id` nullable, FK compuestas `(session_id, registered_camera_id) → sessions(id, registered_camera_id)` y `(scene_version_id, registered_camera_id) → scene_versions(id, camera_id)`, y CHECK `(kind = 'video_analysis') = (scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)`; (7) función `flowsight_forbid_mutation()` que hace `raise exception 'scene configuration is immutable'` y triggers `BEFORE UPDATE OR DELETE FOR EACH ROW` en las cuatro tablas de escena; (8) `downgrade()` que borra tablas, columnas, triggers, función y enums nuevos, dejando los valores agregados a enums existentes. Correr T004 hasta verde. · ADO #74
- [X] T006 Extender `backend/src/flowsight/db/models.py` para reflejar exactamente `0002`: `SourceKind.video_file`, `JobKind.video_analysis`, enums `ZoneRole` y `EntryDirection`, modelos `Camera`, `VideoSource`, `ReferenceFrame` (`image` como `LargeBinary`, cargado con `deferred`), `Shop`, `SceneVersion`, `SceneVersionShop`, `SceneZone` (`polygon` JSONB), `SceneEntryLine`; `Session.registered_camera_id` y relación `camera`; `ProcessingJob.scene_version_id` y `registered_camera_id`; todas las `ForeignKeyConstraint` compuestas y `UniqueConstraint` con los mismos nombres que la migración. Verificar con `alembic check` (o comparando metadata) que no queden diferencias entre modelos y migración. · ADO #74
- [X] T007 Crear `backend/src/flowsight/services/cameras.py` con `normalize_name_key(name) = name.strip().casefold()`, `get_or_create_camera(db, name)` (`INSERT … ON CONFLICT (name_key) DO NOTHING` + `SELECT`), `create_camera(db, name)` que lanza un error de dominio `CameraExists(existing_id)` y `list_cameras(db)` ordenado por nombre. Usar `get_or_create_camera` en `POST /sessions` (`backend/src/flowsight/api/routes.py`) para completar `registered_camera_id` sin cambiar su contrato; `backend/tests/contract/test_sessions_jobs_api.py` y el resto de la suite de specs/002 DEBEN seguir en verde sin modificar sus aserciones (solo cambian a `destructive_database_url()` de T050 y, donde crean sesiones sin pasar por la API —`test_migrations.py` y `create_pending_job` de `test_worker_lifecycle.py`—, la preparación de datos registra la cámara con `get_or_create_camera` o un `INSERT` en `cameras`). · ADO #74
- [X] T008 [P] Crear `backend/src/flowsight/api/errors.py` con `api_error(status_code, code, message, **extra) -> HTTPException` que produzca `{"detail": {"code", "message", ...}}` según `ErrorDetail` de [openapi.yaml](./contracts/openapi.yaml), y con `redact_paths(text, settings)` que reemplace la ruta absoluta de `FLOWSIGHT_VIDEOS_DIR` y cualquier ruta absoluta por un marcador (FR-013). Reutilizar el helper `not_found` existente de `routes.py` a través de `api_error(404, "not_found", …)`. Pruebas unitarias en `backend/tests/unit/test_api_errors.py`. · ADO #73

**Checkpoint**: `alembic upgrade head` aplica `0002` sobre una base con datos de specs/002; toda la suite previa sigue en verde.

---

## Phase 3: User Story 1 — Registrar un video local como sesión (Priority: P1) · #53 🎯 MVP

**Goal**: Registrar un video local desde el navegador como sesión `video_file`, con metadatos, frame de referencia en PostgreSQL, equipo de origen, hash y disponibilidad por equipo.

**Independent Test**: Registrar un clip generado por `flowsight.video.fixtures` y ver en el detalle resolución, fps, duración, cantidad de frames, frame de referencia, equipo de origen y SHA-256; comprobar que en la base no hay bytes del video y que al mover el archivo el detalle muestra `missing` sin error genérico.

### Tests for User Story 1 ⚠️

- [X] T009 [P] [US1] Escribir `backend/tests/unit/test_video_probe.py` usando clips de T003: MJPG `.avi` y mp4v `.mp4` informan `frame_count` contado con `grab()` (no `CAP_PROP_FRAME_COUNT`), `width`/`height` del frame decodificado, `fps` de encabezado con `fps_is_estimated = False`, `frame_index = 0`, `video_timestamp_seconds = 0`, `duration_seconds = frame_count / fps` y JPEG válido (empieza con `FF D8`) con la resolución original; fps fuera de `(0, 240]` (simulado con un doble de `VideoCapture`) se estima con `CAP_PROP_POS_MSEC` del último frame `/ (frames − 1)` y marca `fps_is_estimated = True`; sin fps medible → `fps_unknown`; texto renombrado `.mp4` → `unsupported_format`; video truncado sin frames decodificables → `no_decodable_frames`; con el `.mpg` de T003, `frame_count` igual a los frames escritos (contados con `grab()`) y `duration_seconds` derivada de ese conteo, no del encabezado (skip con motivo si el fixture MPEG no está disponible). · ADO #75
- [X] T010 [P] [US1] Escribir `backend/tests/unit/test_video_storage.py`: copia por bloques de 1 MiB a `<videos_dir>/.incoming/<uuid>.partial` calculando SHA-256 (hex minúscula) y tamaño en una sola pasada; cuerpo vacío → `file_empty`; desconexión simulada → se borra el `.partial` y se informa `upload_interrupted`; `OSError(ENOSPC)` → `insufficient_storage` y sin `.partial`; `finalize` con `os.replace` a `<session_id><ext>` y `discard` que borra parcial y destino; limpieza al arranque de `.partial` con más de 1 h (y no los recientes); extensiones permitidas exactamente `.mp4`, `.mpg`, `.mpeg`, `.avi`, `.mov`, `.mkv` (sin distinguir mayúsculas); `relative_path` sin `..` ni separadores iniciales; disponibilidad `available`/`missing`/`mismatch` (mismo tamaño y distinto contenido)/`not_configured`, con caché por `(ruta, tamaño, mtime_ns)` que no rehashea si el archivo no cambió; carpeta inexistente o sin permiso → `videos_dir_not_writable`. · ADO #75
- [X] T011 [P] [US1] Escribir `backend/tests/contract/test_cameras_api.py`: `POST /cameras` → 201 con `id`, `name`, `created_at`; `name` vacío tras `strip` o > 120 caracteres → 422; `"Cam 01"` y luego `" cam 01 "` → 409 `camera_exists` con el `id` existente; lo mismo con `"Straße"` y luego `"STRASSE"`; `GET /cameras` lista las cámaras creadas y las generadas por `POST /sessions` sintético. · ADO #75
- [X] T012 [P] [US1] Escribir `backend/tests/contract/test_video_sessions_api.py` (PostgreSQL + `tmp_path` como `FLOWSIGHT_VIDEOS_DIR`), cubriendo [contracts/video-registration.md](./contracts/video-registration.md): registro exitoso 201 con el `SessionDetail` completo (también con el `.mpg` de T003, o skip con motivo si no está disponible), `source_kind = "video_file"`, `camera_id` de texto = `cameras.name`, archivo en `<videos_dir>/<session_id><ext>` y `.incoming/` vacío; la fila de `video_sources` y `reference_frames` no contiene los bytes del video (FR-007: tamaño de la base de la fila ≪ tamaño del archivo y ningún campo con el contenido); cámara inexistente → 404; extensión inválida → 422 `unsupported_format` sin leer el cuerpo; vacío → `file_empty`; texto renombrado → `unsupported_format`; truncado → `no_decodable_frames`; en todos los rechazos no queda sesión, `video_sources` ni archivo (SC-002); sin `FLOWSIGHT_VIDEOS_DIR` / carpeta no escribible / sin `FLOWSIGHT_MACHINE_ID` → 503 con el código correspondiente; mismo video dos veces → 201 y `duplicate_session_ids` contiene la primera; `GET /sessions` lista resumen sin disponibilidad; `GET /sessions/{id}` informa `availability` `available`, luego `missing` tras mover el archivo, `mismatch` tras reemplazarlo y `not_configured` sin carpeta, manteniendo metadatos y `reference_frame` (SC-007); `GET /sessions/{id}/reference-frame` → `image/jpeg` con `Cache-Control: private, max-age=86400, immutable` y 404 para sesiones sintéticas; `PUT /sessions/{id}/video` con el archivo correcto → vuelve a `available` sin cambiar metadatos, con otro → 409 `hash_mismatch` sin tocar el archivo existente, sobre sesión sintética → 409 `not_video_session`; ningún cuerpo de error contiene la ruta absoluta de `tmp_path` ni `FLOWSIGHT_DATABASE_URL` (FR-013). El `GET /sessions/{id}` de sesiones sintéticas sigue respondiendo lo que espera `test_sessions_jobs_api.py`. · ADO #75

### Implementation for User Story 1

- [X] T013 [P] [US1] Implementar `backend/src/flowsight/video/probe.py` con `probe_video(path) -> ProbeResult` (dataclass con `width`, `height`, `fps: Decimal`, `fps_is_estimated`, `frame_count`, `duration_seconds: Decimal`, `reference_frame_index`, `reference_timestamp_seconds: Decimal`, `reference_jpeg: bytes`) y la excepción `VideoRejected(code)` con códigos `unsupported_format`, `no_decodable_frames`, `fps_unknown`, según [R3](./research.md#r3-sondeo-del-video-fps-frames-duración-y-frame-de-referencia): conteo con `grab()`, primer `grab()`+`retrieve()` exitoso como referencia, JPEG con `cv2.imencode(".jpg", frame, [IMWRITE_JPEG_QUALITY, 90])` a resolución original, fps de `CAP_PROP_FPS` si está en `(0, 240]` o estimado. Sin acceso a DB ni FastAPI. Hasta T009 en verde. · ADO #75
- [X] T014 [P] [US1] Implementar `backend/src/flowsight/video/storage.py` según [R2](./research.md#r2-atomicidad-de-la-copia-y-limpieza) y [R7](./research.md#r7-disponibilidad-del-video-en-el-equipo-actual-fr-009): `ensure_videos_dir(settings)` (503 codes), `ALLOWED_EXTENSIONS`, `async stream_to_partial(chunks, videos_dir) -> PartialUpload(path, sha256, size_bytes)` con `fsync`, manejo de `ClientDisconnect` y `ENOSPC`, `finalize(partial, videos_dir, session_id, ext) -> relative_path`, `discard(...)`, `cleanup_stale_partials(videos_dir, max_age=3600)` y `check_availability(videos_dir, relative_path, size_bytes, sha256)` con caché en memoria del proceso por `(ruta, tamaño, mtime_ns)`. Hasta T010 en verde. · ADO #75
- [X] T015 [US1] Crear `backend/src/flowsight/services/video_sessions.py`: `register_video_session(db, settings, name, registered_camera_id, original_filename, chunks)` que sigue la secuencia de [video-registration.md](./contracts/video-registration.md) (valida extensión antes de leer el cuerpo → carpeta y `machine_id` → copia y hash → `probe_video` → INSERT de `sessions` con `source_kind = video_file`, `camera_id = cameras.name`, `registered_camera_id`, más `video_sources` (`relative_path = <session_id><ext>`, `original_filename` solo nombre base, `origin_machine_id = settings.machine_id`) y `reference_frames` (`media_type = "image/jpeg"`) → `finalize` → commit; si el commit falla, `discard` del destino); `relink_video(db, settings, session_id, chunks)` que compara SHA-256 y hace `os.replace` a `relative_path` sin volver a sondear; `find_duplicate_session_ids(db, sha256, exclude)`. Depende de T006, T013, T014. · ADO #75
- [X] T016 [US1] Agregar a `backend/src/flowsight/api/schemas.py` los modelos `CameraCreate` (`name` 1–120 tras `strip`, `extra="forbid"`), `CameraResponse`, `SessionSummary`, `SessionDetail`, `VideoSourceResponse` (con `availability`), `ReferenceFrameResponse` (con `url = /sessions/{id}/reference-frame`), siguiendo [openapi.yaml](./contracts/openapi.yaml). `SessionDetail` DEBE seguir incluyendo los campos que hoy devuelve `SessionResponse` para no romper specs/002. · ADO #75
- [X] T017 [US1] Implementar en `backend/src/flowsight/api/routes.py` los endpoints `GET /cameras`, `POST /cameras`, `GET /sessions`, `POST /video-sessions` (cuerpo crudo `application/octet-stream` leído con `request.stream()`, `name`, `registered_camera_id` y `filename` en la query, según el glosario de [data-model.md](./data-model.md#camera_id-y-registered_camera_id)), `GET /sessions/{session_id}` extendido con `camera`, `video` (con `availability`), `reference_frame` y `duplicate_session_ids`, `PUT /sessions/{session_id}/video` y `GET /sessions/{session_id}/reference-frame` (bytes JPEG, `Cache-Control: private, max-age=86400, immutable`). Traducir errores de dominio con `api_error` (T008); ningún mensaje con rutas absolutas. Hasta T011 y T012 en verde. · ADO #75
- [X] T018 [US1] En `backend/src/flowsight/api/main.py`, al arrancar, llamar a `cleanup_stale_partials` si `FLOWSIGHT_VIDEOS_DIR` está configurada y es escribible; si no, registrar un aviso sin la ruta absoluta y seguir arrancando. · ADO #75
- [X] T019 [P] [US1] Reemplazar el ruteo de `frontend/src/App.tsx` por un router mínimo propio con `window.location.pathname` + `history.pushState` + `popstate` para `/` (`SessionsPage`), `/sessions/:id` (`SessionDetailPage`) y `/sessions/:id/editor` (placeholder hasta US3), conservando `?job=<id>` → `JobPreviewPage` tal como lo usa `frontend/e2e/job-preview.spec.ts`. Exponer un helper `navigate(path)` en `frontend/src/navigation.ts`. Sin `react-router` ([R13](./research.md#r13-frontend-navegación-editor-svg-y-pruebas)). · ADO #76
- [X] T020 [P] [US1] Crear `frontend/src/types/session.ts` (tipos de `Camera`, `SessionSummary`, `SessionDetail`, `VideoSource`, `ReferenceFrame`, `ApiError`) y los clientes `frontend/src/api/cameras.ts` (`listCameras`, `createCamera` que devuelve el `id` existente ante `camera_exists`) y `frontend/src/api/sessions.ts` (`listSessions`, `getSession`, `referenceFrameUrl`, `registerVideoSession` y `relinkVideo` con `XMLHttpRequest`, `Content-Type: application/octet-stream`, callback de progreso desde `upload.onprogress` y parseo de `{detail:{code,message}}`), usando `VITE_API_BASE_URL` como `frontend/src/api/jobs.ts`. · ADO #76
- [X] T021 [US1] Crear `frontend/src/components/CameraPicker.tsx` (`<select>` de cámaras + formulario "Nueva cámara" con `<label>`; ante `camera_exists` selecciona la existente y lo informa) y `frontend/src/components/VideoUploadForm.tsx` (`<input type="file">` con `accept=".mp4,.mpg,.mpeg,.avi,.mov,.mkv"`, nombre de sesión, `CameraPicker`, barra `<progress>` determinada durante la subida y estado indeterminado "Analizando video…" hasta la respuesta; errores de lectura local como "No se pudo leer el archivo elegido" sin llamar a la API; mensajes de la API mostrados tal cual por `code`). Depende de T020. · ADO #76
- [X] T022 [US1] Crear `frontend/src/pages/SessionsPage.tsx` (listado de sesiones con cámara y tipo, `VideoUploadForm`, al registrar navega al detalle) y `frontend/src/pages/SessionDetailPage.tsx` (metadatos: resolución, fps con marca "estimado", duración, frames, equipo de origen, SHA-256, archivo original; `<img>` del frame de referencia; aviso de duplicado con enlaces; estado de disponibilidad con textos distintos para `available`, `missing` = "Video no disponible en este equipo", `mismatch` y `not_configured`; control para volver a cargar el video con progreso y el mensaje de `hash_mismatch`; enlace "Editar escena" a `/sessions/:id/editor`). Depende de T019–T021. · ADO #76

**Checkpoint**: US1 completa y demostrable sola (escenarios 1 a 5 de #53, SC-002, SC-007).

---

## Phase 4: User Story 2 — Definir y versionar la configuración espacial de una cámara (Priority: P1) · #54

**Goal**: Versiones inmutables por cámara con locales de identidad estable, validación geométrica en píxeles y compuerta de trabajos `video_analysis`.

**Independent Test**: Sin editor, con la API: guardar una versión válida (201, `version_number = 1`, coordenadas en [0, 1]), enviar el conjunto de inválidas (422 con `rule`, `element`, `shop_index`), guardar una v2 que renombra el mismo `shop_id`, comprobar que la v1 no cambió y que `POST /sessions/{id}/jobs` aplica la compuerta en orden y asocia la versión elegida.

### Tests for User Story 2 ⚠️

- [x] T023 [P] [US2] Escribir `backend/tests/unit/test_scene_geometry.py` con tabla de casos en el límite, en un frame de 1000×500: línea de 9,99 px rechazada y de 10 px aceptada; área de 99 px² rechazada y 100 px² aceptada; vértices consecutivos a 2 px rechazados y a 2,01 px aceptados, incluida la arista de cierre; vértices consecutivos repetidos rechazados; polígono en moño (cruce) y polígono con un vértice que toca una arista no adyacente → autointersección; vértice colineal dentro de una arista aceptado; orientación horaria y antihoraria dan la misma área; coordenadas 0 y 1 aceptadas, −0,000001 y 1,000001 rechazadas; lados A/B con `scene.example.json` del experimento 001 (`start (500,850)`, `end (1400,850)`, `p (950,1000)` → `cross = +135000` → A) y el mismo resultado tras normalizar; `aspect_ratio_mismatch` con `|(w_v/h_v)/(w_f/h_f) − 1| > 0.01` (1920×1080 vs 1280×720 permitido, 640×480 vs 1280×720 bloqueado); redondeo a 6 decimales. · ADO #77
- [x] T024 [P] [US2] Escribir `backend/tests/unit/test_scene_validation.py` con un caso por regla de la tabla "Validación al guardar una versión" de [data-model.md](./data-model.md) (`no_shops`, `duplicate_shop_name` con `"Local A"` y `" local a "`, `duplicate_shop_id`, `missing_front_zone`, `missing_entry_line`, `out_of_range`, `too_few_vertices`, `too_many_vertices` con 65 vértices, `vertices_too_close`, `self_intersection`, `area_too_small`, `line_too_short`), comprobando `rule`, `element` (`version`, `shop`, `zone:front`, `zone:interior`, `zone:showcase`, `entry_line`), `shop_index` y `shop_name`; que una configuración con varios errores los devuelve **todos**; y las advertencias `line_not_touching_zones` (línea que no toca ni cruza la frontal ni la interior) y `zones_overlap` (zonas de locales distintos), que no bloquean. · ADO #77
- [x] T025 [P] [US2] Escribir `backend/tests/contract/test_scene_api.py`: `POST /cameras/{id}/scene-versions` válido → 201 con `version_number = 1`, `frame_width`/`frame_height` del frame de referencia, `created_by_machine_id`, `shop_id` generado, coordenadas en [0, 1] con 6 decimales y `warnings`; cada caso inválido de SC-005 → 422 `invalid_scene_configuration` con `errors` completos; `reference_session_id` de otra cámara → `reference_session_other_camera`; sesión sintética de la misma cámara → `reference_frame_missing`; `shop_id` de otra cámara → `shop_other_camera`; v2 con el mismo `shop_id` y nombre nuevo → `version_number = 2`, mismo `shop_id`, y `GET /scene-versions/{v1}` devuelve la v1 byte a byte igual (JSON canónico) (SC-006); v3 sin ese local conserva el local en v1 y v2; `base_version_id` que no es la última → advertencia `newer_version_exists`; `GET /cameras/{id}/scene-versions` en orden descendente con `shop_count`; `PUT`/`PATCH`/`DELETE` sobre `/scene-versions/{id}` → 405; dos guardados concurrentes (dos conexiones/hilos) reciben números distintos sin error. · ADO #78
- [ ] T026 [P] [US2] Escribir `backend/tests/integration/test_scene_immutability.py`: `UPDATE` y `DELETE` directos sobre `scene_versions`, `scene_version_shops`, `scene_zones` y `scene_entry_lines` fallan con `scene configuration is immutable`; el `TRUNCATE` de las fixtures sigue funcionando. · ADO #78
- [ ] T027 [P] [US2] Escribir `backend/tests/integration/test_scene_isolation.py` con dos cámaras y dos sesiones de video por cámara (SC-008, FR-029): ninguna consulta de versiones o de una versión devuelve locales, zonas o líneas de otra cámara; insertar directamente un `scene_version_shops` con `shop_id` de otra cámara, un `scene_versions` con `reference_session_id` de otra cámara o un `processing_jobs` con `scene_version_id` de otra cámara viola las FK compuestas. · ADO #78
- [ ] T028 [P] [US2] Escribir `backend/tests/contract/test_jobs_gate_api.py`: sobre sesión de video, `video_analysis` sin versiones en la cámara → 409 `scene_not_configured`; sin `scene_version_id` habiendo versiones → 422 `scene_version_required`; versión de otra cámara → 422 `scene_version_other_camera`; sesión 640×480 con versión 1280×720 → 409 `aspect_ratio_mismatch` con `video_aspect_ratio` y `version_aspect_ratio`; sesión 1920×1080 con versión 1280×720 → 201, `status = pending`, `scene_version_id` y `registered_camera_id` guardados; elegir una versión anterior queda asociada aunque luego se cree otra (FR-027); el orden de la compuerta se respeta cuando fallan varias; sesión sintética con `scene_version_id` → 422 `scene_version_not_allowed`; `synthetic_base_flow` sobre sesión de video o `video_analysis` sobre sintética → 422 `job_kind_mismatch`. Agregar a `backend/tests/integration/test_worker_lifecycle.py` un caso: con un `video_analysis` pendiente más viejo y un `synthetic_base_flow` más nuevo, `claim_next_job` toma el sintético y el de video sigue `pending`. · ADO #79

### Implementation for User Story 2

- [x] T029 [P] [US2] Implementar `backend/src/flowsight/scene/__init__.py` y `backend/src/flowsight/scene/geometry.py` (puro, sin DB ni FastAPI), según [R11](./research.md#r11-geometría-coordenadas-tolerancias-y-convención-ab): `in_unit_range` (rango [0, 1] cerrado), `to_px` (solo convierte, sin validar rango), `normalize` con redondeo a 6 decimales, `polygon_area_px` (Shoelace, valor absoluto), `segments_intersect` con test de orientación y colineales (misma lógica que `segments_intersect` del experimento 001), `polygon_self_intersects` (aristas no adyacentes que se cruzan o tocan), `min_consecutive_distance_px` incluida la arista de cierre, `line_length_px`, `side_of_line(start, end, p) -> "A" | "B" | None` con `cross = dx·(py − sy) − dy·(px − sx)` (`> 0` → A), `aspect_ratio_matches(wv, hv, wf, hf, tol=0.01)`, `polygons_overlap` y `segment_touches_polygon` para advertencias. Constantes `MIN_LINE_PX = 10`, `MIN_AREA_PX2 = 100`, `MIN_VERTEX_GAP_PX = 2`, `MAX_VERTICES = 64`. Se puede hacer en paralelo con US1. Hasta T023 en verde. · ADO #77
- [x] T030 [US2] Implementar `backend/src/flowsight/scene/validation.py`: `SceneIssue` (dataclass con `rule`, `element`, `shop_index`, `shop_name`, `message` en español que nombra el local, el elemento y la regla) y `validate_scene(shops_input, frame_width, frame_height) -> (errors, warnings)` que aplica todas las reglas de geometría y de estructura (`no_shops`, `duplicate_shop_name` por `casefold(strip)`, `duplicate_shop_id`, `missing_front_zone`, `missing_entry_line`, a lo sumo una zona por rol) y las advertencias `line_not_touching_zones` y `zones_overlap`, devolviendo todos los errores y no solo el primero. Las reglas que requieren DB (`shop_other_camera`, `reference_*`, `newer_version_exists`) quedan en el servicio. Depende de T029; hasta T024 en verde. · ADO #77
- [ ] T031 [US2] Agregar a `backend/src/flowsight/api/schemas.py` `Point`, `EntryLineInput`, `ShopInput`, `SceneVersionCreate` (`extra="forbid"`, `shops` lista, `base_version_id` opcional), `SceneVersionSummary`, `SceneVersionResponse` (con `shops[].shop_id` obligatorio y `warnings`), `SceneIssueResponse` y extender `JobCreate` con `kind` `synthetic_base_flow | video_analysis` y `scene_version_id` opcional, más `scene_version_id` en la respuesta del trabajo, según [openapi.yaml](./contracts/openapi.yaml). La validación de rango y geometría NO se hace en Pydantic (para devolver todos los errores con `rule`), solo la de forma. · ADO #78
- [ ] T032 [US2] Implementar `backend/src/flowsight/services/scenes.py`: `create_scene_version(db, settings, camera_id, payload)` que (1) bloquea la cámara con `SELECT … FOR UPDATE`, (2) verifica que `reference_session_id` sea de esa cámara (`reference_session_other_camera`) y tenga `reference_frames` (`reference_frame_missing`), (3) valida `shop_id` existentes de la cámara (`shop_other_camera`), (4) llama a `validate_scene` con la resolución del frame, (5) si hay errores lanza `InvalidSceneConfiguration(errors)` sin escribir nada, (6) calcula `max(version_number) + 1`, crea `shops` nuevos para los `shop_id` nulos e inserta versión, locales (`position`, `name` tras `strip`, `name_key`), zonas y línea redondeadas a 6 decimales, con `created_by_machine_id = settings.machine_id`, y (7) agrega `newer_version_exists` si `base_version_id` no es la última; `list_scene_versions(db, camera_id)` descendente con `shop_count`; `get_scene_version(db, id)` con locales ordenados por `position`. Depende de T006, T030. Decisiones (T025): una `reference_session_id` inexistente responde `reference_session_other_camera` (la sesión se busca por `id` y cámara); si la referencia falla no se valida la geometría (no hay resolución de frame); sin `FLOWSIGHT_MACHINE_ID` se guarda `created_by_machine_id = null` (sin 503). · ADO #78
- [ ] T033 [US2] Implementar en `backend/src/flowsight/api/routes.py` `GET /cameras/{camera_id}/scene-versions`, `POST /cameras/{camera_id}/scene-versions` (201 con `warnings`; 422 `{"detail":{"code":"invalid_scene_configuration","message","errors":[…]}}`; 404 si la cámara no existe) y `GET /scene-versions/{scene_version_id}`, sin rutas `PUT`/`PATCH`/`DELETE`. Hasta T025–T027 en verde. · ADO #78
- [ ] T034 [US2] Extender `backend/src/flowsight/services/jobs.py` con `create_job_for_session(db, session, kind, scene_version_id)` que valida `job_kind_mismatch`, `scene_version_not_allowed`, `scene_version_required` y luego la compuerta en orden `scene_not_configured` (409) → `scene_version_other_camera` (422) → `aspect_ratio_mismatch` (409, con `video_aspect_ratio` y `version_aspect_ratio`) usando `aspect_ratio_matches` de T029, y crea el trabajo en `pending` con `scene_version_id` y `registered_camera_id` (FR-025 a FR-028). Usarlo desde `POST /sessions/{session_id}/jobs` en `backend/src/flowsight/api/routes.py`, conservando el comportamiento de specs/002 para sesiones sintéticas. · ADO #79
- [ ] T035 [US2] Filtrar `claim_next_job` en `backend/src/flowsight/worker/lifecycle.py` por `ProcessingJob.kind.in_(SUPPORTED_JOB_KINDS)` con `SUPPORTED_JOB_KINDS = (JobKind.synthetic_base_flow,)`, manteniendo `FOR UPDATE SKIP LOCKED` y el orden `(created_at, id)`; la recuperación de trabajos `PROCESSING` interrumpidos no cambia. Hasta T028 en verde. · ADO #79
- [ ] T036 [US2] Crear `frontend/src/types/scene.ts` (tipos de `SceneVersionSummary`, `SceneVersion`, `ShopInput`, `EntryLine`, `SceneIssue`, `ZoneRole`, `EntryDirection`) y `frontend/src/api/scenes.ts` (`listSceneVersions`, `getSceneVersion`, `createSceneVersion` que devuelve `{ok, version, warnings}` o `{ok: false, errors}` ante 422, y `createVideoAnalysisJob(sessionId, sceneVersionId)`). En `frontend/src/pages/SessionDetailPage.tsx`, agregar la sección "Iniciar análisis": `<select>` de versiones de la cámara con la última preseleccionada, botón "Iniciar análisis" y mensajes para `scene_not_configured` (con enlace al editor), `aspect_ratio_mismatch` (pide crear una versión sobre el frame de esta sesión) y el trabajo creado en `pending` (US2 escenario 6). · ADO #79

**Checkpoint**: US1 y US2 funcionan juntas; la compuerta y la asociación trabajo → versión están probadas por API.

---

## Phase 5: User Story 3 — Editor visual de zonas y líneas sobre el frame de referencia (Priority: P1) · #55

**Goal**: Editor SVG sobre el frame de referencia que produce versiones de US2 sin editar archivos, estable al redimensionar y operable con teclado.

**Independent Test**: Abrir `/sessions/:id/editor`, dibujar un local completo, mover vértices, elegir el sentido de entrada, redimensionar la ventana tres veces, guardar y comprobar vía API que las coordenadas difieren < 0,5 % de las dibujadas.

### Tests for User Story 3 ⚠️

- [ ] T037 [P] [US3] Escribir `frontend/src/editor/coordinates.test.ts` (Vitest): pantalla → frame con una matriz `DOMMatrix` simulada (escala y offset de `xMidYMid meet`) e inversa; frame → normalizado con 6 decimales y normalizado → frame; ida y vuelta estable a 1e-6; `clampToFrame`; `aspectRatioMatches` con la misma fórmula que el backend (T029): 1920×1080 contra 1280×720 coincide, 640×480 contra 1280×720 no; posiciones de etiquetas A/B a ±20 px de la normal en el punto medio con la convención `cross > 0` → A en coordenadas de imagen (mismo caso que `scene.example.json`); flecha de entrada según `a_to_b`/`b_to_a`. · ADO #80
- [ ] T038 [P] [US3] Escribir `frontend/src/editor/editorState.test.ts` (Vitest) para el reducer: cargar una versión existente (convierte a píxeles del frame y conserva `shop_id`); cargar una versión cuyo frame tiene otra relación de aspecto marca `aspectMismatch = true` y conserva todos los locales con su `shop_id` (FR-030); crear, renombrar y quitar locales (quitar no afecta otros locales, renombrar conserva `shop_id`); crear polígono por clics y cerrarlo, crear línea con dos clics; mover vértice / extremo, incluido por teclado (1 px y 10 px con Shift, limitado al frame); eliminar vértice (sin bajar de 3) y elemento; asignar rol respetando "a lo sumo una zona por rol"; cambiar `entry_direction`; `isDirty` pasa a `true` con cambios y a `false` tras guardar; `toSceneVersionCreate` normaliza solo al guardar e incluye `base_version_id`; aplicar errores de la API por `shop_index` + `element` sin descartar el dibujo. · ADO #80
- [ ] T039 [US3] Escribir `frontend/e2e/scene-editor.spec.ts` (Playwright) y ajustar `frontend/e2e/run-e2e.mjs` para exportar `FLOWSIGHT_VIDEOS_DIR` (directorio temporal) y `FLOWSIGHT_MACHINE_ID=e2e-ci`, y generar un clip 1280×720 con `backend/.venv` + `python -m flowsight.video.fixtures`, sin romper `job-preview.spec.ts`. El recorrido: crear cámara y registrar el clip desde `/`; ver el detalle y el frame; abrir el editor; crear "Local A" con zona frontal, interior, vidriera y línea con sentido A→B usando controles por rol y nombre accesible; comprobar etiquetas A/B y flecha; mover un vértice con el teclado; redimensionar el viewport a tres tamaños y verificar que los vértices siguen sobre los mismos puntos de la imagen; guardar y comparar vía `GET /scene-versions/{id}` con el estado dibujado (< 0,5 % del ancho/alto, SC-004); dibujar un polígono autointersectado, guardar y ver el error sobre ese elemento sin perder el dibujo; con cambios sin guardar, navegar fuera y comprobar la advertencia (manejar `dialog` de Playwright). · ADO #81

### Implementation for User Story 3

- [ ] T040 [P] [US3] Implementar `frontend/src/editor/coordinates.ts` con `screenToFrame(svg, clientX, clientY)` usando `getScreenCTM().inverse()`, `frameToNormalized`, `normalizedToFrame`, `clampToFrame`, `aspectRatioMatches(wv, hv, wf, hf, tol = 0.01)`, `lineSideLabelPositions(start, end, offset = 20)` y `entryArrow(start, end, direction)`. Todo el estado del editor vive en píxeles del frame; se normaliza solo al guardar (FR-033). Hasta T037 en verde. · ADO #80
- [ ] T041 [P] [US3] Implementar `frontend/src/editor/editorState.ts` como reducer puro (`useReducer`) con las acciones de T038, selección actual (local, elemento, vértice), `isDirty`, `aspectMismatch`, `issues` mapeados por `shop_index` + `element`, y `toSceneVersionCreate(state, referenceSessionId, frameWidth, frameHeight)`. Hasta T038 en verde. · ADO #80
- [ ] T042 [US3] Implementar `frontend/src/components/SceneCanvas.tsx`: `<svg viewBox="0 0 W H" preserveAspectRatio="xMidYMid meet">` con `<image href={referenceFrameUrl}>`, polígonos por rol con estilos distinguibles, línea de entrada con etiquetas "A"/"B" y flecha de entrada, elementos con error resaltados, vértices como `<circle role="button" aria-label="Vértice n de <rol> de <local>" tabIndex={0}>` movibles con puntero (pointer capture) y flechas del teclado; clics sobre el fondo agregan vértices en modo creación. Depende de T040, T041. · ADO #81
- [ ] T043 [P] [US3] Implementar `frontend/src/components/ShopPanel.tsx` (lista de locales con `<input>` de nombre etiquetado, botones "Agregar local", "Quitar local de esta versión", "Crear zona" con `<select>` de rol `front`/`interior`/`showcase`, "Crear línea de entrada", "Eliminar elemento", "Eliminar vértice"), `frontend/src/components/EntryLineControls.tsx` (`<fieldset>` con `<legend>` y radios "A → B es entrada" / "B → A es entrada") y `frontend/src/components/SceneIssues.tsx` (lista de errores y advertencias con local, elemento y mensaje; al activar uno, selecciona el elemento). Depende de T041. · ADO #81
- [ ] T044 [US3] Implementar `frontend/src/pages/SceneEditorPage.tsx` y conectarla a `/sessions/:id/editor` en `frontend/src/App.tsx`: carga la sesión y su frame, y la última versión de la cámara si existe (FR-030); si la sesión no tiene frame de referencia, muestra un mensaje y no abre el editor; mientras `aspectMismatch` sea verdadero, muestra una advertencia persistente (`role="alert"`) de que las figuras precargadas pueden verse deformadas y deben revisarse antes de guardar; compone `SceneCanvas`, `ShopPanel`, `EntryLineControls` y `SceneIssues`; botón "Guardar versión" que llama a `createSceneVersion` con `base_version_id`, muestra el número de versión y las advertencias, y ante 422 marca los elementos sin descartar el dibujo (FR-034); advertencia de salida con `beforeunload` y `window.confirm` en `navigate` interno mientras `isDirty` (FR-035). Hasta T039 en verde. · ADO #81

**Checkpoint**: Las tres historias funcionan juntas; el recorrido E2E de specs/002 sigue en verde.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Actualizar `.github/workflows/ci.yml` para que el job de E2E y el de backend definan `FLOWSIGHT_VIDEOS_DIR` (directorio temporal del runner) y `FLOWSIGHT_MACHINE_ID`, y confirmar que la caché usa el `backend/requirements.lock` nuevo; sin videos, pesos ni credenciales. · ADO #82
- [ ] T046 [P] Registrar en `docs/decisiones-tecnicas.md` la decisión R5 (el frame de referencia se guarda como JPEG en PostgreSQL; el video nunca) reemplazando la línea "previews… no van en PostgreSQL salvo decisión posterior", y la dependencia `opencv-python-headless` en el backend (R4). · ADO #82
- [ ] T047 [P] Actualizar `README.md` ("Estado del proyecto" y configuración): registro de video, `FLOWSIGHT_VIDEOS_DIR` y `FLOWSIGHT_MACHINE_ID`, editor de escenas, que `video_analysis` queda en `pending` hasta #56 y que la migración `0002` renombra cámaras en conflicto con sufijo; que `pytest` nunca se corre contra la base compartida de Azure y cómo usar `FLOWSIGHT_TEST_DATABASE_URL` (T050). · ADO #82
- [ ] T048 Correr la regresión completa: desde `backend/`, `.venv/bin/ruff check .` y `.venv/bin/pytest`; desde `frontend/`, `npm run lint`, `npm test`, `npm run build` y `npm run test:e2e`. Analizar el primer fallo si lo hay. · ADO #82
- [ ] T049 Ejecutar los escenarios manuales de [quickstart.md](./quickstart.md) y registrar en `specs/004-configuracion-escenas/validation/` las mediciones de SC-001 (video real de ~5 min, < 30 s; si no se cumple, documentar y aplicar la alternativa de R3), SC-003 (persona que no participó del desarrollo, < 5 min) y SC-004 (< 0,5 % tras tres tamaños) y el registro de un `.mpg` real del material del experimento 001, con el `frame_count` contado frente al declarado en el encabezado (respaldo manual de G1), sin rutas absolutas, nombres de equipo, nombres de personas ni secretos. · ADO #82

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias. T001 bloquea T003 (necesita `cv2`).
- **Foundational (Phase 2)**: depende de Setup. T050 → T004 → T005 → T006 → T007. T003 y T008 en paralelo. T050 va antes de correr cualquier prueba PostgreSQL de esta feature. Bloquea todas las historias.
- **US1 (Phase 3)**: depende de Foundational.
- **US2 (Phase 4)**: depende de Foundational y de US1 backend (T015, T017), porque una versión necesita una sesión con frame de referencia. T023, T024 y T029–T030 (geometría pura) pueden empezar apenas termina Foundational, en paralelo con US1. T036 depende de T022.
- **US3 (Phase 5)**: T037, T038, T040, T041 pueden empezar tras Foundational; T042–T044 y T039 dependen de US1 (frontend y endpoints) y del guardado de US2 (T033, T036).
- **Polish (Phase 6)**: depende de las tres historias.

### User Story Dependencies

- **US1 (#53)**: independiente tras Foundational. MVP.
- **US2 (#54)**: necesita sesiones de video de US1 para guardar versiones; su geometría es independiente.
- **US3 (#55)**: necesita el frame de US1 y el guardado de US2.

### Within Each User Story

- Pruebas primero y fallando.
- Módulos puros (`video/`, `scene/`) → servicios → schemas → rutas → frontend.
- Una tarea a la vez, con confirmación antes de pasar a la siguiente (CLAUDE.md del repo).

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo:
Task: "T009 test_video_probe.py en backend/tests/unit/"
Task: "T010 test_video_storage.py en backend/tests/unit/"
Task: "T011 test_cameras_api.py en backend/tests/contract/"
Task: "T012 test_video_sessions_api.py en backend/tests/contract/"

# Módulos puros y frontend base en paralelo:
Task: "T013 backend/src/flowsight/video/probe.py"
Task: "T014 backend/src/flowsight/video/storage.py"
Task: "T019 router mínimo en frontend/src/App.tsx"
Task: "T020 clientes frontend/src/api/cameras.ts y sessions.ts"
```

## Parallel Example: User Story 2

```bash
# Arrancan apenas termina Foundational, junto con US1:
Task: "T023 backend/tests/unit/test_scene_geometry.py"
Task: "T024 backend/tests/unit/test_scene_validation.py"
Task: "T029 backend/src/flowsight/scene/geometry.py"

# Tras US1 backend:
Task: "T025 test_scene_api.py"
Task: "T026 test_scene_immutability.py"
Task: "T027 test_scene_isolation.py"
Task: "T028 test_jobs_gate_api.py"
```

## Parallel Example: User Story 3

```bash
Task: "T037 frontend/src/editor/coordinates.test.ts"
Task: "T038 frontend/src/editor/editorState.test.ts"
Task: "T040 frontend/src/editor/coordinates.ts"
Task: "T041 frontend/src/editor/editorState.ts"
Task: "T043 ShopPanel.tsx, EntryLineControls.tsx, SceneIssues.tsx"
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 y Phase 2.
2. Phase 3 (US1 #53).
3. **Validar**: escenarios 1 y 2 de `quickstart.md`.

### Incremental Delivery

1. Setup + Foundational → esquema `0002` aplicado sin romper specs/002.
2. US1 → registro de videos y frame de referencia → demo.
3. US2 → versiones y compuerta por API → demo.
4. US3 → editor visual → demo del MVP del 2/oct.
5. Cierre: CI, documentación y mediciones.

### Parallel Team Strategy

1. Todo el equipo cierra Setup + Foundational.
2. Después:
   - Persona A: US1 backend (T009–T018).
   - Persona B: US1 frontend (T019–T022).
   - Persona C: geometría y validación de US2 (T023, T024, T029, T030).
   - Persona D: estado y coordenadas del editor de US3 (T037, T038, T040, T041).
3. Al cerrar US1 backend: servicio, rutas y compuerta de US2; luego el editor completo de US3.

---

## Notes

- [P] = archivos distintos y sin dependencias pendientes. `routes.py` y `schemas.py` se tocan en varias tareas: no paralelizarlas entre sí.
- Commits con Conventional Commits, uno por tarea o grupo lógico.
- No subir videos, frames exportados ni `.env` a Git; los clips de prueba se generan en runtime.
- No modificar `experiments/video-tracking-validation/`; solo se replica su convención A/B.
