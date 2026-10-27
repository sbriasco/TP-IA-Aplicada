# Feature Specification: Comparaciones e insights

**Feature Branch**: `feature/013-comparaciones-insights`

**Azure Boards**: Feature #10, hija del Epic #3 `Evolución final para el 6 de noviembre de 2026`.

**Created**: 2026-10-27

**Status**: Clarified

**Input**: User description: Feature #10 — Incorporar comparaciones entre sesiones, días, horarios o comercios, además de insights derivados de métricas estructuradas. Esta Feature no depende de detectar bolsas ni de la Feature de posible compra. Condicionada a contar con varias sesiones comparables y métricas consistentes.

## Clarifications

### Session 2026-10-27

- Q: ¿Qué ejes de comparación deben quedar comprometidos en la primera entrega de esta feature? → A: Sesión vs sesión es el mínimo entregable (P1); día, horario y zona son ampliación P2 de la misma feature si el tiempo alcanza.
- Q: ¿Qué familias de cifras MUST entrar en la comparación de la primera entrega? → A: Obligatorio: ocho métricas + tasa de ingreso + horario pico; funnel, patrones/grupos y posible compra estimada se muestran solo cuando existan en esas sesiones.
- Q: Si una familia opcional existe en una sesión de la comparación pero no en otra, ¿cómo se muestra esa fila? → A: Fila visible; lado faltante = no disponible con motivo; sin diferencia inventada.
- Q: Cuando se compare por franja horaria (eje P2), ¿qué reloj define esa franja? → A: Tiempo del video (timestamps del archivo ya usados en métricas).
- Q: Al comparar por zona de análisis (eje P2), ¿cómo se decide que dos zonas de sesiones distintas son la misma? → A: Misma cámara + mismo nombre de zona, aunque cambie el shop_id entre versiones de escena; nunca unificar solo por nombre entre cámaras.
- Q: Cuando se compara por día (eje P2), ¿qué fecha define el «día» de cada sesión? → A: Fecha UTC de cierre del análisis (`finished_at`); no es el día del local ni el tiempo del video (excepción documentada).
- Q: Para mostrar las ocho métricas, la tasa de ingreso y el horario pico en una comparación, ¿debe el analista indicar el nombre de la zona de análisis? → A: Sí, obligatorio; se resuelve el local por ese nombre en cada sesión; si falta, celdas no disponibles.
- Q: Si la comparación tiene más de dos columnas, ¿cómo se calcula la relación o diferencia mostrada por cifra? → A: Relación/delta solo entre columna 1 y 2; columnas extra solo muestran valores.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Comparar cifras ya guardadas entre sesiones (Priority: P1)

Como analista, quiero elegir al menos dos sesiones de video ya analizadas y ver, lado a lado, las mismas cifras comerciales ya guardadas, para notar diferencias sin volver a abrir cada video ni recalcular desde el archivo.

**Why this priority**: Es el núcleo de la Feature #10 y no depende de bolsas ni de posible compra. Entrega valor con el historial y las métricas que el producto ya tiene.

**Independent Test**: Con dos o más sesiones de archivo completadas, un nombre de zona y cifras guardadas, se arma una comparación legible. Si falta una sesión, si no está completa o si una cifra no está disponible en un lado, eso se ve sin inventar un cero. No hace falta el chat ampliado.

**Acceptance Scenarios**:

1. **Given** al menos dos sesiones de video con análisis completado y un nombre de zona de análisis, **When** el analista las incluye en una comparación, **Then** ve las mismas familias de cifras en cada columna (o fila) y puede identificar cuál sesión es cuál por nombre y contexto visible (cámara o fecha), sin códigos técnicos.
2. **Given** una cifra disponible en ambas sesiones, **When** se lee la comparación, **Then** aparecen ambos valores y una diferencia o relación clara entre ellos (por ejemplo mayor, menor o empate), sin inventar redondeos de negocio distintos a los ya mostrados en el resultado individual.
3. **Given** una cifra no disponible en una de las sesiones, **When** se lee la comparación, **Then** ese lado se muestra como no disponible con el motivo ya conocido del producto, y no se reemplaza por cero ni se inventa una diferencia.
4. **Given** una sesión incompleta, fallida, cancelada o de cámara en vivo, **When** el analista intenta usarla como columna de comparación, **Then** no entra como resultado comparable completo (se rechaza o se explica por qué no sirve).
5. **Given** la misma comparación pedida dos veces con las mismas sesiones, **When** se leen los valores, **Then** coinciden. No se recalcula nada desde el video: solo se leen cifras ya guardadas.
6. **Given** las ocho métricas, la tasa de ingreso, el funnel, los patrones o la posible compra de cada sesión por separado, **When** existe una comparación, **Then** esas consultas individuales no cambian de cuerpo ni de valor.

---

### User Story 2 - Comparar por día, horario o zona de análisis cuando los datos lo permiten (Priority: P2)

Como analista, quiero agrupar o contrastar sesiones comparables por día, franja horaria o zona de análisis (comercio / local de la escena), para ver si un día, un horario o una zona se comportan distinto sin inventar un seguimiento entre cámaras.

**Why this priority**: Amplía la comparación entre sesiones cuando hay varias con métricas consistentes. Sigue sin depender de bolsas. Si no hay suficientes sesiones para un eje, ese eje queda no disponible.

**Independent Test**: Con un conjunto de sesiones de archivo completadas que comparten cámara o zona, se puede contrastar por al menos un eje de agrupación (día, horario o zona). Si el conjunto no alcanza para ese eje, se informa sin inventar grupos.

**Acceptance Scenarios**:

1. **Given** varias sesiones con distinta fecha UTC de cierre de análisis, **When** el analista compara por día, **Then** ve cifras agrupadas por esa fecha de `finished_at` (no por reloj del video ni día del local), sin inventar un calendario externo.
2. **Given** sesiones cuya duración o momento permite franjas horarias del tiempo del video, **When** el analista compara por horario, **Then** ve el contraste por franja solo donde hay datos del archivo; una franja sin sesiones no inventa tráfico ni usa la hora de registro o procesamiento.
3. **Given** sesiones de la misma cámara con zonas de análisis nombradas en su escena, **When** el analista compara por zona, **Then** las cifras se contrastan si comparten el mismo nombre de zona (aunque el identificador interno difiera entre versiones de escena); si falta en un lado, queda no disponible.
4. **Given** un eje sin suficientes sesiones comparables, **When** se pide esa comparación, **Then** el resultado dice que no hay datos suficientes y no muestra un ranking inventado.
5. **Given** dos zonas con el mismo nombre en cámaras distintas, **When** se comparan, **Then** no se tratan como la misma zona física entre cámaras: cada comparación deja claro el contexto de cámara o sesión.

---

### User Story 3 - Leer insights derivados de las métricas comparadas (Priority: P2)

Como analista, quiero ver insights cortos derivados solo de las métricas estructuradas de la comparación (por ejemplo qué lado es más alto en tráfico o en tasa de ingreso), para orientarme sin que el sistema invente causas, identidades o ventas.

**Why this priority**: Cumple la parte de «insights» de la Feature #10 sin abrir el chat ampliado. Los insights se calculan a partir de cifras ya guardadas, no desde el video ni con texto libre del modelo.

**Independent Test**: Sobre una comparación válida, aparecen uno o más insights verificables contra las cifras mostradas. Si no hay diferencia útil o faltan datos, se dice que no hay insight o que no está disponible. El chat mínimo no responde con estos insights.

**Acceptance Scenarios**:

1. **Given** una comparación con al menos una cifra disponible en ambos lados y valores distintos, **When** el analista lee los insights, **Then** ve afirmaciones que solo repiten o resumen esas diferencias (por ejemplo cuál sesión tiene más tráfico), sin explicar causas no medidas.
2. **Given** todas las cifras relevantes empatadas o no disponibles, **When** se piden insights, **Then** no se inventa un hallazgo: se indica que no hay diferencias destacables o que faltan datos.
3. **Given** un insight mostrado, **When** el analista lo confronta con la tabla o lista de la comparación, **Then** el 100 % de las afirmaciones numéricas coinciden con esas cifras.
4. **Given** el chat mínimo del producto, **When** se pregunta por la comparación o por un insight, **Then** no responde con estas cifras. Eso queda para el chat ampliado (Feature #11).
5. **Given** rótulos de estimación (tráfico, atención, posible compra u otros ya existentes), **When** un insight los menciona, **Then** conserva el carácter de estimación y no los presenta como verdad absoluta, venta o identidad.

---

### Edge Cases

- Menos de dos sesiones elegibles: no hay comparación completa; se indica qué falta.
- Sesión incompleta, fallida, cancelada o webcam: no entra como columna comparable completa.
- Cifra no disponible en un lado: no disponible con motivo; no cero inventado; no diferencia inventada.
- Nombre de zona ausente en la petición: petición inválida. Zona inexistente en una sesión: métricas de local de esa columna no disponibles.
- Familia opcional (funnel, patrones, posible compra) presente en un lado y ausente en otro: la fila permanece; el lado ausente es no disponible; no se omite la familia.
- Sesiones de distintas cámaras: se pueden contrastar solo si el analista las elige explícitamente; no se unifican tracks ni identidades entre cámaras.
- Zonas u horarios sin pares comparables: eje o celda no disponible.
- Misma sesión elegida dos veces: no cuenta como dos columnas distintas.
- Comparar de nuevo con las mismas entradas: mismos resultados (solo lectura de cifras guardadas).
- Insights sin diferencias o sin datos: no se fabrican hallazgos.
- Posible compra u otras estimaciones: si entran en la comparación, se leen como estimación; esta feature no depende de ellas para existir.
- Chat mínimo y chat ampliado: el mínimo no usa estas cifras; el ampliado las leerá después sin recalcular desde el video.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir armar una comparación a partir de al menos dos sesiones de video con análisis completado y un nombre de zona de análisis (nombre visible del local de escena), leyendo solo cifras ya guardadas. Las ocho métricas, la tasa de ingreso y el horario pico MUST resolverse en cada sesión por ese nombre; si la zona no existe en una sesión, esas celdas MUST quedar no disponibles. MUST NOT recalcular métricas desde el video ni ejecutar consultas arbitrarias generadas por un modelo.
- **FR-002**: Una sesión incompleta, fallida, cancelada o de cámara en vivo MUST NOT presentarse como columna de comparación completa. Las consultas MUST aislar los datos entre sesiones: una columna no muestra cifras de otra.
- **FR-003**: Para cada cifra incluida, el sistema MUST mostrar el valor de cada columna. La diferencia o relación (`relation` / `delta`) MUST calcularse solo entre la primera y la segunda columna cuando ambas están disponibles; columnas adicionales MUST mostrar su valor sin alterar ese par. Si un lado del par no está disponible, MUST mostrarlo como no disponible con motivo y MUST NOT inventar cero ni diferencia.
- **FR-004**: La primera entrega MUST permitir comparación sesión vs sesión (P1). Comparación por día, franja horaria y zona de análisis MAY implementarse en la misma feature como ampliación P2 si el tiempo alcanza; MUST NOT bloquear el cierre de P1 ni inventar grupos cuando falten sesiones comparables. Si se implementa el eje día, el grupo MUST usar la fecha de calendario UTC de `finished_at` del análisis completado; MUST NOT presentarse como día civil del local ni como tiempo del video (excepción explícita frente al reloj de archivo). Si se implementa el eje horario, la franja MUST basarse en el tiempo del video (timestamps del archivo), MUST NOT en el momento de registro ni de procesamiento de la sesión. Si se implementa el eje zona, dos columnas MUST considerarse la misma zona solo con la misma cámara y el mismo nombre de zona (aunque el `shop_id` cambie entre versiones de escena); MUST NOT unificar zonas solo por nombre entre cámaras distintas.
- **FR-005**: La comparación MUST incluir las ocho métricas comerciales, la tasa de ingreso y el horario pico. Funnel, patrones/grupos y posible compra estimada MUST incluirse como filas cuando al menos una columna tenga cifras guardadas de esa familia; el lado sin datos MUST mostrarse como no disponible con motivo, MUST NOT omitirse la fila ni inventarse diferencia, y MUST NOT hacer depender la feature de bolsas ni de que exista posible compra.
- **FR-006**: El sistema MUST ofrecer insights derivados únicamente de las métricas estructuradas de esa comparación. MUST NOT inventar causas, identidades, parentesco, ventas confirmadas ni seguimiento entre cámaras. MUST NOT usar el modelo de chat para redactar esos insights en esta feature.
- **FR-007**: Un insight MUST ser verificable contra las cifras mostradas. Si no hay diferencias destacables o faltan datos, el sistema MUST indicarlo en lugar de inventar un hallazgo.
- **FR-008**: Las consultas ya existentes de métricas, hechos, funnel, patrones, posible compra, historial y chat mínimo MUST conservar su comportamiento y su cuerpo. El chat mínimo MUST NOT responder con la comparación ni con estos insights.
- **FR-009**: Esta feature MUST NOT depender de la detección de bolsas ni de que exista posible compra estimada. Cuando la fila de posible compra estimada aparece en la comparación, MUST conservarse el rótulo de estimación y de que no es una venta.
- **FR-010**: Comparar otra vez con las mismas sesiones y el mismo eje MUST devolver las mismas cifras e insights. Los tiempos y denominadores MUST respetar las reglas ya vigentes del producto (no disponible vs cero real).

### Key Entities

- **Comparación**: Conjunto de dos o más sesiones (u agrupaciones derivadas) elegidas por el analista para contrastar cifras ya guardadas.
- **Columna comparable**: Una sesión o un grupo (día, horario o zona) que aporta un lado de cada cifra; puede estar completa o parcialmente no disponible.
- **Cifra contrastada**: Una métrica o indicador ya persistido, alineado por nombre entre columnas, con valores y disponibilidad por celda; la diferencia/relación, si aplica, es solo entre la primera y la segunda columna.
- **Insight derivado**: Afirmación breve generada solo a partir de las cifras contrastadas disponibles; no es un diagnóstico causal ni un mensaje del chat ampliado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las comparaciones con dos sesiones de archivo completadas y al menos una cifra disponible en ambos lados, el analista ve ambos valores y una diferencia o relación correcta sin abrir los videos.
- **SC-002**: En el 100 % de los casos con una cifra no disponible en un solo lado, ese lado se muestra como no disponible y no aparece un cero inventado ni una diferencia inventada.
- **SC-003**: El 100 % de los insights mostrados coinciden con las cifras de esa comparación; ninguno afirma venta, identidad o causa no medida. Si no hay diferencias o faltan datos, el 100 % de esas situaciones se informan sin inventar un hallazgo.
- **SC-004**: En el 100 % de las sesiones del caso de prueba, las consultas individuales de métricas, funnel, patrones y posible compra quedan iguales después de usar comparaciones e insights.
- **SC-005**: En el 100 % de los intentos con menos de dos sesiones elegibles, o solo con webcam/incompletas, no se presenta una comparación completa falsa.
- **SC-006**: Un analista reconoce, sin ayuda técnica, qué está comparando (sesiones u eje elegido) y qué insight destaca, en una sola lectura de la pantalla de comparación.
- **SC-007**: El chat mínimo no incorpora estas cifras en el 100 % de las preguntas de prueba sobre comparación o insights.

## Assumptions

- El historial de sesiones procesadas, el análisis completado de archivo y las métricas (y, si aplican, funnel/patrones) ya existen. Esta feature no redefine carga, escena, tracking ni el chat ampliado.
- «Comercio» en el enunciado de Boards se interpreta como zona de análisis / local de la escena ya configurado (`shop`), no como un comercio real identificado entre cámaras. La comparación exige el nombre visible de esa zona. Emparejamiento entre sesiones (eje P2): misma cámara + mismo nombre de zona.
- Día (P2) = fecha UTC de `finished_at` del análisis completado: metadato del historial, no día del local ni tiempo del video. Horario (P2) usa el tiempo del video, no el registro ni el procesamiento. No se inventa un calendario de local comercial externo.
- Varias sesiones comparables implica al menos dos análisis de archivo completados con métricas consistentes (mismos códigos de cifra cuando están disponibles).
- Los ejes día / horario / zona son deseables (P2) dentro de esta feature; el compromiso mínimo de entrega es sesión vs sesión.
- Los insights de esta feature son reglas sobre métricas estructuradas, no texto libre del modelo. El chat ampliado (Feature #11) podrá leer comparación e insights después, sin recalcular desde el video.
- Posible compra y bolsas quedan fuera de la dependencia: la feature funciona aunque esas cifras no existan. Funnel, patrones y posible compra son filas opcionales de lectura cuando ya están guardadas.
- Webcam, análisis incompletos y chat mínimo quedan fuera del alcance de producir o narrar estas comparaciones.
- No hay reconocimiento facial, identidad real, seguimiento entre cámaras ni confirmación de compras.
