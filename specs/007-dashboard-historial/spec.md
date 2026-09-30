# Feature Specification: Dashboard e historial

**Feature Branch**: `feature/007-dashboard-historial`

**Azure Boards**: Feature #15, hija del Epic #1 `MVP funcional para el 2 de octubre de 2026`. User Stories #65, #66 y #67.

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "vamos con la feature #15"

## Clarifications

### Session 2026-09-30

- Q: Si el analista elige un tramo del video, ¿los ocho indicadores siguen siendo los de toda la sesión? → A: Sí. Los ocho indicadores son siempre los de toda la sesión. El tramo solo filtra los hechos y muestra los minutos del flujo que caen adentro.
- Q: Mientras un análisis no terminó, ¿el tablero muestra las entradas, las salidas y la ocupación visible marcadas como parciales? → A: Sí. Solo esas tres, marcadas como parciales. Las otras cinco aparecen cuando el análisis está completado.
- Q: Si el video no está en este equipo, ¿el frame de referencia de la escena sigue visible? → A: Sí. No se reproduce el archivo. El frame de referencia sigue visible y, si hay muestra, el mapa se dibuja sobre ese frame.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver el historial de sesiones procesadas (Priority: P1) · Boards #65

Como usuario, quiero ver las sesiones ya procesadas y abrir sus resultados, para retomar un análisis sin volver a cargar el video ni reconfigurar la escena.

**Why this priority**: Sin un listado que distinga sesiones terminadas, fallidas y canceladas, el tablero no tiene por dónde empezar. Es el camino crítico de la Feature #15.

**Independent Test**: Con al menos una sesión completada, una fallida y una cancelada, el listado muestra nombre, video, estado, fecha de procesamiento y versión de configuración. Abrir la completada lleva a sus resultados. La fallida y la cancelada muestran el motivo y no se presentan como resultado final.

**Acceptance Scenarios**:

1. **Given** sesiones ya registradas, **When** se abre el historial, **Then** cada fila muestra el nombre de la sesión, el video, el estado del análisis, la fecha de procesamiento y la versión de configuración usada.
2. **Given** un análisis fallido o cancelado, **When** aparece en el historial, **Then** se ve el motivo y ese estado no se presenta como un resultado final.
3. **Given** una sesión completada, **When** el usuario la abre, **Then** llega a los resultados de esa sesión y de ninguna otra.
4. **Given** una sesión cuyo video no está en este equipo, **When** se abre, **Then** los resultados se pueden consultar igual, la reproducción del archivo se muestra como no disponible en este equipo y el frame de referencia de la escena sigue visible.

---

### User Story 2 - Ver indicadores y gráficos de una sesión (Priority: P1) · Boards #66

Como analista, quiero ver las métricas de un local en una sesión y acotar el flujo a un tramo del video, para leer el resultado sin reinterpretar el video.

**Why this priority**: Es el entregable visible del MVP. Depende del historial para elegir la sesión y de las cifras ya guardadas por la Feature #14.

**Independent Test**: En una sesión completada con al menos un local, los ocho indicadores coinciden con las cifras ya registradas de ese local para toda la sesión. El flujo muestra solo los minutos ya registrados que se solapan con el tramo elegido, cada uno entero. Una métrica no disponible se muestra como no disponible. Una estimación se distingue de una observación.

**Acceptance Scenarios**:

1. **Given** una sesión completada y un local de su escena, **When** se piden sus resultados, **Then** se ven los indicadores de tráfico, pasos, entradas, salidas, tasa de ingreso, permanencia observable, ocupación visible y horario pico, más el gráfico de flujo temporal.
2. **Given** esos resultados, **When** se comparan con las cifras ya registradas, **Then** cada indicador coincide con el de ese local en toda la sesión, y cada minuto del flujo visible es un minuto ya registrado que se solapa con el tramo elegido. El tablero no calcula otra vez desde el video ni arma indicadores nuevos para el tramo.
3. **Given** un local y un tramo del video elegidos por el analista, **When** se aplican, **Then** los ocho indicadores corresponden a ese local en toda la sesión. El flujo muestra, entero, cada minuto ya registrado que se solapa con el tramo. Los hechos listados son solo los de ese local cuyo instante cae en el tramo.
4. **Given** un análisis que todavía no terminó, **When** se abre en el tablero, **Then** se ven solo las entradas, las salidas y la ocupación visible, marcadas como parciales y distintas de una cifra final. Tráfico, pasos, tasa de ingreso, permanencia observable y horario pico no se muestran como cifras disponibles.
5. **Given** una sesión completada, **When** se muestran sus cifras, **Then** una estimación de visitas o una permanencia observable se distingue de una observación.
6. **Given** una tasa sin pasos o una permanencia sin estadías cerradas, **When** se muestra, **Then** figura como no disponible y no como cero inventado.

---

### User Story 3 - Ver un mapa de calor de posiciones (Priority: P2) · Boards #67

Como analista, quiero ver un mapa de calor de las posiciones de una sesión, para ubicar por dónde pasó la gente frente a la escena.

**Why this priority**: Ayuda a leer la escena, pero no bloquea el historial ni los indicadores. Si no entra en el plazo del MVP, las otras dos historias siguen siendo válidas.

**Independent Test**: Con una sesión que tiene una muestra de posiciones, el mapa se dibuja sobre la escena. Sin esa muestra, se muestra un estado vacío explicado y el resto del tablero sigue usable.

**Acceptance Scenarios**:

1. **Given** una sesión con una muestra de posiciones del recorrido, **When** se pide el mapa de calor, **Then** se ve sobre el frame de referencia de esa sesión.
2. **Given** una sesión sin esa muestra, **When** se pide el mapa, **Then** aparece un estado vacío que explica por qué no hay mapa, sin ocultar los indicadores.
3. **Given** una sesión con muestra de posiciones cuyo video no está en este equipo, **When** se pide el mapa, **Then** se dibuja sobre el frame de referencia. La reproducción del archivo sigue no disponible.

---

### Edge Cases

- No hay sesiones procesadas: el historial muestra un estado vacío y no inventa filas.
- Hay varias sesiones: cada una se distingue y abrir una no mezcla resultados de otra.
- El análisis sigue en curso: el historial lo muestra como no terminado. Si se ven cifras, son solo entradas, salidas y ocupación visible, marcadas como parciales. Las otras cinco no se presentan.
- El análisis falló o fue cancelado: se ve el motivo. No se muestran ocho indicadores como si el análisis hubiera terminado bien.
- El video no está en este equipo: los resultados siguen visibles, la reproducción del archivo dice que no está disponible aquí y el frame de referencia sigue visible.
- El video no tiene fecha real: la fecha del historial es la del procesamiento. El flujo y el horario pico siguen siendo tramos del video, no horas del reloj.
- Hay más de un local: el analista elige cuál ver. Cambiar de local cambia las cifras.
- El tramo pedido no tiene hechos: la lista de hechos de ese tramo queda vacía. Los ocho indicadores siguen siendo los de toda la sesión y no pasan a cero por el recorte. Un minuto del flujo no se parte: si se solapa con el tramo, se muestra entero.
- Falta la zona frontal o la línea: las métricas que ya quedaron no disponibles siguen viéndose así, con un motivo reconocible.
- No hay muestra de posiciones: el mapa de calor explica el vacío y no bloquea los indicadores.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El historial MUST listar las sesiones procesadas con nombre, video, estado del análisis, fecha de procesamiento y versión de configuración.
- **FR-002**: Un análisis fallido o cancelado MUST mostrar su motivo y MUST NOT presentarse como resultado final.
- **FR-003**: Abrir una sesión MUST mostrar solo los resultados de esa sesión.
- **FR-004**: Si el video de la sesión no está en este equipo, los resultados MUST poder consultarse igual, la reproducción del archivo MUST indicarse como no disponible en este equipo y el frame de referencia MUST seguir visible.
- **FR-005**: Para una sesión completada y un local, el tablero MUST mostrar tráfico, flujo temporal, pasos, entradas, salidas, tasa de ingreso, permanencia observable, ocupación visible y horario pico.
- **FR-006**: Cada uno de los ocho indicadores MUST coincidir con la cifra ya registrada de ese local para toda la sesión. Cada minuto del flujo que se muestra MUST ser un minuto ya registrado, mostrado entero, que se solapa con el tramo elegido. El tablero MUST NOT recalcular esas cifras desde el video ni armar indicadores nuevos para el tramo.
- **FR-007**: El analista MUST poder elegir el local y un tramo del video. Cambiar de local MUST cambiar los indicadores. Cambiar el tramo MUST filtrar los hechos y los minutos del flujo, y MUST NOT cambiar los ocho indicadores de la sesión.
- **FR-008**: Mientras el análisis no está completado, el tablero MUST mostrar solo entradas, salidas y ocupación visible, marcadas como parciales y distintas de una cifra final. MUST NOT mostrar tráfico, pasos, tasa de ingreso, permanencia observable ni horario pico como cifras disponibles hasta ese cierre. En un resultado completado, una estimación de visitas y una permanencia observable MUST distinguirse de una observación.
- **FR-009**: Una métrica no disponible MUST mostrarse como no disponible, con un motivo reconocible cuando ya exista, y MUST NOT reemplazarse por un cero inventado.
- **FR-010**: El tráfico MUST rotularse como estimación de visitas. La ocupación MUST rotularse como visible. La permanencia MUST rotularse como observable.
- **FR-011**: El mapa de calor, si se incluye, MUST construirse con la muestra de posiciones de esa sesión y MUST dibujarse sobre su frame de referencia, también si el archivo de video no está en este equipo. Si no hay muestra, MUST mostrar un estado vacío explicado y MUST NOT impedir el uso del historial ni de los indicadores.
- **FR-012**: El mapa de calor MUST NOT ser requisito para dar por válido el historial ni los indicadores.

### Key Entities

- **Sesión procesada**: una sesión con su video, el estado de su análisis, la fecha de procesamiento, el motivo si falló o se canceló, y la versión de configuración usada.
- **Resultado de local**: las cifras ya registradas de un local para toda la sesión, con su rótulo de estimación, observación o no disponible. El tramo del video solo acota los hechos y los minutos del flujo.
- **Mapa de calor**: la concentración de posiciones de la muestra de esa sesión sobre su frame de referencia. Puede no existir.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En un historial con sesiones completadas, fallidas y canceladas, el 100 % de las filas muestra nombre, video, estado, fecha de procesamiento y versión de configuración. El 100 % de las fallidas y canceladas muestra el motivo.
- **SC-002**: Abrir una sesión lleva a sus resultados en un solo paso. En una prueba con dos sesiones, el 100 % de las cifras visibles pertenecen a la sesión abierta.
- **SC-003**: En una sesión completada, el 100 % de los ocho indicadores coincide con las cifras ya registradas de ese local para toda la sesión. El 100 % de los minutos del flujo visibles se solapan con el tramo elegido, se muestran enteros y coinciden con los minutos ya registrados.
- **SC-004**: Una tasa sin pasos, una permanencia sin estadías cerradas y cualquier otra cifra no disponible se muestran como no disponibles en el 100 % de esos casos.
- **SC-005**: Con el video ausente en este equipo, los resultados de una sesión completada siguen pudiendo leerse, la reproducción del archivo informa que no está disponible aquí y el frame de referencia sigue visible. Si hay muestra de posiciones, el mapa se dibuja sobre ese frame.
- **SC-006**: El recorrido de prueba del historial y de los indicadores puede completarse sin el mapa de calor. Si el mapa se incluye y no hay muestra de posiciones, el estado vacío es explícito.

## Assumptions

- La carga de video, la escena y el análisis ya existen. Esta feature no vuelve a definirlos.
- Las cifras que muestra el tablero son las que la Feature #14 ya dejó registradas. No se inventan métricas nuevas ni se reinterpretan desde el video.
- La fecha de procesamiento es el momento en que se procesó el análisis, no un horario del video. El flujo y el horario pico siguen midiendo el tiempo del video.
- Si una sesión tiene más de un análisis, el historial muestra el más reciente. Los resultados que se abren son los de ese análisis.
- Al abrir una sesión completada, el tablero empieza por el primer local de la escena y por todo el video. Cambiar el local cambia los ocho indicadores. Cambiar el tramo no los cambia: solo filtra hechos y minutos del flujo.
- Un identificador temporal no es una persona única. El tráfico se muestra como estimación de visitas.
- Si el archivo de video no está en este equipo, no se reproduce. El frame de referencia sigue visible y el mapa, si hay muestra, se dibuja sobre ese frame.
- El mapa de calor es deseable y no bloquea el MVP. El chat analítico queda fuera: es la Feature #16.
- El contraste manual del clip real queda fuera: es la historia #64 y se hará más adelante.
- No hay reconocimiento facial, identidad real, seguimiento entre cámaras ni confirmación de compras.
