# Research: Procesamiento y seguimiento con vista en vivo

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`.

## R1 — Detector y tracker

**Decision**: El worker real usa Ultralytics `8.4.153` con el peso `yolov8n.pt` (el mismo del experimento 001, no se versiona) y el tracker ByteTrack de ese paquete. El lock del backend fija la variante CPU (`torch==2.7.1+cpu`, `torchvision==0.22.1+cpu`) para tests y CI. En el equipo de referencia, el mismo código elige el dispositivo gráfico si está disponible; el wheel de GPU no entra al lock de CI.

**Rationale**: El stack ya acordó YOLO y ByteTrack. El experimento los evaluó como viables con ajustes para cruces, zona frontal y oclusión, y dejó ocupación total y permanencia interior como no viables. BoT-SORT no se compara en esta feature.

**Alternatives considered**: Elegir otro peso o otro tracker ahora. Se rechaza: la spec usa el método ya evaluado y solo registra la versión. Instalar GPU en CI. Se rechaza: las pruebas ordinarias deben correr sin ese equipo.

## R2 — Qué se guarda y qué no

**Decision**: No hay una fila de base por persona y por fotograma. Cada cruce confirmado y las tres medidas oficiales viven en PostgreSQL. La trayectoria es un JSONL de muestra, un registro cada 5 fotogramas de video, en disco, con ruta relativa guardada en el trabajo. El punto de referencia es el centro inferior del recuadro, igual que `reference_point` del experimento.

**Rationale**: La spec prohíbe el registro permanente por instante y exige instante de video, identificador temporal y pies en lo que sí se conserva. El experimento ya definió ese punto.

**Alternatives considered**: Reusar la tabla `observations` de specs/002 para cada detección real. Se rechaza: esa tabla es la traza sintética y crecería con cada fotograma. Guardar solo el JSONL y calcular las medidas después. Se rechaza: al completar, entradas, salidas y ocupación visible tienen que quedar como números oficiales consultables.

## R3 — Entradas, salidas y ocupación visible

**Decision**: Una entrada es un cruce confirmado en el sentido de entrada de la línea del local; una salida es el sentido opuesto. Si el mismo identificador produce el sentido contrario dentro de los 10 fotogramas siguientes, ambos quedan como oscilación y no suman, igual que `OSCILLATION_MAX_FRAMES = 10` del experimento. Un cambio de identificador no hereda el cruce ni confirma una salida. La ocupación visible de un local es la cantidad de identificadores distintos cuyo pie está dentro de la zona frontal en el último fotograma analizado. No se usa la zona interior. Una tasa sin denominador no se calcula en esta feature.

**Rationale**: Respeta la convención A/B de specs/004, la constitución (ocupación visible distinta de la total, sin permanencia si se pierde el seguimiento) y la aclaración de que estos tres números, al completar, son los oficiales.

**Alternatives considered**: Contar personas por identificador a lo largo de todo el video como ocupación. Se rechaza: el experimento marcó ese conteo como no viable. Recalcular las medidas en la feature de métricas. Se rechaza: la aclaración del 2026-09-29 lo prohíbe.

## R4 — Estados, incluido cancelado

**Decision**: Se agrega `cancelled` al enum `job_status`. Transiciones nuevas: `pending → cancelled` y `processing → cancelled`. `completed` y `failed` siguen siendo terminales y no se reintentan. Cancelar un trabajo `processing` se observa en el límite del fotograma: el worker vuelve a leer el estado y no escribe el cierre oficial. Una caída del proceso sigue yendo a `failed` con `failure_code=worker_interrupted`. El trabajo completado queda `result_complete=true`; fallido o cancelado queda `false` y sus medidas, si existen, siguen `partial=true`.

**Rationale**: La aclaración separa la cancelación del operador del fallo. Permitir cancelar también en `pending` evita que un trabajo en cola ocupe el único worker. Los cuatro estados de specs/002 no se renombran.

**Alternatives considered**: Reusar `failed` con un motivo de cancelación. Se rechaza: el operador no podría distinguir un corte pedido de un error. Borrar lo ya guardado al cancelar. Se rechaza: la spec pide marcarlo incompleto.

## R5 — Vista en vivo

**Decision**: El canal sigue siendo `ws://{host}/ws/jobs/{job_id}/preview`. Los trabajos sintéticos mantienen el mensaje `schema_version` `1` (JPEG 320×180, tope 100 KiB). Un `video_analysis` publica `schema_version` `2`: el JPEG del fotograma analizado, a su resolución, con recuadros, identificadores, zonas y línea dibujados, más el avance por fotogramas y las tres medidas. Si el JPEG supera 200 KiB se baja la calidad, sin cambiar el instante. Sigue habiendo un solo mensaje pendiente por conexión y el productor no espera al cliente.

**Rationale**: La spec pide que la imagen coincida con su instante y que un observador lento no frene el análisis. El tope de la vista sintética de specs/002 no se aplica al video real.

**Alternatives considered**: Un canal nuevo. Se rechaza: la spec reutiliza el existente. Mandar el video real a 320×180. Se rechaza: las zonas dibujadas dejan de ser legibles en los clips de 384×288.

## R6 — Pruebas sin el equipo de referencia

**Decision**: El worker depende de una interfaz `Detector`. En tests y en el recorrido reproducible, `FLOWSIGHT_DETECTOR=fake` reinyecta una secuencia fija de recuadros, sin peso ni GPU. `pytest` no recolecta `pytest.mark.gpu`. La evidencia del equipo de referencia es un JSON resumido en `validation/`, con dispositivo, versiones y fotogramas procesados por segundo de procesamiento, sin nombre de máquina, usuario, rutas ni secretos. Si el dispositivo gráfico no está disponible, el mismo video corre en CPU y el resumen lo dice.

**Rationale**: Los seis integrantes y CI tienen que cerrar el análisis sin la RTX 5080. La spec no promete tiempo real; la velocidad queda medida.

**Alternatives considered**: Exigir el peso y la GPU para la suite. Se rechaza: specs/002 ya obliga a que las pruebas ordinarias no dependan de esa máquina.

## R7 — Avance

**Decision**: El avance es `frames_analyzed / frames_total`, donde `frames_total` es el conteo de fotogramas ya guardado al registrar el video (no el encabezado MPEG). El instante de negocio es `frame_index / fps` del video. El reloj de pared solo alimenta `processing_duration_ms` y la velocidad de procesamiento de la evidencia.

**Rationale**: SC-003 pide que al 50 % de los fotogramas el avance informado sea el 50 %, con tolerancia de un fotograma. La constitución prohíbe medir el negocio con el tiempo de proceso.
