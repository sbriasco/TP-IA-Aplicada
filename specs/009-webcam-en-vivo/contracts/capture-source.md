# Contrato interno: fuente de captura

Python, sin dependencia de geometría, DB, detector o UI. Tipos en `capture/contracts.py`; webcam/fake son implementaciones. Un adaptador IP futuro respetará este contrato, sin ser implementado ahora.

## Tipos y métodos

`CaptureSettings`: device_index:int, backend:str, requested_width=1280, requested_height=720; en webcam solo índices allowlist, nunca strings con URL.

`CapturedFrame`: image:np.ndarray BGR uint8, sequence:int global creciente durante job (también con frames descartados), segment_index:int, captured_monotonic_ns:int, timestamp_seconds:Decimal relativo al epoch analítico, width:int, height:int.

`CaptureProbeResult`: frame JPEG en memoria, width/height, backend efectivo, device_index, reported_fps nullable; no Job ni archivo. Validez de probe/check máxima60 s, no prueba identidad real del USB.

`CaptureDiscontinuity`: reason:str, last_valid_timestamp:Decimal, first_resumed_timestamp:Decimal|None; no genera eventos de cruce.

`FrameSource`:

- `start() -> None`: inicia capture auxiliar; espera primer frame como máximo5 s, error estable en fallo.
- `read_latest(after_sequence: int, timeout_s: float) -> CapturedFrame | None`: retorna únicamente la última secuencia nueva o None por timeout; no reentrega frame ni bloquea indefinidamente.
- `stop(timeout_s: float = 2.0) -> None`: cierre cooperativo1 s y terminación1 s; descarta generation/locks/sharedmemory si hubo terminate. No mata worker ni API.
- `status() -> CaptureStatus`: connected/interrupted/closed y backend/dimensiones; no interpreta tiendas/personas.

`SourceFactory`: callable que consume CaptureSettings y epoch/segment/sequence inicial y retorna FrameSource; fake inyecta reloj, frames, read bloqueada, desconexión y cambio de resolución. Fake solo configurable en entorno test, nunca disponible desde parámetros HTTP.

## Propiedad de buffers y límites

Un slot pendiente raw ≤1920×1080×3; metadata se actualiza atómicamente con la imagen. Worker copia snapshot y libera lock antes de inferencia. Hilo de captura reemplaza pendiente; no espera al modelo. No se transmite un pickle de np.ndarray por WS a la API, solo JPEG de preview ya analizado.

Proceso auxiliar usa spawn y módulos importables, sin modelos globales. Tiene hilo de captura y supervisor; thread solo captura, no DB/inferencia. Watchdog del padre cierra helper tras3 s sin secuencia o bloqueo de lock; nuevo helper usa nuevos recursos. Ningún proceso se reinicia durante inferencia de otro job.

Timestamp se toma después de read exitoso y se identifica como recepción local del frame. Primer frame analítico establece epoch0; frames de preparación no cuentan. Tras reconectar epoch se conserva y sequence sigue creciente, segment cambia. El adaptador no corrige ni inventa tiempos por FPS; reported_fps solo diagnóstico.

## Errores

`device_unavailable`, `device_busy`, `capture_open_timeout`, `capture_read_timeout`, `capture_resolution_unsupported`, `capture_format_changed`, `capture_process_failed`. Mensajes públicos sin rutas, secretos ni identificación personal del equipo.

Una resolución/proporción incompatible o dispositivo posiblemente cambiado exige reconfiguración/confirmación antes de medir. El adaptador no puede detectar con certeza desplazamiento físico de cámara: operador confirma encuadre.

## Pruebas de contrato

Tipos de salida del análisis: `LiveCrossingFact` contiene candidate_id estable, session/job/segment, shop_id, track_id temporal, candidate_sequence, capture_timestamp_seconds original, confirmed_at_capture_seconds, direction y foot normalizado. `PositionSlotChange` contiene slot_index (0..19999) y muestra con session/segment/track/sequence/timestamp/foot; reemplaza el slot, nunca agrega otro fuera de capacidad. Ninguno transporta imagen. Persistencia valida pertenencia al job y aplica cambios de forma idempotente.

- Fuente200Hz, consumidor5Hz: máximo1 pendiente, secuencia avanza saltando frames, timestamps conservan tiempo real.
- read eterna: stop retorna≤2 s en fixture de proceso y cierra handles; no hereda lock al reconectar.
- Discontinuidad: primer frame del segmento nuevo no produce cruce con posición del anterior.
- Dos consumidores no se soportan para inferencia; preview es downstream separado y no abre webcam.
