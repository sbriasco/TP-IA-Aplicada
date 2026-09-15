# Feature Specification: Validación técnica de videos y tracking

**Feature Branch**: `001-validacion-videos-tracking`

**Azure Boards**: Feature #4, hija del Epic #2 `Validación técnica y entorno reproducible`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: Especificar la validación técnica de los videos seleccionados de FlowSight para determinar si permiten medir las interacciones comerciales del MVP mediante detección y tracking.

## Clarifications

### Session 2026-09-15

- Q: ¿Qué tamaño mínimo debe tener la muestra de referencia manual para cada fragmento evaluado? → A: Documentar la cantidad observada y los casos cubiertos. Si faltan cruces u oclusiones, ampliar la muestra antes de sacar conclusiones sobre esos casos.
- Q: ¿El rendimiento debe registrarse por cada fragmento evaluado, además de cualquier resumen global? → A: Registrar por fragmento la duración del video, los frames procesados, el tiempo de procesamiento y el equipo o dispositivo; permitir un resumen global opcional.
- Q: ¿Cómo debemos identificar coincidencias, omisiones y duplicados al comparar la referencia manual con los resultados automáticos? → A: Comparar cruces por ocurrencia observable y evaluar por separado la continuidad de los tracks. Un cambio de ID no implica automáticamente un evento duplicado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seleccionar fragmentos representativos (Priority: P1)

Como integrante del Grupo 6, quiero seleccionar fragmentos representativos de los videos disponibles para evaluar circulación, oclusiones, entradas y frentes de locales, de modo que la decisión sobre la viabilidad del MVP se base en evidencia del material real.

**Why this priority**: La adecuación de los videos condiciona qué métricas comerciales pueden comprometerse.

**Independent Test**: Se puede revisar el conjunto de fragmentos seleccionado y comprobar que cada video disponible tiene al menos un fragmento documentado con sus características observables y motivo de selección.

**Acceptance Scenarios**:

1. **Given** los videos seleccionados están disponibles, **When** se revisan sus características y se eligen fragmentos, **Then** cada fragmento queda identificado por video, intervalo temporal y motivo de selección.
2. **Given** un video no permite observar una interacción comercial relevante, **When** se documenta la selección, **Then** esa limitación queda registrada y no se presenta el video como evidencia suficiente para esa medición.

---

### User Story 2 - Comparar detecciones y cruces con una referencia manual (Priority: P1)

Como integrante del equipo, quiero comparar los resultados automáticos con una referencia manual acotada para distinguir errores de detección, pérdidas de seguimiento, cruces omitidos y duplicados.

**Why this priority**: Sin una referencia manual no se puede interpretar la calidad del tracking ni decidir qué métricas son viables.

**Independent Test**: Se puede ejecutar la comparación sobre uno o más fragmentos y revisar un registro que contenga la cantidad observada, los casos cubiertos, el resultado automático y las diferencias encontradas.

**Acceptance Scenarios**:

1. **Given** uno o más fragmentos representativos y una escena preconfigurada, **When** se realiza el conteo manual de personas y cruces observables, **Then** la referencia documenta la cantidad observada, los casos cubiertos, el intervalo temporal y los criterios usados.
2. **Given** la muestra no contiene cruces u oclusiones suficientes para evaluar esos casos, **When** se revisa la cobertura antes de concluir, **Then** se amplía la muestra y la limitación queda registrada.
3. **Given** la referencia manual y el resultado automático están disponibles, **When** se comparan, **Then** cada cruce se identifica por ocurrencia observable y cada diferencia se clasifica como detección faltante, detección espuria, pérdida de track, oclusión, duplicado, cruce omitido u otro error documentado. La continuidad de los tracks se evalúa por separado.

---

### User Story 3 - Evaluar tracking y eventos espaciales básicos (Priority: P1)

Como integrante del equipo, quiero evaluar una detección inicial con YOLO y ByteTrack sobre una zona frontal y una línea de entrada preconfiguradas para saber si el material permite medir tráfico, paso frente a locales y entradas.

**Why this priority**: Estas interacciones sostienen las métricas comerciales obligatorias del MVP.

**Independent Test**: Se puede ejecutar la prueba sobre una escena preconfigurada y revisar los tracks, la zona frontal, la línea de entrada, los cruces y los errores registrados sin construir el editor visual ni el dashboard.

**Acceptance Scenarios**:

1. **Given** un fragmento con una zona frontal y una línea de entrada preconfiguradas, **When** se ejecuta la evaluación inicial, **Then** se registran detecciones, IDs temporales, entradas en la zona y cruces de la línea con su dirección cuando sea observable.
2. **Given** un track se pierde, reaparece o queda ocluido, **When** se revisan los resultados, **Then** el informe evalúa la continuidad por separado y no interpreta automáticamente un cambio de ID como una persona diferente, un evento duplicado o una salida confirmada.
3. **Given** un cruce oscila sobre una línea o una ocurrencia observable produce varios eventos automáticos, **When** se analizan los eventos, **Then** se comparan por ocurrencia observable y los duplicados quedan registrados junto con su causa; un cambio de ID aislado se registra como posible discontinuidad de track, no como duplicado automático.

---

### User Story 4 - Medir tiempos y decidir viabilidad (Priority: P1)

Como responsable de la planificación, quiero obtener un informe de viabilidad por medición del MVP, con tiempos basados en el video y limitaciones explícitas, para decidir qué debe ajustarse antes de comprometer la implementación.

**Why this priority**: La validación debe producir una decisión trazable, no solo una demostración visual.

**Independent Test**: Se puede revisar el informe final y verificar que relaciona cada medición con evidencia, errores observados, limitaciones y uno de estos estados: viable, viable con ajustes, no viable con el material o configuración evaluados, o no evaluable por falta de evidencia.

**Acceptance Scenarios**:

1. **Given** un fragmento con timestamps del video, **When** se calculan duraciones de permanencia o intervalos de comportamiento, **Then** se usan los timestamps del video y no el tiempo que tardó en ejecutarse la prueba.
2. **Given** se completaron las evaluaciones disponibles, **When** se genera el informe, **Then** incluye para cada medición evaluada la viabilidad, la evidencia, las limitaciones y los ajustes requeridos cuando corresponda, y distingue las mediciones comprobadas directamente de las que no pueden evaluarse con los fragmentos, zona o línea disponibles.
3. **Given** no hay evidencia suficiente para una medición, **When** se redacta el informe, **Then** se marca como no evaluable o pendiente y no se inventa un resultado ni un umbral de precisión.

---

### Edge Cases

- Un video puede no mostrar entradas, frentes de locales o circulación suficiente; la medición afectada debe marcarse como no evaluable.
- La resolución, iluminación, perspectiva o duración pueden impedir distinguir personas, pies, objetos o cruces.
- Una oclusión puede ocultar temporalmente un track; la permanencia no debe inferirse como continua si se pierde el seguimiento.
- Un track puede reaparecer con otro ID; la prueba debe registrar la discontinuidad y evitar contar una identidad real.
- Un mismo cruce puede generar varias detecciones por oscilación; los duplicados deben separarse de cruces válidos.
- Si un video no tiene fecha real conocida, los análisis deben usar la sesión y el tiempo relativo del video.
- Una división por cero o una población insuficiente para una métrica debe informarse como no disponible, no como cero.
- El tiempo de procesamiento puede ser mayor o menor que la duración del video; esto no cambia los timestamps usados para métricas de comportamiento.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El equipo DEBE seleccionar y documentar fragmentos representativos de los videos disponibles, indicando video, intervalo temporal, características observables y motivo de selección.
- **FR-002**: La evaluación DEBE utilizar escenas preconfiguradas para una zona frontal y una línea de entrada, sin requerir la construcción del editor visual.
- **FR-003**: La evaluación DEBE ejecutar una prueba inicial de detección y tracking con YOLO y ByteTrack, dejando abierta la comparación con otro tracker si los resultados lo justifican.
- **FR-004**: El equipo DEBE crear una referencia manual acotada y documentar la cantidad de personas, tracks, permanencias y cruces observados, junto con los casos cubiertos, intervalos temporales y criterios usados. Si faltan cruces u oclusiones para evaluar una conclusión, DEBE ampliar la muestra antes de concluir sobre esos casos y registrar la limitación.
- **FR-005**: El registro de resultados DEBE distinguir detecciones faltantes, detecciones espurias, pérdidas de tracks, oclusiones, duplicados, cruces omitidos y otros errores observados. Los cruces DEBEN compararse por ocurrencia observable, considerando su intervalo, zona o línea y dirección cuando estén disponibles.
- **FR-006**: La evaluación DEBE registrar los IDs temporales y tratarlos como pertenecientes únicamente a la sesión y cámara evaluadas, sin inferir identidad real ni unicidad de personas. La continuidad de los tracks DEBE evaluarse por separado de la comparación de cruces; un cambio de ID no implica automáticamente un evento duplicado.
- **FR-007**: La evaluación DEBE registrar para la zona frontal y la línea de entrada los eventos observados, su dirección cuando sea visible y las oscilaciones o duplicaciones que afecten su interpretación.
- **FR-008**: Las duraciones de permanencia y los intervalos de comportamiento DEBEN calcularse con timestamps del video original y no con el tiempo de ejecución del procesamiento.
- **FR-009**: La evaluación DEBE registrar por cada fragmento su duración según el video, frames procesados, tiempo de procesamiento y equipo o dispositivo utilizado. Puede incluir un resumen global, pero no debe reemplazar los datos por fragmento.
- **FR-010**: El informe DEBE distinguir las duraciones e intervalos de comportamiento calculados con timestamps del video de la duración del fragmento, los frames procesados y el tiempo de procesamiento usados para describir rendimiento.
- **FR-011**: El informe DEBE indicar qué mediciones se comprobaron directamente con los fragmentos, zona frontal y línea de entrada disponibles, cuáles no pudieron evaluarse y por qué, sin exigir implementar todas las métricas del MVP en este experimento.
- **FR-012**: El informe DEBE asignar a cada medición evaluada uno de estos estados: viable, viable con ajustes, no viable con el material o configuración evaluados, o no evaluable por falta de evidencia. Una conclusión negativa respaldada por evidencia completa la validación y no debe convertirse automáticamente en una tarea de implementación.
- **FR-013**: El informe DEBE indicar para cada medición la evidencia utilizada, las limitaciones, los datos incompletos y las decisiones o ajustes requeridos.
- **FR-014**: La prueba DEBE poder ejecutarse con un script y configuración manual acotados, sin construir el editor visual, dashboard, chat ni la persistencia completa del MVP.
- **FR-015**: Los artefactos de la evaluación DEBEN conservar una referencia al video, fragmento, configuración, criterio manual, mediciones de rendimiento y resultado para permitir repetir o revisar la conclusión.

### Key Entities

- **Video candidato**: video disponible para la validación, con condiciones de uso y características observables.
- **Fragmento representativo**: intervalo temporal seleccionado para cubrir circulación, oclusiones, entradas o interacción con un local.
- **Escena preconfigurada**: configuración manual de una zona frontal y una línea de entrada utilizada para la prueba.
- **Referencia manual**: conteo y registro humano de personas, permanencias y cruces observables en un fragmento.
- **Track temporal**: seguimiento anónimo dentro de una sesión y cámara, sujeto a pérdidas, oclusiones y cambios de ID.
- **Evento evaluado**: detección de ingreso, salida, paso o permanencia observada en la zona o línea configurada.
- **Registro de error**: evidencia de una pérdida, oclusión, duplicado, cruce omitido, detección incorrecta u otra limitación.
- **Informe de viabilidad**: conclusión por medición del MVP, con evidencia, limitaciones y ajustes requeridos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los videos seleccionados tiene al menos un fragmento representativo documentado o una justificación explícita de por qué no puede evaluarse.
- **SC-002**: El 100% de los fragmentos evaluados tiene una referencia manual acotada que documenta la cantidad observada, los casos cubiertos y un resultado automático comparable, o una causa documentada de imposibilidad. Las conclusiones sobre cruces u oclusiones cuentan con una muestra ampliada cuando la primera selección no los cubre.
- **SC-003**: Cada fragmento evaluado registra la cantidad y categoría de errores observados, incluyendo pérdidas de tracks, oclusiones, duplicados y cruces incorrectos cuando ocurran.
- **SC-004**: El informe distingue las mediciones comprobadas directamente de las no evaluables con el material o configuración disponibles, sin exigir que este experimento implemente todas las métricas del MVP.
- **SC-005**: Cada fragmento evaluado tiene registrados su duración según el video, frames procesados, tiempo de procesamiento y equipo o dispositivo; cualquier resumen global conserva la trazabilidad a esos registros.
- **SC-006**: Todas las duraciones de permanencia e intervalos de comportamiento del informe pueden rastrearse a timestamps del video y no al tiempo de ejecución de la prueba.
- **SC-007**: Cada medición evaluada tiene uno de los estados viable, viable con ajustes, no viable con el material o configuración evaluados, o no evaluable por falta de evidencia. Las conclusiones negativas respaldadas por evidencia se consideran resultados válidos de la validación.
- **SC-008**: La evaluación produce una recomendación reproducible sobre la adecuación de los videos y del tracking para continuar la planificación del MVP, incluyendo decisiones pendientes cuando la evidencia sea insuficiente.
- **SC-009**: La prueba puede repetirse con los mismos fragmentos, escena preconfigurada y criterios manuales sin construir componentes del MVP que están fuera del alcance de esta Feature.

## Assumptions

- Los videos ya fueron seleccionados por el equipo y estarán disponibles localmente para la evaluación; no se eligen nuevos videos dentro de esta Feature.
- La prueba puede utilizar un script y configuración manual acotados, sin convertir esos artefactos en componentes del producto.
- YOLO y ByteTrack son el punto de partida acordado para la evaluación, pero sus versiones, pesos, umbrales, compatibilidad y rendimiento siguen pendientes de validación.
- La PC con RTX 5080 es una referencia de integración; la conclusión debe considerar también la ejecución o pruebas sintéticas en equipos sin esa GPU.
- La referencia manual será acotada y servirá para comparar fragmentos representativos; documentará la cantidad observada y los casos cubiertos, y se ampliará si faltan cruces u oclusiones antes de concluir sobre esos casos. No pretende constituir una anotación exhaustiva de todos los videos.
- La ocupación y permanencia se interpretan como observables en la zona evaluada; perder un track no demuestra la salida de un local.
- No se fijan umbrales de precisión ni velocidad en esta especificación. El informe debe proponer decisiones o ajustes basados en la evidencia obtenida.
- Esta Feature no construye el editor visual, dashboard, chat ni la persistencia completa del MVP.
