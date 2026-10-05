# Research: webcam en vivo

Fecha: 2026-10-03. Investigación de código y documentación primaria; sin instalación, hardware ni pruebas de rendimiento. Los límites siguientes son decisiones iniciales de diseño, no resultados medidos.

## R1 · Fuente y preparación

**Decision**: `SourceKind.WEBCAM` y `JobKind.LIVE_ANALYSIS`; un adaptador `FrameSource` entrega imagen, secuencia, segmento y tiempo de captura. Preparar es una operación de control del worker, sin crear un `ProcessingJob`. El worker recibe solicitud por WS local, abre/cierra la cámara y devuelve un único frame en memoria; la API registra sesión/LiveSource/ReferenceFrame en una transacción al recibirlo.
**Rationale**: `SceneVersion.reference_session_id` exige sesión previa. OpenCV corre donde está el dispositivo, no en el navegador. El mismo worker serializa probes y análisis; una cámara no es abierta a la vez por API y worker.
**Alternatives considered**: `getUserMedia` requeriría mover frames desde navegador; abrir OpenCV en API crearía competencia; un job de análisis durante configuración contradice preparación sin análisis.

Dispositivos: enumeración de monikers DirectShow de Windows, FriendlyName y orden nativo compatible con OpenCV DSHOW. Solo se muestran dispositivos detectados (incluidos virtuales), hasta33/índices0–32, no candidatos inventados. Helper aislado con timeout3s, sin abrir captura y una enumeración activa; errores explícitos. Selección y Actualizar cámaras en UI, sin dispositivo en .env. Los índices no son identidad USB estable: confirmar encuadre al iniciar/reconectar. El registro de cámara lógica sigue separado. En tests fake con ENVtest se muestra una sola cámara simulada, identificada como tal. Implementado por pedido adicional aprobado del usuario2026-10-05.

## R2 · Captura desacoplada y lectura bloqueante

**Decision**: OpenCV en auxiliar `multiprocessing` con contexto `spawn`. Un hilo de captura dentro del auxiliar sobrescribe un slot compartido acotado; el worker copia únicamente una secuencia nueva y analiza fuera del lock. El auxiliar no importa/carga YOLO. Se conserva un frame pendiente, otro en análisis y scratch de captura; sin cola de frames.
**Rationale**: Los timeouts de lectura documentados por OpenCV 4.10 solo aplican a FFmpeg/GStreamer, no garantizan cerrar una webcam Windows. Un thread no puede interrumpir con seguridad una llamada nativa bloqueada. Aislar la captura permite terminar ese proceso sin matar API/worker.
**Alternatives considered**: Hilo dentro del worker es más corto pero deja lectura bloqueada sin cierre acotado; RTSP/servidor externo no es necesario para USB.

Windows: el selector por nombre enumera y abre con `CAP_DSHOW`, conservando el orden entre lista y captura; no cambiar silenciosamente a `CAP_MSMF` con otra enumeración. La función genérica de captura conserva soporte MSMF para adaptadores explícitos. Persistir backend efectivo. Pedir 1280×720; aceptar tamaño real hasta 1920×1080, positivo y BGR8; si excede límite, rechazar con mensaje de configuración. El frame de referencia y la fuente deben tener mismo encuadre; una resolución diferente requiere finalizar y preparar una escena nueva; no se reanuda la escena antigua aun con proporción compatible (alineado con spec).

Slot raw máximo 1920×1080×3 bytes (~6 MiB) con metadatos escalares y lock de timeout 50 ms; lock solo para copiar, nunca inferir. Si lock/lectura se atasca, descartar esa generación y crear un auxiliar nuevo. `probe_timeout=5 s`, watchdog sin frame nuevo `3 s`, cierre cooperativo `1 s` y terminación/join `1 s` adicional. Recursos IPC nuevos después de terminar forzosamente: no reutilizar un lock potencialmente retenido. Memoria compartida es volátil; cerrar todos los handles incluso ante excepción. Para la prueba SC-003, medir explícitamente frames pendientes e in-flight, no temporales de OpenCV como cola.

## R3 · Visión aprobada y reglas de vivo

**Decision**: Conservar `yolo11m.pt`, ByteTrack, persons `[0]`, `persist=True`, selección CUDA/CPU y `quantize=16` ya existentes. Agregar `Detector.reset_tracking()`; Ultralytics resetea únicamente los trackers inicializados y no recarga pesos. Fake implementa reset determinista. Mantener GPU inferencia en el worker, nunca en el auxiliar.
**Rationale**: Modelo chico no fue validado para esta escena; reset sin volver a cargar pesos evita duplicar VRAM al reconectar. El detector actual no tiene reset y los contadores de archivos usan frames y `finish()`.
**Alternatives considered**: Reconstruir YOLO por segmento duplicaría costo y podría retener VRAM; cambiar pesos/ONNX/OpenVINO agrega una evaluación distinta.

`LiveSpatialCounter` independiente: misma geometría de pies normalizados, segmento y lados A/B; `oscillation_window_s=1/3` inicial (equivalente a 10 frames a 30 Hz, no afirmación de adecuación universal). Confirmar al superar estrictamente el límite; el cruce opuesto a ≤ventana cancela candidatos de ambos sentidos. Retorno después de ventana es válido, sin cooldown general. `max_observation_gap_s=1`, descartar continuidad y candidato del track ante ausencia/interrupción/gap superior; no asumir presencia en ese hueco. `advance()` procesa vencimientos con reloj de captura ya recibido: nunca fabricar eventos usando tiempo de procesamiento. Al detener, confirmar solo candidatos que vencieron antes del último tiempo observado continuo; descartar restantes, contabilizar candidatos no confirmados en diagnóstico. Perder un track antes de confirmarlo descarta el candidato.

Reinicio global de segmento/tracker si gap de análisis supera 1 s o capture se interrumpe; en vez de unir posiciones distantes se registra intervalo no evaluable. `max_active_tracks=2048` y TTL 1 s en contador/sampler; exceso se diagnostica y rompe continuidad de los tracks descartados. Auditar también estado interno del tracker durante ensayo sostenido, no solo dict propio.

## R4 · Afinidad, control y resultados durables

**Decision**: Una sesión webcam pertenece a `machine_id` del worker. API y worker son locales en la misma PC y pueden usar DB local o compartida. Un registro `worker_machines` con lease y un advisory lock PostgreSQL por máquina impiden dos owners; fallo de adquirir el lock implica no recuperar ni reclamar trabajos. Establecer `target_machine_id` para trabajos nuevos de archivos y vivo; jobs antiguos sin target conservan el recorrido existente hasta ser reclamados.
**Rationale**: `claim_next_job` usa `skip_locked` por fila, que evita doble claim del mismo job pero no dos jobs simultáneos en una PC; la recuperación actual marca todos los processing, peligroso con base compartida.
**Alternatives considered**: Filtrar por worker_id no alcanza si cambian nombres o se abren dos procesos. No agregar cola externa.

API inicia bajo lock de fila de máquina, sesión y cámara en un orden documentado; el vivo no se admite si hay un trabajo pendiente/procesando del mismo equipo. Los archivos conservan su cola existente, pero se rechazan durante un vivo o reserva de preparación. Claim sigue permitiendo solo un trabajo en ejecución por equipo (corrección de compatibilidad detectada por E2E). Claim verifica afinidad, cámara/escena/sesión activas y lease. Recovery solo del mismo equipo/owner muerto; preservar otras PCs. Preparación no crea un job pero toma control de dispositivo únicamente cuando máquina está ociosa; no comparte inferencia con archivos.

Stop persistido (`stop_requested_at`) con respuesta 202 idempotente, consultado cada 200 ms por control thread; captura se cierra sin depender de inferencia. El cierre durable espera el frame en inferencia, guarda y transiciona a completado; no se garantiza un tiempo terminal si un backend de inferencia se bloquea. La UI muestra «Finalizando» hasta estado terminal, con diagnóstico si excede 10 s. Caída del worker → failed/worker_interrupted, sin auto-resume; petición stop pendiente se recupera como fallo si el worker murió.

Flush de datos cada ≤1 s desde última operación terminada y al cerrar; transacción única con cruces nuevos, buckets, muestra modificada y checkpoint. `lock_timeout=250 ms`, `statement_timeout=1000 ms` para writes live. Retry temporal sin duplicados, buffer ≤5 s/4096 hechos nuevos; si fallo DB supera 5 s o cap, detener captura, fallar y conservar último checkpoint durable. No prometer cero pérdida ante caída: hasta un intervalo de flush más la transacción en curso; cuando DB falla, cobertura/resultado quedan incompletos hasta checkpoint. La recuperación marca el hueco desconocido en vez de inventar duración exacta.

## R5 · Preview sin archivos

**Decision**: Worker productor conecta a WS interno local de FastAPI con `websockets` ya fijado; cola de envío size-one, task de publicación separado con timeout 500 ms y reconexión 1/2/5 s. API/broker RAM reemplaza último resultado y cada consumidor size-one; ninguna tabla ni snapshot almacena JPEG de preview.
**Rationale**: `preview/broker.py` no atraviesa procesos; el vivo no puede reutilizar `preview/snapshot.py`, que escribe `preview.json`.
**Alternatives considered**: Guardar JPEG en DB/disco viola no-recording; incorporar Redis/stream server agrega dependencias. Este WS transporta resultado analizado y control, no es servidor intermedio de captura.

Token local compartido solo por API/worker (`FLOWSIGHT_LIVE_CHANNEL_TOKEN`, SecretStr), ingress loopback, sin proxy ni credential/query logs. Validar producer `machine_id`, worker lease y `claimed_by`/job/session; un productor autorizado por equipo y token, mensajes ≤1 MiB, ignorar secuencias/revisiones viejas. No expone URLs arbitrarias ni conecta cámara IP. App sin token conserva archivos y devuelve live_not_configured. Un proceso Uvicorn para demo; no múltiples brokers independientes.

Preview máximo 5 Hz; JPEG reducido a ≤960×540 y ≤200 KiB (calidad adaptada), base64 más estadísticas ≤1 MiB. RAM último mensaje TTL 10 s; staleness visible después de 2 s. Hasta 8 observadores; slow send cierra socket tras 1 s sin bloquear al productor. Desconectar/reiniciar API no detiene worker mientras DB esté disponible; el siguiente mensaje es snapshot acumulado de valores, no incrementos. Estado terminal se recupera de DB aunque se pierda el último preview.

## R6 · Cruces por minuto y cobertura

**Decision**: Tablas live específicas; no `TrafficBucket`, `ShopMetric`, `SceneEventRecorder` ni `persist_completed_scene`. Entradas/salidas internas se proyectan a A/B según sentido configurado y etiqueta de acceso elegida por operador. Buckets relativos de 60 s con `entries`, `exits`, `observed_seconds`, `missing_seconds`, `pending_count` y flags abierto/incompleto independientes.
**Rationale**: Tráfico/flujo existentes son visitas estimadas por tracks, no cantidad de cruces. Confirmación tardía pertenece al tiempo original.
**Alternatives considered**: Cambiar TrafficBucket rompería significado del histórico y chat; gráficos nuevos no se calculan en frontend.

Cobertura: intervalos entre capturas válidas continuas hasta checkpoint; saltos de secuencia descartados no son necesariamente hueco de captura, pero gap >1 s entre observaciones de análisis es intervalo no evaluable. Interrupción desde última observación válida hasta primer frame aprobado de nuevo segmento. Períodos anteriores al primer frame válido no cuentan como captura analítica. Bucket abierto contiene duración hasta último checkpoint; pérdida solo donde existe intervalo conocido, y unknown_tail cuando worker cae. Un cruce confirmado corrige bucket anterior; UI mantiene `revision` creciente aun con misma secuencia para cambio solo de estadísticas. Total siempre suma ambos sentidos, no suma personas entre locales.

## R7 · Muestreo y mapa histórico

**Decision**: Una posición elegible por track/segmento cada 1 s de captura; reservoir uniforme global con `k=20000`, RNG inyectado para tests. Persistir slots reemplazables en DB y contador de candidatos; nunca imágenes ni cada frame. Muestras guardan timestamp, contexto y pie normalizado. Batch deltas en flush, memoria del reservoir y de cambios pendientes acotada por k.
**Rationale**: Writer JSONL actual cada quinto frame crece sin límite; conservar solo primeras posiciones sesgaría el final de una expo larga.
**Alternatives considered**: Guardar todo rompe límites; solo grilla no cumple muestra de posiciones elegida por usuario.

Mapa de sesión completa: endpoint de posiciones devuelve a lo sumo 2.000 slots distribuidos determinísticamente por el rango de slots ocupados, no las primeras 2.000 observaciones. `PositionHeatmap` existente renderiza como máximo 2.000 círculos; etiqueta muestra y razón 2000/N. Muestras no permiten inferir permanencia exacta, visitas únicas ni flujo. Si futura UI filtra intervalo se debe muestrear dentro del intervalo antes de limitar; esta entrega muestra mapa de toda la sesión, sin sumar filtros nuevos.

## R8 · UI/historia y contrato futuro IP

**Decision**: Páginas live separadas, origen discriminado en session/history y enlaces de activo. Reutilizar SVG/editor/scene validators y layout Split; `CrossingChart` propio, sin modificar `FlowChart` de tracks. Historial muestra cruces/duración/huecos/muestra y «Sin grabación». Chat devuelve `live_chat_unavailable` antes del modelo, incluso al resolver nombre/última sesión.
**Rationale**: `JobPreviewPage` asume progreso porcentual/cancelación y `SessionResultsPage` asume duración de archivo; ausencia de video se llama sintética actualmente.
**Alternatives considered**: Volver todo un dashboard genérico amplía refactor; mostrar ocho indicadores ausentes o recalcularlos amplía alcance.

Capas de `FrameSource` y mensaje de discontinuidad no dependen de device index; future IP adapter podrá proveer frames/tiempos/estado. Esta entrega no acepta URL, RTSP, credenciales de cámara ni túneles entre redes.

## R9 · Latencia verificable

**Decision**: Captura marca `time.monotonic_ns()` inmediatamente tras read exitoso; API/worker/auxiliar comparten reloj de PC en Python 3.11. Browser calibra `performance.now()` con 8 intercambios de reloj al conectar, usa muestra de menor RTT y repite cada 30 s. Medir edad al render `requestAnimationFrame`, guardar estimación y error ±RTT/2; nunca restar relojes sin calibrar. SC-002 usa cota superior estimada ≤2 s y declara muestras sin calibración como no medibles.
**Rationale**: UTC del navegador puede estar desajustada; capture-publication es solo parte de captura-pantalla. Timestamp es tiempo de recepción del frame en OpenCV: la latencia no incluye tiempo interno sensor/driver desconocido.
**Alternatives considered**: Solo medir inferencia no verifica la demo; reloj de pared sin corrección confunde hosts.

FPS y métricas técnicas en ventanas de 5 s; clock control usa tiempo operativo únicamente para rendimiento, separado de timestamps de negocio. Evidencia guarda números agregados anonimizados, no frames ni identificadores personales.

## R10 · Migraciones y gobierno

**Decision**: `0009_live_capture` agrega enums mediante `autocommit_block` para ADD VALUE; `0010_live_capture_schema` crea tablas/constraints y checks para escenas de video o live. `alembic upgrade head` debe poder actualizar desde 0008 incluso si el motor agrupa revisiones en una transacción. Downgrade de tests elimina tablas pero deja enum values, como 0004; no usar downgrade como recuperación operativa.
**Rationale**: PostgreSQL no permite usar inmediatamente un enum recién agregado sin commit. Las migraciones son aditivas y no alteran escenas/retiradas.
**Alternatives considered**: Renombrar valores existentes o vaciar datos rompe histórico; migración destructiva no autorizada.

Constitución 1.0.2 aclara tiempo observado de captura en III; AGENTS.md y decisiones técnicas alineados, sin prometer implementación. Por instrucción del usuario, esta feature no se vincula ni publica en Azure Boards: es un agregado para la expo, fuera del TP. Pruebas y guías conservan guard de base local.

## Fuentes primarias consultadas

- [OpenCV 4.10 · propiedades y backends](https://docs.opencv.org/4.10.0/d4/d15/group__videoio__flags__base.html): alcance limitado de read/open timeouts.
- [websockets · cliente asyncio](https://websockets.readthedocs.io/en/latest/reference/asyncio/client.html): librería cliente ya presente; envío en tarea cancelable con timeout.
- [PostgreSQL 17 · ALTER TYPE](https://www.postgresql.org/docs/17/sql-altertype.html) y [Alembic · autocommit_block](https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.autocommit_block): commit requerido antes de usar valores nuevos de un enum.
- [Python 3.11 · relojes](https://docs.python.org/3.11/library/time.html): reloj monótono compartido entre procesos Windows desde 3.10.
- [Python 3.11 · multiprocessing](https://docs.python.org/3.11/library/multiprocessing.html): contexto spawn y recursos de procesos.

Evidencia local: `db/models.py`, `services/jobs.py`, `worker/lifecycle.py`, `video/decode.py`, `vision/spatial.py`, `vision/ultralytics_tracker.py`, `preview/broker.py`, `preview/snapshot.py`, `services/position_samples.py`, frontend navigation/páginas/tipos, locks y runner E2E. No se ejecutaron pruebas de producto durante research.
