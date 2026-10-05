# Data model: webcam en vivo

Diseño aditivo, 2026-10-03. Todas las tablas nuevas usan PostgreSQL/SQLAlchemy existentes. No se crean `VideoSource`, snapshots ni JSONL de trayectorias para webcam.

## Entidades existentes

- `Session.source_kind`: agregar `webcam`. Conservar `camera_id` textual de trazabilidad y `registered_camera_id` UUID; cámara lógica no se identifica por índice USB. Webcam conserva `ReferenceFrame` bytea asociado a sesión; frame de preparación tiene índice 0/timestamp 0 y contexto de referencia, no evento analítico.
- `ProcessingJob.kind`: agregar `live_analysis`; conservar status `pending/processing/completed/failed/cancelled`. Reemplazar `ck_processing_jobs_video_analysis_scene` para exigir scene+camera en video_analysis **o** live_analysis, sin exigirlas para synthetic_base_flow. Mantener FK compuestas y check result_complete/status.
- `ProcessingJob.target_machine_id`: nullable para registros antiguos; nuevos archivos/live registran equipo propietario. No cambia `claimed_by` (worker_id). Recovery de jobs antiguos processing sin target solo si claimed_by corresponde al worker recuperado; no tocar trabajos de otro equipo.
- `ReferenceFrame` y `SceneVersion`: mismo editor, validators, inmutabilidad y baja lógica. Preparación crea sesión/frame antes de escena. No sobrescribir frame si ya es referencia de escena.
- `AnalysisMeasure`, `LineCrossing`, `SceneEvent`, `ShopMetric`, `TrafficBucket`: conservar sin reinterpretar para webcam; sus lecturas de archivos siguen intactas. Vivo consulta tablas específicas.

## WorkerMachine (`worker_machines`)

- `machine_id` PK, formato existente; `worker_id`, `owner_epoch` UUID, `heartbeat_at` UTC, `capture_state` (`idle/probing/analyzing`), `reservation_id` UUID nullable, `reserved_until` UTC nullable.
- Afinidad de todos los nuevos jobs con su `target_machine_id`. Worker mantiene conexión dedicada con advisory lock por hash estable de machine_id; si no lo obtiene, no ejecuta recovery ni toma dispositivos.
- Heartbeat cada 1 s, vencimiento 5 s; esto describe disponibilidad, no continuidad observada. Claim conserva lock mientras ejecuta y comprueba lease propio.
- API reserva fila de máquina mediante SELECT FOR UPDATE: rechaza jobs pendientes/procesando del equipo o reserva vigente; reserva de probe vence en 10 s y se libera al finalizar/expirar.
- Orden de locks para control nuevo: máquina → sesión (si ya existe) → cámara → job. Mantener locks de retiro existentes; servicios de vivo y claim no invierten sesión/cámara. Archivo solo toma reserva de máquina antes de su validación existente.
- Registro no contiene secretos, URLs de cámara ni JPEG. Reservas no equivalen a job activo y no aparecen como análisis.

## LiveSource (`live_sources`)

- `session_id` PK/FK sessions, `machine_id`, `device_index` >=0 y en allowlist, `capture_backend` (`dshow/msmf/auto/fake`), `width/height` positivos ≤1920×1080, `reported_fps` nullable diagnóstico, `prepared_at` UTC.
- `label_mode` (`directions/access`), por defecto directions; mapea etiquetas por escena, sin cambiar EntryDirection. Frame/reference determina proporción.
- `frame_checked_at` nullable y token efímero en RAM, nunca persistir token. El check retorna preview transitorio; el único JPEG durable es el frame de referencia inicial.
- Sin filename/path/hash/duración total. Abandono deja sesión preparada sin jobs; liberar dispositivo siempre. Retomar hace check y confirmación de encuadre.
- Validación en servicio y constraint trigger diferible de pertenencia: LiveSource requiere Session.source_kind=webcam y cámara activa para crear; origen no se cambia después de crear. Checks DB preservan datos retirados, no borran históricos.

## LiveAnalysisState (`live_analysis_states`)

- `job_id` PK, `session_id`, `machine_id`; FK `(job_id,session_id)` a ProcessingJob y source de la misma sesión; kind=live_analysis validado por trigger/servicio.
- `capture_status` (`starting/connected/interrupted/awaiting_confirmation/stopping/ended`); status de transporte/captura no agrega valores a JobStatus.
- `capture_started_at` UTC nullable hasta primer frame válido, `capture_ended_at` UTC nullable; `elapsed_capture_seconds` Numeric(12,6) >=0 del último checkpoint; `last_capture_sequence` BigInteger >=0, `last_analyzed_sequence` nullable, `current_segment_index` >=0.
- `stop_requested_at` UTC nullable, `retry_requested_at` UTC nullable, `resume_confirmed_at` UTC nullable, `checkpoint_at` UTC, `revision` BigInteger monótona.
- `coverage_complete` bool, `unknown_tail` bool, `observed_seconds/missing_seconds` no negativos; closed duration es el tiempo de captura de la sesión hasta stop, incluye huecos conocidos. Al fallar sin fin conocido, duration es hasta último checkpoint y unknown_tail=true.
- `detector_parameters` JSONB documentado (modelo/tracker/precisión/window/gap), `unconfirmed_crossings` contador diagnóstico, `sample_candidates_seen` BigInteger y `sample_capacity=20000`.
- FPS/latencia son runtime/diagnóstico; no métricas comerciales. `ProcessingJob.frames_total=NULL`, progreso porcentual no aplica; frames_analyzed es cantidad observada y no representa duración.
- Stop normal marca result_complete=true y completed, independientemente de coverage_complete. Fallo marca result_complete=false/failed; no replay ni nuevo live job sobre esa misma sesión cerrada. Nuevo análisis webcam crea sesión nueva.

## LiveCaptureSegment (`live_capture_segments`)

- `id` UUID, `job_id/session_id`, `segment_index` int, `started_capture_seconds`, `ended_capture_seconds` nullable, `first_sequence`, `last_sequence` nullable, `reason` (`initial/reconnected/analysis_gap`).
- UNIQUE(job_id,segment_index); FK `(job_id,session_id)` y UNIQUE(id,job_id,session_id). No se superponen segmentos; ID raw pertenece a este contexto, no a identidad real.
- El primero comienza en timestamp 0. Reanudar crea otro segmento y reset de tracking; nunca unir posiciones de segmentos distintos.

## LiveInterruption (`live_interruptions`)

- `id` UUID, `job_id/session_id`, `start_seconds`, `end_seconds` nullable, `reason` (`capture_lost/analysis_gap/awaiting_confirmation/worker_interrupted/database_unavailable`), `end_known` bool.
- FK compuesta a job/session; bounds no negativos y end>=start. Un intervalo abierto se cierra al reanudar o detener con captura reloj aún disponible; recovery solo conoce el último checkpoint y marca cola unknown.
- Para buckets unir intervalos superpuestos, no sumar pérdida dos veces. Razones pueden coexistir como diagnóstico, cobertura usa su unión.

## LiveCrossing (`live_crossings`)

- `id` UUID, `job_id/session_id`, `segment_id`, `shop_id`, `track_id` BigInteger, `candidate_sequence` BigInteger, `capture_sequence`, `capture_timestamp_seconds`, `confirmed_at_capture_seconds`, `direction` (`entry/exit`), `foot_x/foot_y` en [0,1].
- Unicidad `(job_id,candidate_sequence)`; candidate_sequence asignada por contador del job y conservada al reintentar flush. No persistir eventos de cada detección; solo cruces confirmados.
- FK `(segment_id,job_id,session_id)` y `(job_id,session_id)`; constraint/servicio exige shop de scene_version del job. Cruce de otro local/cámara no se admite. Tiempo original y confirmado se distinguen.
- Eventos históricos de webcam son estos hechos de cruce; no generan store_enter/pasos/permanencia de 006. Oscilaciones descartadas quedan como conteo diagnóstico, no eventos confirmados.

## LiveCrossingBucket (`live_crossing_buckets`)

- PK `(job_id,shop_id,bucket_index)`; `session_id`, `start_seconds=60*index`, `end_seconds`, `entries/exits` >=0, `observed_seconds/missing_seconds` en [0,60], `pending_count` >=0, `is_open`, `coverage_incomplete`, `unknown_tail`, `revision`.
- Suma de duración conocida por bucket hasta checkpoint ≤60; campo abierto no implica pérdida. Campos agregados por timestamp original de cruces, con upsert transaccional deltas exactly-once usando candidate_sequence.
- Mismos minutos sin personas son cero **solo con cobertura válida**. Confirmación tardía actualiza el bucket previo y la revisión. No sumar buckets de distintos locales como personas.
- Leer historial con paginación de 250 buckets; preview manda últimos 60 buckets por local, máximo 20 locales. Final no contiene candidatos pendientes: se confirman vencidos o se descartan restantes y se etiqueta el diagnóstico.

## LivePositionSample (`live_position_samples`)

- PK `(job_id,slot_index)` con 0≤slot<20000, `session_id`, `segment_id`, `track_id`, `capture_sequence`, `capture_timestamp_seconds`, `foot_x/foot_y` en [0,1]. FK compuestas de segmento/job/session.
- Una candidatura por track/segmento por segundo; reservoir reemplaza slots uniformemente entre candidaturas. No almacenar bbox/JPEG ni IDs reales. RNG inyectado; no se promete reconstrucción exhaustiva.
- API devuelve ≤2000 muestras distribuidas por slots ocupados; incluye sample_count/candidate_count/capacity y etiqueta temporal de captura. No guardar resultado de mapa como imagen; frontend dibuja sobre reference_frame.
- SQL constraints acotan filas por job (slot range+PK); memoria incluye reservoir y dirty slots, ambos ≤20000. Inactive track metadata TTL1 s y máximo2048; excederlo descarta continuidad y registra limitación.

## Migración y compatibilidad

1. `0009_live_capture` (down_revision 0008_scene_configuration_removal): ADD VALUE webcam/live_analysis a enums con commit seguro.
2. `0010_live_capture_schema`: tablas nuevas, target_machine_id, constraint de escena ampliada y FKs/índices. No modificar ni borrar escenas inmutables ni nombres retirados.
3. Actualizar desde 0008 dos veces en PostgreSQL local y confirmar que referencia/frame/retiradas y resultados de archivos permanecen idénticos; test específico de inserts con enum nuevo.
4. Downgrade solo en tests guardados: borrar tablas/columns nuevas y restaurar checks previos después de retirar fixtures live; conservar valores enum como patrón0004. No usar rollback destructivo operacional.

## Ciclo

Preparar → sesión+frame sin job → guardar/elegir escena → check frame y confirmar → job pending → claim local → processing/starting → primer frame timestamp0 → connected.

Interrupción no termina job: interrupted → retry abre dispositivo → awaiting_confirmation (preview solo en RAM, no conteo) → operador confirma encuadre → nuevo segmento connected. Retry automático 1/2/5 s por tres intentos, luego esperar acción; no reanudar métricas sin confirmación.

Stop → stopping → liberar captura → resolver frame en curso/candidatos vencidos → flush final → completed/ended. Camera perdida no bloquea stop. Fallo/caída → failed/ended, conservar último checkpoint y cobertura incompleta, no auto-resume.
