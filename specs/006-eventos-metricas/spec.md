# Feature Specification: Eventos espaciales, métricas y persistencia

**Feature Branch**: `feature/006-eventos-metricas`

**Azure Boards**: Feature #14, hija del Epic #1 `MVP funcional para el 2 de octubre de 2026`. User Stories #61, #62, #63 y #64.

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "vamos con la feature #14"

## Clarifications

### Session 2026-09-30

- Q: ¿La permanencia observable se mide solo en la zona frontal? → A: Sí. Solo en la zona frontal. La zona interior y la vidriera no generan permanencia ni ocupación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Convertir el seguimiento en eventos de la escena (Priority: P1) · Boards #61

Como analista, quiero que el seguimiento anónimo de una sesión ya analizada se convierta en hechos de negocio de esa escena, para calcular después las métricas a partir de un relato estable y no de cada instante del video.

**Why this priority**: Sin eventos no hay métricas nuevas ni una consulta que el tablero o el chat puedan reutilizar. Es el camino crítico de la Feature #14.

**Independent Test**: Con una sesión cuyo análisis terminó bien y una escena con zona frontal, línea de entrada y sentido, se obtienen los hechos de esa sesión. Un caso sintético de oscilación sobre la línea y otro de reaparición con otro identificador se pueden comprobar sin video real.

**Acceptance Scenarios**:

1. **Given** un análisis completado de una sesión con zona frontal y línea de entrada, **When** se generan los hechos, **Then** cada hecho pertenece solo a esa sesión, esa cámara y ese análisis, y queda atado al instante del video en que ocurrió.
2. **Given** el pie de un identificador temporal que cruza el tramo dibujado de la línea de entrada en el sentido configurado, **When** se evalúa el cruce, **Then** queda una entrada al local. El sentido contrario queda como salida. Cruzar la prolongación de la línea, fuera del tramo dibujado, no cuenta.
3. **Given** el pie de un identificador que entra o sale de una zona configurada de esa escena, **When** se evalúa la zona, **Then** queda el hecho de entrada o de salida de esa zona.
4. **Given** un identificador cuyo pie estuvo en la zona frontal y no registró una entrada al local, **When** se cierra su paso, **Then** queda un paso frente al local.
5. **Given** un identificador que permanece observable dentro de la zona frontal y luego la deja sin perderse el seguimiento, **When** se cierra esa estadía, **Then** queda una permanencia observable con su duración en tiempo del video. El tiempo en la zona interior o en la vidriera no genera esa permanencia.
6. **Given** el mismo identificador que cruza la línea en un sentido y en el contrario dentro de la ventana de oscilación ya usada por el análisis, **When** se generan los hechos, **Then** esos cruces no se confirman como entrada ni como salida.
7. **Given** un identificador que se pierde, **When** desaparece, **Then** no se genera una salida ni se inventa una permanencia. Un identificador nuevo no hereda el hecho del anterior.

---

### User Story 2 - Obtener las ocho métricas de una sesión (Priority: P1) · Boards #62

Como analista, quiero las ocho métricas comprometidas de una sesión ya analizada, con rótulos que no prometan más de lo que la cámara puede ver, para leer el resultado sin reinterpretar el video.

**Why this priority**: Es el entregable de negocio de la feature. Depende de los hechos de la historia anterior y, para tres medidas, de los números oficiales que el análisis ya cerró.

**Independent Test**: Sobre un caso con resultado calculado a mano, las ocho métricas coinciden con ese resultado. Calcularlas de nuevo con los mismos hechos devuelve los mismos números. Un caso sin personas deja ceros o valores no disponibles, nunca un número inventado.

**Acceptance Scenarios**:

1. **Given** un análisis completado, **When** se consultan las métricas de la sesión, **Then** están las ocho: tráfico total, flujo temporal, paso frente al local, entradas, salidas, tasa de ingreso, permanencia observable y ocupación observable, más el horario pico derivado del flujo.
2. **Given** esas métricas, **When** se muestran, **Then** el tráfico total se rotula como estimación de visitas, la ocupación como visible y la permanencia como observable.
3. **Given** un análisis completado, **When** se leen entradas, salidas y ocupación visible, **Then** son los números oficiales ya cerrados por ese análisis, no un segundo cálculo distinto.
4. **Given** los mismos hechos guardados, **When** las métricas se calculan otra vez, **Then** el resultado es el mismo.
5. **Given** un video sin fecha real, **When** se arma el flujo temporal y el horario pico, **Then** los intervalos se miden desde el inicio del video y no con el reloj de la computadora.
6. **Given** un local sin pasos frente a él, o una sesión sin permanencias observables cerradas, **When** se pide la tasa de ingreso o la permanencia, **Then** el valor figura como no disponible.

---

### User Story 3 - Consultar sesiones, hechos y métricas (Priority: P1) · Boards #63

Como tablero o como chat, quiero pedir resultados de una sesión, de un local y de un intervalo, para mostrar o responder siempre con las mismas cifras.

**Why this priority**: El tablero y el chat mínimo del MVP no calculan: leen. Esta consulta es el contrato que ambos van a usar.

**Independent Test**: Una consulta de una sesión completada devuelve sus métricas y sus hechos filtrados. La misma consulta sobre otra sesión no devuelve esos datos. Pedir un intervalo devuelve solo lo que cae en ese tramo del video.

**Acceptance Scenarios**:

1. **Given** sesiones ya analizadas, **When** se pide el listado, **Then** cada sesión se distingue de las demás y no arrastra hechos ni métricas ajenas.
2. **Given** una sesión completada y un local de su escena, **When** se piden las métricas, **Then** la respuesta trae las ocho métricas de ese local en esa sesión, con los rótulos de la historia anterior.
3. **Given** una sesión y un intervalo del video, **When** se piden los hechos, **Then** solo aparecen los de esa sesión cuyo instante de video cae en el intervalo, y se pueden limitar a un local.
4. **Given** la misma pregunta hecha para el tablero y para el chat, **When** ambos consultan, **Then** reciben las mismas cifras. El chat no las recalcula desde el video.

---

### User Story 4 - Contrastar el resultado con un conteo manual (Priority: P2) · Boards #64

Como equipo, quiero comparar entradas, salidas y pasos de al menos un video elegido contra un conteo hecho a mano, para poder defender las cifras y dejar escritas las diferencias.

**Why this priority**: Las tres historias anteriores ya entregan un resultado usable. Esta cierra la defensa del número, pero no bloquea la consulta.

**Independent Test**: Sobre un clip del material elegido, con entradas, salidas y pasos contados a mano, queda un informe de diferencias clasificadas. El recorrido de prueba sintético no exige ese conteo manual.

**Acceptance Scenarios**:

1. **Given** un clip del material elegido y un conteo manual de entradas, salidas y pasos frente al local, **When** se contrastan con las métricas de esa sesión, **Then** queda registrada cada diferencia y su clasificación.
2. **Given** ese contraste, **When** se lee el informe, **Then** no afirma que el conteo automático sea exacto: describe en qué coincidió y en qué no.
3. **Given** el recorrido habitual de pruebas del equipo, **When** se ejecuta sin el clip real ni el conteo manual, **Then** las otras historias siguen pudiendo darse por válidas.

---

### Edge Cases

- El análisis no está completado (sigue en curso, falló o fue cancelado): los hechos y las métricas no se presentan como resultado completo de la sesión.
- El seguimiento se pierde sobre la línea o dentro de la zona frontal: no se genera una salida ni una permanencia. Un identificador nuevo no continúa la estadía anterior.
- El identificador solo estuvo en la zona interior o en la vidriera: no se genera permanencia observable ni se suma ocupación por ese tiempo.
- La persona oscila sobre la línea: no se confirman entradas ni salidas duplicadas por ese vaivén, con la misma ventana que ya usa el análisis.
- El cruce ocurre fuera del tramo dibujado de la línea: no cuenta.
- No hay personas, no hay pasos o no hay permanencias cerradas: el conteo es cero o no disponible. Una tasa sin denominador se muestra como no disponible.
- El video no tiene fecha ni hora reales: el flujo y el horario pico usan el tiempo relativo al inicio del video.
- Hay empate entre dos intervalos del flujo: el horario pico es el más temprano.
- Dos sesiones se consultan a la vez: ninguna ve hechos ni métricas de la otra.
- La escena no tiene zona frontal o no tiene línea de entrada: no se inventan pasos ni entradas de ese local; esas métricas quedan no disponibles y el motivo es reconocible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A partir de un análisis completado, el sistema MUST generar hechos de negocio de esa sesión: entrada y salida de zona, paso frente al local, entrada y salida del local, y permanencia observable.
- **FR-002**: Cada hecho MUST pertenecer a una sola sesión, una sola cámara y un solo análisis, y MUST guardar el instante del video en que ocurrió. Los tiempos MUST calcularse con el video, nunca con la duración del procesamiento.
- **FR-003**: Una entrada o salida del local MUST contar solo cuando el pie cruza el tramo dibujado de la línea, en el sentido configurado o en el contrario. La prolongación de la línea MUST NOT contar.
- **FR-004**: El sistema MUST NOT confirmar entradas ni salidas duplicadas por oscilación, usando la misma ventana que el análisis ya usa para sus números oficiales. Perder el seguimiento MUST NOT generar una salida ni una permanencia. Un identificador temporal nuevo MUST NOT heredar hechos del anterior.
- **FR-005**: Una permanencia observable MUST medirse solo en la zona frontal, mientras el mismo identificador sigue visible y luego la deja. La zona interior y la vidriera MUST NOT generar permanencia ni ocupación. MUST rotularse como observable.
- **FR-006**: El sistema MUST calcular, para cada local de una sesión completada, estas medidas: tráfico total, flujo temporal, paso frente al local, entradas, salidas, tasa de ingreso, permanencia observable (media y mediana) y ocupación observable. El horario pico MUST ser el intervalo del flujo temporal con mayor tráfico; si hay empate, el más temprano.
- **FR-007**: El tráfico total MUST rotularse como estimación de visitas y MUST contarse como identificadores temporales distintos vistos en la sesión. MUST NOT presentarse como personas únicas.
- **FR-008**: Entradas, salidas y ocupación visible de un análisis completado MUST ser los números oficiales ya cerrados por ese análisis. Esta feature MUST leerlos y MUST NOT reemplazarlos con otro cálculo. El paso frente al local y el resto de las medidas MUST poder reconstruirse desde los hechos guardados, y una segunda pasada MUST devolver los mismos números.
- **FR-009**: La ocupación MUST rotularse como visible, MUST ser la ocupación visible oficial de la zona frontal y MUST distinguirse de la ocupación total del local. El tiempo en la zona interior o en la vidriera MUST NOT sumar ocupación. La permanencia MUST rotularse como observable.
- **FR-010**: El flujo temporal MUST repartir el tráfico en intervalos iguales de un minuto de video, cubriendo toda la grabación. Si el video dura menos de un minuto, hay un solo intervalo. La suma de los intervalos MUST coincidir con el tráfico total. Si el video no tiene fecha real, los intervalos MUST contarse desde el inicio del video.
- **FR-011**: La tasa de ingreso de un local MUST ser las entradas oficiales divididas por los pasos frente a ese local. Si no hay pasos, o si no hay permanencias observables cerradas al pedir media o mediana, el sistema MUST mostrar el valor como no disponible.
- **FR-012**: Quien consulta MUST poder listar sesiones, pedir las métricas de una sesión y un local, y pedir los hechos de una sesión filtrados por local y por un intervalo del video. El tablero y el chat MUST recibir las mismas cifras por esa consulta. El chat MUST NOT calcularlas desde el video.
- **FR-013**: Las consultas MUST aislar los datos entre sesiones. Un análisis que no está completado MUST NOT presentarse como resultado completo.
- **FR-014**: Si a un local le falta la zona frontal o la línea de entrada, el sistema MUST dejar no disponibles las métricas que dependen de ese elemento y MUST indicar un motivo reconocible, sin inventar el dato.
- **FR-015**: El equipo MUST contrastar, en al menos un clip del material elegido, las entradas, las salidas y los pasos frente al local contra un conteo manual, y MUST dejar escritas las diferencias y su clasificación. Ese contraste MUST NOT ser requisito para dar por válida la consulta en el recorrido de prueba.

### Key Entities

- **Hecho de escena**: Entrada o salida de zona, paso frente al local, entrada o salida del local, o permanencia observable. Pertenece a una sesión, una cámara y un análisis, y tiene instante de video.
- **Métrica de sesión**: Una de las ocho medidas de un local en una sesión completada, con su rótulo (estimación de visitas, visible u observable) y, si no se puede calcular, la marca de no disponible.
- **Flujo temporal**: Serie de conteos del tráfico en intervalos iguales del video. El horario pico es un intervalo de esa serie.
- **Consulta de resultados**: Pedido de sesiones, métricas o hechos, acotado a una sesión y, cuando corresponde, a un local y a un intervalo del video.
- **Contraste manual**: Comparación, para un clip elegido, entre el conteo a mano de entradas, salidas y pasos y las métricas de esa sesión, con las diferencias clasificadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el caso sintético de oscilación, el 100 % de los cruces de ida y vuelta dentro de la ventana quedan sin confirmar como entrada o salida. En el caso de un identificador que se pierde y otro que aparece, no hay salida inventada ni permanencia heredada.
- **SC-002**: En un caso con resultado calculado a mano, las ocho métricas y el horario pico coinciden con ese resultado. Calcularlas de nuevo no cambia ningún número.
- **SC-003**: En una sesión completada, entradas, salidas y ocupación visible consultadas por esta feature son iguales a los números oficiales del análisis, en el 100 % de las sesiones del caso de prueba.
- **SC-004**: Una tasa sin pasos, o una permanencia sin estadías cerradas, se muestra como no disponible en el 100 % de esos casos. Ninguna consulta devuelve un valor inventado.
- **SC-005**: Al consultar dos sesiones, el 100 % de los hechos y de las métricas devueltos pertenecen a la sesión pedida.
- **SC-006**: En al menos un clip del material elegido, el informe de contraste incluye el conteo manual y el automático de entradas, salidas y pasos, y clasifica cada diferencia. El recorrido de prueba sin ese clip sigue pudiendo validar las otras historias.

## Assumptions

- La sesión, la escena (zona frontal, línea de entrada y sentido) y un análisis completado ya existen (Features #12 y #13). Esta feature no vuelve a definir la carga, el editor ni el seguimiento.
- Entradas, salidas y ocupación visible oficiales son las que el análisis completado ya guardó. Esta feature las lee. El paso frente al local, el tráfico, el flujo, la tasa, la permanencia y el horario pico se apoyan en los hechos de esta feature y, donde corresponde, en esos tres oficiales.
- El tráfico total es una estimación de visitas: identificadores temporales distintos de esa sesión y esa cámara. No es una persona única ni un visitante reconocido entre cámaras.
- Un paso frente al local es un identificador cuyo pie estuvo en la zona frontal y que no tuvo una entrada confirmada al local.
- La tasa de ingreso es entradas oficiales divididas por pasos frente a ese local. No es entradas por hora.
- La permanencia observable es la media y la mediana, en segundos del video, de las estadías cerradas en la zona frontal porque el identificador la dejó sin perderse. La zona interior y la vidriera no generan permanencia ni ocupación. No se usa el reloj de la computadora.
- El flujo temporal usa intervalos de un minuto de video. El horario pico es el intervalo de mayor tráfico y, en empate, el más temprano. Sin fecha real en el video, ese pico es un tramo de la grabación, no una hora del reloj.
- La ventana de oscilación es la misma que ya usa el análisis para no duplicar cruces. No se abre otra regla distinta para los hechos de entrada y salida.
- El tablero, el chat, el mapa de calor, la exposición, la atención, la posible compra y los grupos quedan fuera. El chat, cuando exista, va a usar esta consulta y no va a calcular desde el video.
- El contraste manual usa el protocolo de diferencias del experimento de videos ya hecho. Alcanza con un clip del material elegido. No se promete que el automático coincida con la mano.
- Un identificador temporal no es una identidad real y no se sigue entre cámaras.
