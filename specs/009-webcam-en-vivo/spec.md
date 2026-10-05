# Feature Specification: Análisis en vivo con webcam

**Feature Branch**: `feature/009-webcam-en-vivo`

**Created**: 2026-10-03

**Status**: Draft

**Azure Boards**: Fuera de alcance por instrucción del usuario: agregado para la expo del profesor, separado del TP. No crear ni actualizar elementos en Azure Boards para esta feature.

**Input**: Demo de FlowSight para la Expo IA: webcam local, escena configurable, imagen analizada con estadísticas al costado actualizadas continuamente, resultados históricos y sin grabación. Preparar la incorporación posterior de cámaras IP, que podrán probarse con cámaras domésticas.

## Clarifications

### Session 2026-10-03

- Q: ¿El gráfico de la webcam debe mostrar cruces por minuto o visitas estimadas por minuto? → A: Cruces por minuto, separados del flujo de visitas de los videos. Los sentidos se rotulan A → B/B → A, o entradas/salidas si el encuadre corresponde a un acceso. Visitas estimadas y otras estadísticas del vivo se evaluarán después.
- Q: ¿Al presionar «Detener», la sesión de webcam debe finalizar normalmente y guardar sus resultados? → A: Sí. Detener cierra normalmente el período observado y conserva resultados e interrupciones; la cobertura incompleta se indica por separado.
- Q: ¿Guardamos también una muestra de posiciones para poder mostrar un mapa de calor después? → A: Sí. Guardar una muestra acotada de posiciones y mostrar el mapa de calor en el historial sobre el frame de referencia, sin grabar video ni imágenes continuas.
- Q: ¿Cómo querés mostrar en el historial las estadísticas de una sesión de webcam? → A: Cruces por sentido, total, cruces por minuto, duración, interrupciones y mapa de calor. Los indicadores comerciales adicionales se evaluarán después.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configurar e iniciar una webcam (Priority: P1)

Como expositor quiero elegir una webcam conectada a la PC, obtener un frame y configurar la escena antes de iniciar una sesión, para medir cruces en el sector que finalmente nos asignen.

**Why this priority**: La ubicación de la cámara aún se desconoce y la demo necesita una fuente real configurable.

**Independent Test**: Con una webcam, obtener el frame, guardar una escena válida mediante el editor existente e iniciar y detener una sesión identificada.

**Acceptance Scenarios**:

1. **Given** una webcam disponible, **When** la selecciono y confirmo preparar la sesión, **Then** se registra una sesión de origen webcam y su frame de referencia; puedo configurar zonas, línea y sentido de entrada con las validaciones del editor existente.
2. **Given** una sesión preparada con cámara y configuración activas, **When** inicio, **Then** se crea su trabajo aislado y comienza el análisis; la configuración queda inmutable para ese trabajo y el tiempo de captura analítica comienza en cero.
3. **Given** una sesión activa, **When** la detengo, **Then** cesa la captura, se libera el dispositivo, el trabajo queda completado y se conservan los resultados del período observado; las interrupciones se señalan como cobertura incompleta y puedo iniciar otra sesión sin heredar tracks ni contadores.
4. **Given** dispositivo ausente, ocupado o configuración retirada, **When** intento iniciar, **Then** recibo un motivo comprensible y no queda un trabajo activo ficticio.

### User Story 2 - Mostrar análisis y estadísticas durante la expo (Priority: P1)

Como visitante quiero ver la imagen analizada y estadísticas al costado para entender cómo cambia el flujo mientras transitan personas.

**Why this priority**: Es la demostración principal del stand.

**Independent Test**: Realizar cruces anotados manualmente y observar imagen, detecciones, línea, conteos por sentido, total de cruces y gráfico de cruces por minuto sin recargar la página.

**Acceptance Scenarios**:

1. **Given** una sesión activa, **When** hay personas visibles, **Then** la pantalla presenta la imagen analizada con detecciones y línea, junto a estadísticas identificadas como parciales.
2. **Given** un cruce confirmado, **When** vence su ventana de validación, **Then** se actualiza el sentido correspondiente aunque ese track no vuelva a cruzar ni termine la sesión.
3. **Given** captura más rápida que análisis, **When** continúa la sesión, **Then** se priorizan imágenes recientes sin acumular una cola creciente de imágenes atrasadas.
4. **Given** actualización de imagen y métricas, **When** se muestran, **Then** comparten una referencia temporal analizada; no se presenta una imagen reciente junto a cifras de un instante posterior o de otra sesión.
5. **Given** recuperación del navegador tras una desconexión, **When** vuelve a abrir la sesión, **Then** recibe los valores actuales sin reiniciar captura ni duplicar eventos.

### User Story 3 - Recuperarse de interrupciones y consultar resultados (Priority: P2)

Como expositor quiero conocer las interrupciones de la cámara y consultar el resultado al terminar, para no confundir falta de datos con ausencia de tránsito.

**Why this priority**: Una demo prolongada debe conservar evidencia y comunicar fallas.

**Independent Test**: Desconectar y reconectar la webcam, detener la sesión y abrirla desde el historial.

**Acceptance Scenarios**:

1. **Given** una sesión activa, **When** se pierde la captura, **Then** la pantalla marca interrupción y último instante válido; los períodos sin datos no se muestran como flujo cero observado.
2. **Given** el mismo dispositivo recuperado, **When** se reanuda, **Then** mantiene los acumulados, registra la discontinuidad y comienza un nuevo segmento de tracking sin inferir cruces a través del intervalo perdido.
3. **Given** que no puede recuperarse automáticamente, **When** falla la recuperación, **Then** el usuario puede reintentar o finalizar; las estadísticas previas permanecen disponibles.
4. **Given** una sesión finalizada, **When** abro el historial, **Then** veo configuración, duración, cruces por sentido, total de cruces, cruces por minuto, eventos, interrupciones y mapa de calor; la cobertura incompleta se identifica cuando corresponde y se muestra «Sin grabación», sin ofrecer reproducción ni recarga de archivo.
5. **Given** caída del proceso, **When** el sistema se recupera, **Then** la sesión interrumpida conserva lo persistido, explicita su finalización incompleta y no figura indefinidamente como activa.
6. **Given** una sesión con muestra de posiciones guardada, **When** abro su mapa de calor en el historial, **Then** se dibuja sobre el frame de referencia, sin requerir video; si no hay posiciones válidas, se muestra un estado vacío explicado.

### Edge Cases

- No hay personas; cruces simultáneos, retorno legítimo, oscilación sobre la línea y personas que desaparecen del encuadre.
- Frames descartados, cambio de resolución, dispositivo distinto después de reconectar o cámara desplazada: si cambia el encuadre no se reutiliza silenciosamente la escena; se exige finalizar y reconfigurar.
- Un track perdido no hereda la trayectoria de otro. Un cruce pendiente frente a una interrupción se descarta como no confirmado; al detener normalmente se confirma solo si ya venció su ventana.
- Cierre de la página: el análisis continúa hasta detenerlo explícitamente o fallar el worker; el usuario puede volver a la sesión activa.
- Dos intentos de inicio concurrentes: inicialmente se permite una única sesión de análisis activa en el worker, incluyendo trabajos de archivos; el segundo recibe un aviso.
- La baja lógica de sesión, cámara o configuración sigue bloqueada mientras existan trabajos activos; el historial respeta las reglas actuales de retiro.
- Si el operador abandona una preparación, se libera la webcam y no se crea un trabajo de análisis. La sesión queda preparada, sin resultados analíticos, y puede retomarse verificando el encuadre o retirarse mediante la baja lógica existente; el frame sigue conservado si una escena lo referencia.
- Si dos observaciones de un track están demasiado separadas para demostrar continuidad, no se infiere un cruce entre ellas; el límite se fija y prueba en la planificación.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Permitir seleccionar y verificar una webcam local; distinguir el dispositivo físico del registro de cámara de FlowSight.
- **FR-002**: Al confirmar la preparación, registrar la sesión de origen webcam y su único frame de referencia antes de configurar o seleccionar una escena compatible mediante el recorrido existente. Crear el trabajo de análisis únicamente al iniciar; no incluir el tiempo de preparación en la duración analítica. Preservar validaciones de zonas, locales, pertenencia a cámara y relación de aspecto; esta feature no agrega un editor nuevo ni relaja su validación. La sesión webcam no exige archivo, hash ni duración total anticipada.
- **FR-003**: Permitir iniciar y detener explícitamente una sesión en vivo, con estados de preparación, análisis, interrupción, finalización y fallo visibles. «Detener» cierra normalmente el período observado, deja el trabajo completado y conserva sus resultados; permanece disponible durante una interrupción. La cobertura incompleta por desconexiones se registra independientemente del cierre completado. No modifica la cancelación de archivos: esos trabajos siguen quedando cancelados. Una caída del worker deja el trabajo fallido, con resultados persistidos incompletos y sin reanudación automática.
- **FR-004**: Detectar personas y mantener tracks temporales por sesión/cámara/segmento de captura; distinguir los IDs reutilizados después de reconectar tanto en eventos como en muestras persistidas. Reutilizar la visión aprobada y registrar versiones y parámetros usados en el análisis. No introducir identidad real ni conteo de visitantes únicos.
- **FR-005**: Desacoplar captura y análisis, conservando una cantidad acotada de frames transitorios y priorizando el último disponible. Cada imagen capturada debe mantener su secuencia y tiempo de captura aunque se descarten intermedias.
- **FR-006**: Medir tiempos por captura, relativos al inicio de la sesión, con una referencia que no retroceda. Nunca calcular duración o permanencia mediante cantidad de frames analizados dividida por FPS nominal ni por tiempo de inferencia.
- **FR-007**: Adaptar ventanas de oscilación y confirmación a duración temporal documentada, y definir un máximo intervalo entre observaciones compatible con continuidad de tracking. El plan debe fijar y justificar ambos parámetros con pruebas. Confirmar cruces al vencer la ventana conservando el timestamp del cruce original; no aplicar un cooldown general que suprima retornos legítimos. Los intervalos perdidos o superiores al límite de continuidad no prueban cruces, presencia continua ni permanencia.
- **FR-008**: Mostrar simultáneamente imagen analizada, detecciones, configuración espacial y estadísticas parciales: cruces por sentido, total de cruces confirmados y «Cruces por minuto», por línea/local seleccionado y para la sesión actual. Rotular sentidos A → B/B → A; usar entradas/salidas cuando el operador indique que la línea corresponde a un acceso. La dirección configurada conserva su significado interno para el conteo.
- **FR-009**: Definir total de cruces como la suma de ambos sentidos confirmados, no personas únicas. «Cruces por minuto» agrupa esos eventos por timestamp de captura en intervalos de 60 segundos desde el inicio; el intervalo actual se etiqueta parcial, sin extrapolar. Intervalos con pérdida de cobertura se marcan incompletos. Esta serie no reemplaza ni modifica tráfico, flujo de visitas ni horario pico de los videos. Visitas estimadas y su gráfico en vivo quedan fuera de esta entrega y se evaluarán después.
- **FR-010**: Publicar actualizaciones continuas con referencia temporal consistente y acotadas en frecuencia; indicar antigüedad de la imagen y estado de conexión. No requerir una actualización gráfica por frame.
- **FR-011**: Mostrar estado de captura, FPS de captura y análisis medidos y latencia captura-pantalla. La latencia incluye el transporte y presentación; si solo puede medirse captura-publicación debe etiquetarse como tal y no usarse como sustituto de la medición completa.
- **FR-012**: Ante pérdida de captura, intentar recuperar el mismo dispositivo, mostrar el estado y ofrecer reintento/finalización. Registrar intervalos perdidos, resetear tracking y evitar eventos espaciales que unan ambos lados de una interrupción.
- **FR-013**: Persistir sesión y cámara, escena inmutable, frame de referencia, inicio y fin, eventos, cifras acordadas, interrupciones y muestra de posiciones. El historial de webcam muestra cruces por sentido, total, cruces por minuto, duración, interrupciones y mapa de calor; si hubo fallo conserva resultados parciales. No exige las ocho métricas comerciales de archivos ni calcula visitas, pasos, tasa, permanencia, ocupación o horario pico en esta entrega. El dashboard de archivos conserva su comportamiento. El chat no queda habilitado para resultados de webcam en esta entrega: debe explicar esa indisponibilidad, incluso si una consulta por nombre o por «última sesión» refiere a una webcam, sin inventar cifras ni sustituirla silenciosamente por otra sesión.
- **FR-014**: No grabar video ni secuencias de imágenes en disco. Los frames de captura, overlays y previews son transitorios y acotados, también después de finalizar; solo se conserva el frame de referencia de la escena. Los eventos y métricas pueden crecer con la duración, sin almacenar imágenes continuas.
- **FR-015**: Mantener el procesamiento de archivos existente, sus timestamps y recorrido completo de frames. La política de descartar frames corresponde exclusivamente al vivo.
- **FR-016**: Separar el contrato de fuente de captura de las reglas, tracking, estadísticas y pantalla para admitir en un incremento posterior una cámara IP. Ese contrato contempla frame, secuencia, tiempo y discontinuidad; esta entrega solo ofrece webcam y no implementa conectividad IP.
- **FR-017**: Mantener aislamiento de consultas, eventos y actualizaciones entre sesiones, exclusión de trabajos concurrentes y reglas de baja lógica actuales.
- **FR-018**: Documentar entorno probado, encuadre, concurrencia visible, calidad de conteo, latencia y limitaciones. No asumir GPU ni garantizar 40 FPS o precisión para más de 200 asistentes sin medición.
- **FR-019**: Conservar una muestra acotada de posiciones observadas para mostrar el mapa de calor en el historial sobre el frame de referencia mediante la presentación existente. Cada posición debe conservar sesión, cámara, segmento de captura, timestamp de captura y coordenadas normalizadas. La muestra no incluye imágenes ni reconstruye posiciones durante interrupciones; no debe persistir cada persona en cada frame. La planificación fijará límites de memoria, cantidad de muestras y política de muestreo temporal para sesiones de 2–3 horas; el mapa representa posiciones muestreadas, no visitantes únicos ni tiempos de permanencia exactos. Sin muestra válida, mostrar un estado vacío explicado sin bloquear estadísticas.
- **FR-020**: Un cruce confirmado después del cierre de su minuto se agrega al intervalo de su timestamp original; los intervalos con candidatos pendientes siguen sujetos a actualización hasta resolverlos. Distinguir intervalo temporal abierto de cobertura incompleta; registrar duración observada y perdida por intervalo, sin completar huecos como cero observado. Mantener agrupación por línea/local y no presentar una suma de líneas como visitantes únicos.
- **FR-021**: Persistir resultados del vivo con cadencia temporal acotada y al finalizar, independientemente de una cantidad fija de frames. La planificación fija la cadencia y la pérdida máxima de resultados ante caída; la desconexión de una pantalla no detiene ni bloquea el análisis. Acotar memoria de captura, preview, tracks inactivos y muestreo; conservar la imagen y sus cifras como una actualización temporal consistente, sin snapshots en disco para el vivo.

### Key Entities

- **Sesión en vivo**: cámara, escena, estado, tiempos de inicio/fin y resultados parciales o finales; diferenciada de una sesión con archivo reproducible. El cierre normal produce un trabajo completado; cobertura completa/incompleta es un atributo independiente que conserva las interrupciones.
- **Fuente de captura**: dispositivo seleccionado, dimensiones, disponibilidad y tiempos asociados a cada frame; webcam en esta entrega, IP futura.
- **Segmento de captura**: intervalo continuo con tracking propio; separa los intervalos antes y después de una interrupción.
- **Interrupción**: inicio, fin cuando se conoce, motivo y cobertura perdida; asociada a una sesión.
- **Actualización analítica**: imagen transitoria y cifras correspondientes a una referencia temporal analizada de una sesión.
- **Resultado persistido**: escena y frame de referencia, eventos confirmados, métricas y calidad de cobertura, sin video reproducible.
- **Origen webcam**: sesión con metadatos de captura y equipo de origen, sin video, ruta de archivo ni hash; distingue preparación de análisis y usa «Sin grabación» en el historial.
- **Muestra de posiciones**: subconjunto acotado de observaciones normalizadas, con tiempo de captura y contexto de sesión/cámara/segmento, utilizado para el mapa de calor histórico sin imágenes continuas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El recorrido selección → frame → escena válida → inicio → detención → historial se completa con una webcam real; se verifica también con una fuente reproducible sin hardware.
- **SC-002**: En la PC y webcam de demo, durante 10 minutos, al menos 95 % de las actualizaciones visuales tienen latencia captura-pantalla de hasta 2 segundos. Es un objetivo de aceptación por medir, no una capacidad demostrada ni garantía para otros equipos.
- **SC-003**: En una prueba reproducible que entrega imágenes a una tasa triple de la capacidad de análisis durante 10 minutos, la cantidad pendiente no supera dos imágenes y no crece con el tiempo; al quitar la sobrecarga se recuperan imágenes recientes sin reproducir el atraso acumulado.
- **SC-004**: En trayectorias sintéticas con tiempos conocidos, se verifica exactamente el conteo bidireccional esperado, la eliminación de oscilaciones, la confirmación por vencimiento y la ausencia de cruces entre segmentos o sesiones, incluso descartando frames.
- **SC-005**: En un ensayo manual corto con al menos 40 cruces anotados, incluyendo pasos juntos y retornos, se publica el error absoluto por sentido y el número de personas simultáneas. Objetivo inicial: error por sentido no mayor al 10 % de sus cruces reales; si un sentido tiene cero, se exige cero falsas detecciones. Un fallo requiere ajustar el encuadre/configuración o declarar la limitación antes de la demo.
- **SC-006**: Tras desconectar la webcam y tras desconectar únicamente la pantalla, se conservan los valores previos sin duplicados; al recuperar captura no se confirma ningún cruce que abarque el intervalo perdido.
- **SC-007**: En una sesión de estabilidad de 2 horas con escena tranquila, los frames pendientes permanecen acotados y la memoria al final no supera en más del 20 % la mediana posterior a los primeros 10 minutos; no aparecen archivos de video ni secuencias de preview. Esta prueba no valida precisión con multitud y puede ejecutarse sin tránsito continuo.
- **SC-008**: Una sesión finalizada o interrumpida conserva sus resultados consultables después de reiniciar; detener normalmente deja el trabajo completado, incluso con desconexiones registradas como cobertura incompleta. Una caída del worker deja el trabajo fallido sin reanudación automática. La revisión de almacenamiento confirma que la única imagen persistente es la referencia de escena y que no existe reproducción de video.
- **SC-009**: Tras reiniciar, una sesión con posiciones muestreadas muestra su mapa sobre el frame de referencia; dos sesiones no mezclan muestras. Sin posiciones válidas, el mapa presenta un vacío explicado. En la prueba prolongada, la muestra y su almacenamiento cumplen los límites definidos en el plan y no incluyen posiciones inventadas durante interrupciones.
- **SC-010**: En pruebas de confirmación tardía, cada cruce se atribuye exactamente a su minuto original; los intervalos perdidos conservan su duración y marca de cobertura incompleta. Un ID reutilizado en otro segmento no hereda eventos ni muestras anteriores. Abandonar la preparación no deja un análisis activo.
- **SC-011**: El historial de webcam presenta las cifras acordadas sin requerir métricas comerciales ausentes; consultar esa sesión mediante el chat informa indisponibilidad sin sustituir la sesión. Los recorridos existentes de archivos mantienen sus métricas, cancelación, timestamps, previews y chat.

## Assumptions

- Una webcam fija y un único worker local; la PC concreta, cámara y encuadre se registrarán al validar. No se asume RTX en todos los equipos.
- Más de 200 asistentes representan tránsito acumulado, sin información aún sobre concurrencia visible. No es un requisito de detectar 200 personas simultáneamente.
- Los cruces se llaman entradas/salidas del evento únicamente si la línea cubre un acceso pertinente; en otros encuadres representan flujo del sector observado.
- Una sesión dura potencialmente 2–3 horas. La estabilidad puede probarse con poca gente; la exactitud se evalúa en ensayos breves anotados. No se requiere simular una multitud durante horas.
- Una configuración guardada puede reutilizarse solo si corresponde a la misma cámara y encuadre. El operador confirma esa correspondencia.
- Los requisitos numéricos de aceptación son objetivos iniciales propuestos en esta spec y deben revisarse con evidencia al planificar/validar.
- La planificación debe respetar stack y modelo vigentes y proponer la aclaración temporal de captura en la constitución, AGENTS.md y decisiones técnicas antes de implementar; nunca se reemplaza el tiempo observado por duración de inferencia. Ventanas temporales, continuidad, cadencia de persistencia y límites de muestreo/memoria son decisiones del plan que deben quedar justificadas y verificables.
- Fuera de alcance: cámara IP operativa, acceso entre redes, grabación, múltiples cámaras simultáneas, ONNX/OpenVINO, cambios de pesos, alertas de presencia, nuevas métricas comerciales y ampliación del chat.

## Registro de elaboración

Elaborada con asistencia de IA a partir del alcance acordado el 2026-10-03 y la revisión estática del commit `f7d7072`: se reutiliza visión/conteo existentes y se distingue el prefetch de archivos de la captura con último frame para vivo. No se ejecutaron pruebas de cámara ni de rendimiento al redactarla. La ubicación de expo y validación real quedan pendientes; no bloquean la especificación del recorrido configurable.
