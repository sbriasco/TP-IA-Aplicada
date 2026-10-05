# Contratos REST y WebSocket: webcam

Contrato implementado y revisado 2026-10-05; ver validation/implementation.md para pruebas y límites. JSON validado con Pydantic, extra=forbid, números finitos, UUIDs, tiempos no negativos. Frontend discrimina `source_kind`/`type`/`schema_version` y valida runtime antes de modificar estado.

## REST nuevo

| Método / ruta | Entrada | Respuesta |
|---|---|---|
| GET `/live/devices` | sin parámetros | 200 machine_id, worker_available, candidates:[{device_index,label,verified:false}]; dispositivos detectados por nombre, enumeración serial sin abrir streams |
| POST `/live/sessions` | name, registered_camera_id, device_index, label_mode:`directions/access` | 201 sesión webcam preparada + live_source + reference_frame metadata; probe5 s por control del worker antes de transacción de creación |
| POST `/sessions/{id}/live/check` | sin cuerpo | 200 frame transitorio JPEG base64, dimensions, backend, check_token y expires_in_seconds=60; cámara se libera al terminar |
| POST `/sessions/{id}/live/start` | scene_version_id, check_token, frame_confirmed:true | 201 job live_analysis pending; reserva/admisión de máquina, validación escena y consumo token atómico |
| POST `/jobs/{id}/live/stop` | sin cuerpo | 202 job_id, stop_requested_at, status; idempotente, no pasar directamente a completed desde API |
| POST `/jobs/{id}/live/retry` | sin cuerpo | 202 retry_requested_at; solo en interrupted/awaiting_confirmation, no revive jobs terminales |
| POST `/jobs/{id}/live/confirm-resume` | check_token, frame_confirmed:true | 202 solicitud de reanudación; token de segmento/probe actual, valida identidad de job y dimensiones |
| GET `/jobs/{id}/live-results` | shop_id opcional; bucket_cursor opcional | 200 snapshot durable del último checkpoint, summary del local, minutes paginados hasta250, interruptions, coverage, sampling metadata, estado |
| GET `/jobs/{id}/live-events` | shop_id opcional, from_seconds/to_seconds opcionales, cursor, limit≤250 | cruces confirmados ordenados por timestamp original/candidate_sequence; sin eventos de zona/comercio adicionales |

Endpoints de config/cámaras/referencia siguen existentes. Preparar requiere cámara lógica registrada; crear cámara se hace por el endpoint actual. En nueva preparación no se crea job. No sustituir reference frame al usar live/check.

GET live-results sin shop_id selecciona primer local de escena y retorna selected_shop_id; no devuelve un total de personas sumando líneas. Summary: `entry_count`, `exit_count`, `a_to_b_count`, `b_to_a_count`, `total_crossings`, `partial` y `label_mode`. Matemática exacta: total=entry+exit=a_to_b+b_to_a; scene.entry_direction define mapeo.

Snapshot: job_id, session_id, source_kind=webcam, status, capture_status, result_complete, coverage_complete, unknown_tail, capture_started_at/ended_at, elapsed_capture_seconds, checkpoint_at, revision, summary, minutes, interruptions, unconfirmed_crossings. Bucket: shop_id, bucket_index, start_seconds/end_seconds, counts por sentido, observed_seconds, missing_seconds, pending_count, is_open, coverage_incomplete, unknown_tail, revision. Minutos de 60 s relativos, no reloj de pared ni visitas estimadas.

## Extensiones compatibles

- GET `/sessions/{id}` agrega `live_source` nullable; webcam: video=null y reference_frame disponible. No cambiar video_file/synthetic ni devolver archivo ausente cuando nunca hubo archivo.
- GET `/processed-sessions` agrega source_kind, live_duration_seconds y coverage_complete nullable; filename=null significa «Sin grabación» solo para webcam. Sesiones preparadas sin trabajo se ven como preparación, sin filas ficticias de análisis terminado.
- GET `/jobs/{id}` agrega target_machine_id y live_state nullable; webcam frames_total=null, progress_percent=null. Archivo sigue calculando porcentaje como antes.
- GET `/jobs/{id}/position-samples`: video conserva shape actual; live agrega source_kind=webcam, time_basis=capture, sample_count, candidate_count, returned_count, capacity y samples:[{capture_timestamp_seconds,foot:[x,y]}], máximo2000. No reutilizar video_timestamp_seconds para fingir un video. No exponer track_id en el mapa.
- Cancel de archivos conserva semántica; si se invoca cancel sobre live responder409 `use_live_stop`. No permitir crear live por endpoint genérico omitiendo check/confirmación; `create_job_for_session` soporta kind/source pero admisión viene de live/start.
- Herramientas/chat al resolver una webcam responden `live_chat_unavailable` antes de llamar al LLM; no elegir otra sesión silenciosamente. Sesión retirada se comporta como404 salvo frame referenciado por escena, como hoy.

## Errores

Envelope común `{code,message}` con detalles no sensibles cuando corresponda. 422 para entrada inválida/índice fuera de allowlist; 404 sesión/job no visibles; 409 `machine_busy`, `camera_removed`, `scene_version_removed`, `scene_version_other_camera`, `aspect_ratio_mismatch`, `encuadre_confirmation_required`, `check_expired`, `live_already_started`, `use_live_stop`; 503 `worker_unavailable`, `live_not_configured`, `database_unavailable`, `device_unavailable`; 504 `capture_open_timeout`.

Stop terminal es idempotente200 con estado terminal sin mutaciones; stop pending devuelve202 y se atiende al claim sin capturar si aún no empezó. Worker sigue pending→processing→completed, observa stop antes de abrir fuente/cargar modelo y crea cierre normal de duración0 sin datos observados. No agregar transiciones especiales; probar el cierre previo a captura.

## WS interno productor/control

`/ws/internal/live/{machine_id}` es loopback; header `Authorization: Bearer <FLOWSIGHT_LIVE_CHANNEL_TOKEN>`, validación de owner_epoch/worker_id y lease. Token nunca llega al frontend ni URL/logs. Rechazar origen/peer remoto y equipo distinto, aunque token coincida; una conexión productora por owner. Sin token, archivos siguen funcionando y vivo no se ofrece.

Control API→worker: `capture.probe` con request_id, reservation_id, device_index, max_timeout_s=5; retry/confirm-resume se persisten bajo lock del job en REST y el worker los observa en DB; WS transporta probes y comprobaciones neutrales. Respuestas de probe incluyen request_id y resultado en RAM. Reservas se confirman en DB antes de enviar; al crear sesión revalidar cámara activa y liberar reserva. Solicitudes pendientes RAM≤8, timeout5 s, nunca persistir el JPEG en worker_machines. Fallo/expiración cancela probe y libera dispositivo.

`capture.probe.result`: JPEG para referencia o check; solo la operación de preparación persiste ReferenceFrame. Reanudación publica check frame neutral, sin métricas nuevas, hasta confirmación de operador. Token nonce generado API y ligado a session/job/device/segment/dimensions/owner_epoch; consumible una vez, TTL60 s; no contiene secretos de cámara.

Inferencia→publisher queue1: reemplaza mensajes sin esperar a red. Client asyncio `proxy=None`, `open_timeout=2`, `max_size=1048576`, `max_queue=1`; enviar en task dedicada con timeout500 ms, cerrar/reconectar sin retener mensajes viejos. API valida que updates correspondan a job claimed_by/target del productor, guarda último en RAM y no acepta imágenes para job terminal.

## WS público observador

Reutilizar `/ws/jobs/{job_id}/preview` con branch de live. Esquemas1/2 de archivos no cambian. Hasta8 observadores del vivo; mantener una actualización pendiente por observador, send timeout1 s, close1013 en exceso/lentitud. Un navegador no puede producir updates ni controlar dispositivos por este socket.

Mensaje `live.update`, `schema_version:"3"`:

```json
{
  "type": "live.update", "schema_version": "3", "source_kind": "webcam",
  "session_id": "UUID", "job_id": "UUID", "revision": 41,
  "capture_status": "connected", "segment_index": 0, "capture_sequence": 302,
  "capture_timestamp_seconds": 10.2, "captured_monotonic_ms": 123456.7,
  "published_monotonic_ms": 123470.1, "image_media_type": "image/jpeg",
  "image_base64": "JPEG_BASE64", "partial": true,
  "capture_fps": 30.0, "analysis_fps": 12.1,
  "capture_to_publish_ms": 13.4,
  "shops": [], "minutes": [], "coverage_complete": true,
  "checkpoint_revision": 40, "checkpoint_at": "UTC"
}
```

Shops contiene conteos completos por local, hasta20; minutes hasta60 minutos/local. No porcentaje de avance. Imagen y cifras comparten horizonte temporal analizado; si vence candidato sin nuevo frame se mantiene la imagen y aumenta revision, pero no se adelanta horizonte más allá del último tiempo observado válido. UI acepta revision creciente incluso misma capture_sequence, reemplaza valores, nunca suma deltas recibidos. Publicar un nuevo frame excluye en su snapshot hechos cuyo timestamp original es posterior al frame.

`live.status`: sin JPEG, status/capture_status, revision y último horizonte válido; se usa para interrupción, finalización y staleness. No modificar contadores con un clock heartbeat. `job.terminal` conserva formato existente y obliga lectura REST final. Producer/API RAM imagen TTL10 s; después devolver `awaiting_preview`, no reproducir snapshot histórico. Browser puede mantener último frame visible marcado como desactualizado y se limpia al salir de sesión.

`live.reconnect-check`: capture_status=awaiting_confirmation, JPEG neutral, dimensions, check_token y expires_in_seconds=60. Permite revisar encuadre y enviar confirm-resume; no incluye métricas nuevas ni representa un frame analizado. Nonce consumible una vez; no es el token secreto del canal interno. Tras expirar, pedir retry para obtener una comprobación nueva.

Control de reloj público: `clock.ping {client_sent_ms,nonce}` → `clock.pong {client_sent_ms,nonce,server_received_monotonic_ms,server_sent_monotonic_ms}`; server limita8 por conexión al calibrar y1 cada30 s después. Browser calcula offset con muestra de mínimoRTT, latencia de captura al primer render y margenRTT/2. Valores no calibrados se muestran no disponibles, no negativos corregidos a cero. No comparar épocas de relojes sin esa calibración.

Reconnect1/2/5 s en cliente con cancelación al navegar; primero consultar estado REST y luego usar snapshot runtime nuevo. Cierre del navegador no detiene sesión. API reiniciada recupera metadata durable y productor vuelve a enviar último resultado; imagen vive solo en RAM. Estados previos al primer frame pueden mostrar «Iniciando análisis», sin usar el frame de referencia como prueba de captura actual.

### Selector de webcams por nombre · 2026-10-05

GET /live/devices conserva candidates, machine_id y worker_available; candidates ahora contiene solo dispositivos enumerados por Windows, con device_index0–32, label FriendlyName≤200caracteres y verified:false. La enumeración no abre captura; solo preparar/comprobar demuestra disponibilidad. Lista vacía no crea sesión/job. UI ofrece Actualizar cámaras y bloquea si la selección desaparece. Índices conservan orden DirectShow y el probe Windows usa ese backend. Error de driver/timeout retorna503 device_enumeration_failed; plataforma no implementada retorna503 device_enumeration_unsupported. Fake solo ENVtest/capturefake: un dispositivo expresamente simulado. Sin nuevas migraciones ni variables de dispositivo en .env.
