# Research: Carga, configuración y editor visual de escenas

Decisiones de Phase 0 para `specs/004-configuracion-escenas`. Cada una resuelve una incógnita del Technical Context o un ítem abierto de `checklists/data-geometry.md` que el plan puede fijar sin cambiar la spec.

## R1. Transporte del video desde el navegador

- **Decision**: El navegador envía el archivo como cuerpo crudo (`Content-Type: application/octet-stream`) en `POST /video-sessions`, con nombre de sesión, cámara y nombre de archivo original en la query. La API lee `request.stream()` por bloques, escribe en `<videos_dir>/.incoming/<uuid>.partial` y calcula SHA-256 y tamaño en la misma pasada. El frontend usa `XMLHttpRequest` para mostrar el progreso de la subida con `upload.onprogress`. Después muestra una fase indeterminada de "analizando video".
- **Rationale**: API y navegador corren en el mismo equipo (procesamiento local), así que "subir" es copiar a la carpeta de videos. El cuerpo crudo evita el doble volcado de `UploadFile`, que primero guarda el archivo en el temp del sistema, y no agrega `python-multipart`. Hashear durante la copia evita leer el archivo dos veces. El progreso de subida cubre el caso borde de "archivos grandes sin indicar progreso".
- **Alternatives considered**: `multipart/form-data` + `UploadFile` (nueva dependencia y doble escritura). Hash en el navegador con WebCrypto (no tiene SHA-256 incremental y obliga a cargar todo el archivo en memoria). Que el operador escriba una ruta local (lo descartó la clarificación: "elige el archivo desde el navegador").

## R2. Atomicidad de la copia y limpieza

- **Decision**: El orden es: parcial en `.incoming/`, luego `fsync` y sondeo (R3). Después se hace el INSERT en una transacción y `os.replace` al destino final `<session_id><ext>`, y recién entonces el commit. Si falla el commit se borra el destino. Si el cliente se desconecta (`ClientDisconnect`), el disco se llena (`ENOSPC`, HTTP 507) o el sondeo falla, se borra el parcial. Al arrancar, la API borra los `.partial` de `.incoming/` con más de 1 h.
- **Rationale**: Cumple "no se crea la sesión ni queda un archivo parcial" (caso borde, FR-011). El nombre final lo genera el servidor, así que el nombre del cliente nunca entra en la ruta (no hay path traversal). `os.replace` es atómico dentro del mismo volumen, y `.incoming/` vive en ese mismo volumen.
- **Alternatives considered**: Escribir directo al destino (deja parciales visibles). Subida en dos pasos con `upload_id` (deja huérfanos si el operador abandona y agrega un endpoint).

## R3. Sondeo del video: fps, frames, duración y frame de referencia

- **Decision**: Se usa OpenCV (`cv2.VideoCapture`) sobre el parcial:
  - **Frames**: se cuentan recorriendo el video con `grab()`, sin confiar en `CAP_PROP_FRAME_COUNT`. Es la lección del experimento 001 con MPEG.
  - **Frame de referencia**: el primer `grab()` + `retrieve()` exitoso. Su índice es la cantidad de `grab()` previos y su timestamp es `índice / fps`.
  - **fps**: `CAP_PROP_FPS` si está en (0, 240]. Si no, se estima con `CAP_PROP_POS_MSEC` del último frame / (frames − 1) y se marca `fps_is_estimated = true`. Si ninguno funciona, se rechaza con `fps_unknown`.
  - **Duración**: `frame_count / fps`, la misma base de tiempo que usa el experimento (`frame_index / fps`).
  - **Resolución**: la del frame de referencia decodificado, no la del encabezado.
  - **Formatos**: se aceptan las extensiones `.mp4`, `.mpg`, `.mpeg`, `.avi`, `.mov`, `.mkv`. La prueba de verdad es que OpenCV decodifique al menos un frame. Si no se puede abrir, el error es `unsupported_format`; si abre pero no decodifica ningún frame, `no_decodable_frames`.
- **Rationale**: Es consistente con `experiments/video-tracking-validation/video_io.py`, que ya validó OpenCV con el material real. `grab()` evita la conversión de color de `read()`.
- **Riesgo / validación**: SC-001 (5 min en < 30 s) depende de la velocidad de `grab()` en la PC de desarrollo. `quickstart.md` lo mide. Si no se cumple, la alternativa documentada es confiar en el encabezado para contenedores con índice (MP4) y contar solo en MPEG.
- **Alternatives considered**: `ffprobe` (binario externo a instalar por equipo). PyAV (dependencia nueva que no está en el stack).

## R4. Dependencia nueva del backend

- **Decision**: Agregar `opencv-python-headless==4.10.0.84` (con su `numpy` fijado en el lock) a `backend/pyproject.toml` y `backend/requirements.lock`. Es la misma versión que usa el experimento; la variante *headless* no trae GUI y se instala en CI Ubuntu sin librerías de sistema. No se agrega `python-multipart` (R1).
- **Rationale**: OpenCV está en el stack acordado (`docs/decisiones-tecnicas.md`, "Detección y tracking") y el worker de #56 lo va a necesitar igual. AGENTS.md exige consultar antes de instalar: el usuario la confirmó el 2026-09-26, junto con R5 (frame de referencia en PostgreSQL) y R12 (`video_analysis` en `pending` hasta #56).
- **Alternatives considered**: `opencv-python` completo (arrastra dependencias GUI innecesarias en CI).

## R5. Frame de referencia accesible desde cualquier equipo (FR-006)

- **Decision**: Guardar el frame de referencia como JPEG (calidad 90, resolución original) en una columna `bytea` de la tabla `reference_frames`, separada de `video_sources` para no cargarlo en los listados. Se sirve con `GET /sessions/{id}/reference-frame` (`image/jpeg`, `Cache-Control: private, max-age=86400, immutable`).
- **Rationale**: Es la única forma de verlo desde otro equipo sin el video ni un file server. A 1080p pesa ~200–400 KB por sesión. Corrige de forma explícita la línea "previews no van en PostgreSQL salvo decisión posterior" de `docs/decisiones-tecnicas.md`, que se actualiza en la implementación. El video sigue fuera de la base (FR-007).
- **Alternatives considered**: Blob storage (servicio cloud nuevo, fuera del alcance). Archivo local (no se ve desde otro equipo). Reducir la resolución (el editor perdería precisión).

## R6. Identificador del equipo y carpeta de videos

- **Decision**: Dos variables nuevas y **opcionales** en `Settings`:
  - `FLOWSIGHT_VIDEOS_DIR`: ruta absoluta.
  - `FLOWSIGHT_MACHINE_ID`: formato `^[a-z0-9][a-z0-9-]{2,39}$`, p. ej. `equipo-03`. `.env.example` indica que no se use el nombre de la persona ni el usuario del sistema.
  
  La API y el worker arrancan sin ellas, así los `.env` actuales del equipo siguen funcionando. Los endpoints de registro y recarga de video responden 503 con `videos_dir_not_configured`, `videos_dir_not_writable` o `machine_id_not_configured` y la acción sugerida, sin mostrar la ruta absoluta (FR-013).
- **Rationale**: Es la opción que la spec dejó al plan ("configurable por variable de entorno"). Si fueran obligatorias, se rompería el arranque de los seis integrantes y de CI. Con un formato restringido baja el riesgo de filtrar datos personales (FR-012).
- **Alternatives considered**: Un UUID autogenerado en un archivo dentro de la carpeta de videos (cambia si se cambia la carpeta). El hostname (puede revelar el nombre de la persona).

## R7. Disponibilidad del video en el equipo actual (FR-009)

- **Decision**: `GET /sessions/{id}` calcula `video.availability`:
  - `missing`: el archivo no existe.
  - `mismatch`: el tamaño o el SHA-256 difieren de los registrados.
  - `available`: coinciden.
  - `not_configured`: falta `FLOWSIGHT_VIDEOS_DIR`.
  
  El SHA-256 del archivo local se cachea en memoria del proceso API con la clave `(ruta, tamaño, mtime_ns)`, así que solo se recalcula si el archivo cambia. El listado de sesiones no informa disponibilidad.
- **Rationale**: Cumple el texto de FR-009 (existencia + hash) sin rehashear gigabytes en cada consulta. El listado queda liviano.
- **Alternatives considered**: Solo existencia y tamaño (no detecta un archivo reemplazado con igual tamaño). Un archivo de caché persistente en la carpeta (más estado local que mantener).

## R8. Cámaras registradas y migración de sesiones sintéticas

- **Decision**:
  - **Tabla `cameras`**: `name` (el texto que se muestra) y `name_key = casefold(strip(name))`, con UNIQUE sobre `name_key` (FR-002).
  - **`sessions`**: suma `registered_camera_id` (FK NOT NULL a `cameras`). La columna de texto `sessions.camera_id` se conserva como clave de trazabilidad de las FK compuestas de specs/002. En sesiones de video se completa con `cameras.name`.
  - **Migración `0002`**: agrupa las sesiones existentes por `lower(btrim(camera_id))`. Dentro de cada grupo, cada `camera_id` original distinto (ordenado por la primera `created_at`) genera una cámara. La primera conserva el nombre; las siguientes reciben el sufijo ` (2)`, ` (3)`, etc., truncado a 120 caracteres. Cada conflicto se informa con `logger.warning` de Alembic, con los nombres involucrados. No se fusionan sesiones y no se modifica `sessions.camera_id`.
  - **Compatibilidad**: `POST /sessions` (sintético) conserva su contrato con `camera_id` de texto y hace *get-or-create* de la cámara por `name_key` (`INSERT … ON CONFLICT DO NOTHING` + `SELECT`).
  - **Alcance MVP**: no se renombran ni borran cámaras, y una sesión no cambia de cámara (CHK002, CHK003).
- **Rationale**: Renombrar la columna `camera_id` obligaría a reescribir las FK compuestas de `synthetic_frames`, `observations` y `events`, lo cual es un refactor ajeno. El sufijo cumple la clarificación "renombra la cámara que choca, sin perder datos".
- **Alternatives considered**: Reemplazar `camera_id` por un UUID en todas las tablas (demasiado grande para el MVP). Fusionar cámaras que chocan (lo prohíbe la clarificación).

## R9. Enums de PostgreSQL y migración reversible en tests

- **Decision**: `ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'video_file'` y `ALTER TYPE job_kind ADD VALUE IF NOT EXISTS 'video_analysis'` corren al inicio de `0002`, dentro de `op.get_context().autocommit_block()`: el bloque confirma los valores antes de que siga la migración, así que el resto de `0002` ya puede usarlos, por ejemplo en CHECKs. El `downgrade()` de `0002` borra tablas y columnas nuevas y deja los valores de enum; el `downgrade` de `0001` elimina los tipos completos. Ese `downgrade` existe solo para las fixtures de pytest, que hacen `downgrade base` / `upgrade head`. La regla operativa no cambia: nunca se hace `downgrade` para recuperar un entorno (CHK010). Si `0002` falla a mitad de camino, PostgreSQL revierte el DDL transaccional; se corrige la causa y se vuelve a correr `upgrade head`.
- **Rationale**: PostgreSQL no permite usar un valor de enum recién agregado en la misma transacción. Los tests existentes dependen de que el downgrade funcione.
- **Alternatives considered**: Recrear los enums con `CREATE TYPE … RENAME` (más riesgoso sobre la base compartida de Azure).

## R10. Modelo de versiones, locales con identidad estable e inmutabilidad

- **Decision**:
  - **Tablas**: `scene_versions` (por cámara, `version_number` secuencial), `shops` (identidad estable por cámara), `scene_version_shops` (nombre y pertenencia de un local en una versión), `scene_zones` (rol `interior|front|showcase`, polígono JSONB) y `scene_entry_lines` (una por local en la versión).
  - **Numeración**: se toma `SELECT … FOR UPDATE` sobre la fila de `cameras` y luego `max(version_number) + 1`, con UNIQUE `(camera_id, version_number)` como red de seguridad. Así dos guardados concurrentes reciben números distintos y no quedan huecos por concurrencia (CHK011).
  - **Inmutabilidad**: un trigger `BEFORE UPDATE OR DELETE` en las cuatro tablas de escena lanza una excepción. La API no expone `PUT`, `PATCH` ni `DELETE` (FR-023, SC-006, CHK036). `TRUNCATE` de las fixtures de test no dispara triggers de fila.
  - **Identidad de locales**: en la request, cada local trae un `shop_id` opcional. Si lo trae, tiene que ser de la misma cámara y no puede repetirse en la versión; si no lo trae, se crea un local nuevo.
  - **Nombres**: unicidad por versión con la misma normalización que las cámaras (`casefold(strip)`, CHK013).
  - **Topología**: una línea por local (FR-016, CHK022); la geometría no se comparte entre locales (CHK023); la vidriera no necesita relación geométrica con la frontal (CHK024).
- **Rationale**: Las tablas con FK compuestas `(…, camera_id)` repiten el patrón de aislamiento de specs/002 (FR-029). Guardar el polígono en JSONB alcanza porque nunca se consulta por vértice.
- **Alternatives considered**: Un único documento JSONB por versión (no se puede reforzar la identidad de los locales ni el aislamiento con FKs). Una tabla de vértices (sin beneficio de consulta).

## R11. Geometría: coordenadas, tolerancias y convención A/B

- **Decision**: El módulo puro `flowsight/scene/geometry.py` valida en píxeles del frame de referencia: `x_px = x · frame_width` y `y_px = y · frame_height`.
  - **Rango**: cada coordenada en [0, 1], cerrado (CHK025).
  - **Polígono**:
    - tiene entre 3 y 64 vértices (CHK020);
    - la distancia entre vértices consecutivos es > 2 px, incluida la arista de cierre, y los repetidos se rechazan;
    - las aristas no adyacentes no se cruzan ni se tocan. Se usa el test de orientación con colineales, igual que `segments_intersect` del experimento; los vértices colineales dentro de una arista se aceptan (CHK027);
    - el área de Shoelace es ≥ 100 px²;
    - la orientación horaria o antihoraria da lo mismo y se guarda tal como se dibujó (CHK021).
  - **Línea**: longitud ≥ 10 px.
  - **Lados A/B**: `cross = (end − start) × (p − start) = dx·(py − sy) − dy·(px − sx)` en coordenadas de imagen (y hacia abajo); `cross > 0` es el lado **A** (derecha del vector) y `cross < 0` es **B**. Se verificó con `scene.example.json`: `start (500,850)`, `end (1400,850)` y `p (950,1000)` dan `cross = +135000`, que es A. Como la normalización escala x e y por factores positivos, conserva el signo (CHK018, CHK019). El cruce contra el segmento se evalúa recién en #63 (CHK032).
  - **Precisión**: las coordenadas se guardan como `double precision`, redondeadas a 6 decimales; 1e-6 × 3840 px es mucho menos que la tolerancia de 0,5 % de SC-004 (CHK029, CHK030).
  - **Advertencias** (no bloquean y no se persisten, CHK033): la línea no toca ni cruza la zona frontal ni la interior del local (`line_not_touching_zones`); zonas de locales distintos que se superponen (`zones_overlap`); la versión base del editor ya no es la última (`newer_version_exists`, CHK034).
  - **Relación de aspecto (FR-028, CHK028)**: se bloquea si `|(w_v / h_v) / (w_f / h_f) − 1| > 0.01`, donde `v` es el video de la sesión y `f` el frame de la versión.
- **Rationale**: Las tolerancias en píxeles son las de la clarificación. La función de lados replica `classify_line_sides` del experimento para que #63 reutilice la misma convención.
- **Alternatives considered**: Shapely (dependencia nueva para cuatro funciones de ~60 líneas en total).

## R12. Trabajos de análisis de video (FR-025 a FR-028)

- **Decision**:
  - **Tipo de trabajo**: se agrega `JobKind.video_analysis`. `POST /sessions/{id}/jobs` exige `scene_version_id` para sesiones de video y lo prohíbe para las sintéticas (CHK008), y valida en este orden:
    1. la cámara tiene al menos una versión (`scene_not_configured`, 409);
    2. la versión es de la misma cámara (`scene_version_other_camera`, 422);
    3. la relación de aspecto coincide (`aspect_ratio_mismatch`, 409).
  - **`processing_jobs`**: suma `scene_version_id` y `registered_camera_id`, ambos nullable. Tiene FK compuestas `(session_id, registered_camera_id) → sessions(id, registered_camera_id)` y `(scene_version_id, registered_camera_id) → scene_versions(id, camera_id)`, y un CHECK: `(kind = 'video_analysis') = (scene_version_id IS NOT NULL)`. Ese CHECK se agrega en la misma `0002`, después del bloque autocommit del enum (R9).
  - **Worker**: `claim_next_job` filtra por los tipos que el worker sabe procesar (`synthetic_base_flow`). Los trabajos `video_analysis` quedan en `pending` hasta que #56 agregue su handler.
  - **Preselección**: la hace la UI con la última versión (`GET /cameras/{id}/scene-versions`, orden descendente); la API no elige una versión por defecto.
- **Rationale**: La compuerta y la asociación trabajo → versión son el alcance de esta feature. Filtrar el claim evita que el worker actual marque como fallidos trabajos que todavía no sabe procesar.
- **Alternatives considered**: Que el worker falle con `unsupported_job_kind` (genera fallos que no son reales). No crear trabajos de video hasta #56 (US2 escenarios 5 a 8 quedarían sin probar).

## R13. Frontend: navegación, editor SVG y pruebas

- **Decision**:
  - **Navegación**: un router mínimo propio en `App.tsx`, con `window.location.pathname` y `history.pushState`, para `/`, `/sessions/:id` y `/sessions/:id/editor`. Se conserva `?job=` para `JobPreviewPage` (el E2E existente lo usa). No se agrega `react-router`.
  - **Editor**: `<svg viewBox="0 0 W H" preserveAspectRatio="xMidYMid meet">` con `<image href="…/reference-frame">`. Todo el estado se guarda en píxeles del frame, y el puntero se convierte con `getScreenCTM().inverse()`. Redimensionar la vista no toca el estado (FR-033, SC-004); se normaliza solo al guardar.
  - **Controles**: nativos y accesibles (FR-036):
    - `<button>` para crear zona o línea, eliminar y guardar;
    - `<select>` para local y rol;
    - `<fieldset>` con radios para el sentido de entrada;
    - cada vértice es un `<circle>` con `role="button"`, `aria-label` y `tabIndex=0`, que se mueve con flechas (1 px, o 10 px con Shift).
  - **Sentido de entrada**: una flecha marca el sentido de entrada, y las etiquetas "A" y "B" se ubican a ±20 px de la normal en el punto medio.
  - **Errores**: los de la API traen `shop_index`, `element` y `rule`, y se mapean al elemento dibujado sin descartar el estado (FR-034).
  - **Cambios sin guardar** (FR-035): `beforeunload`, más `window.confirm` al navegar dentro de la app.
  - **Pruebas**: Vitest para conversiones de coordenadas y reducers del editor. Playwright para el recorrido: registrar video, dibujar, redimensionar, guardar y verificar las coordenadas vía API.
- **Rationale**: Es SVG sobre el frame, como fija el stack acordado. Con `viewBox` en píxeles del frame, la correspondencia al redimensionar viene gratis. Tres rutas no justifican una dependencia.
- **Alternatives considered**: Canvas 2D (lo descarta el stack acordado, y los vértices no quedan accesibles). `react-router` (dependencia nueva).

## R14. Video de prueba sin subir videos a Git

- **Decision**: Se agrega el helper `backend/src/flowsight/video/fixtures.py`, que genera con `cv2.VideoWriter` clips cortos y deterministas (MJPG `.avi`, `mp4v` `.mp4`, 1280×720 y 640×480, 2 s) en un directorio temporal. Pytest lo usa, y `frontend/e2e/run-e2e.mjs` lo invoca a través del venv del backend. Los archivos inválidos (vacío, texto con extensión `.mp4`, truncado) se generan en el test.
- **Rationale**: AGENTS.md prohíbe subir videos a Git, y CI necesita casos reales para decodificar.
- **Alternatives considered**: Un video diminuto versionado (viola la regla del repo).
