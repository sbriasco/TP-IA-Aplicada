# Feature Specification: Chat analítico ampliado

**Feature Branch**: `feature/014-chat-analitico-ampliado`

**Azure Boards**: Feature #11, hija del Epic #3 `Evolución final para el 6 de noviembre de 2026`. Depende de la estabilidad del contrato de analytics (Features #8, #10, #12 y lecturas asociadas) y de la disponibilidad validada del servicio de modelo en Azure.

**Created**: 2026-10-27

**Status**: Clarified

**Input**: User description: Chat analítico ampliado — el agente interpreta preguntas comerciales usando más herramientas acotadas de analytics (métricas de sesión, funnel, patrones/grupos, posible compra estimada y comparaciones/insights ya disponibles), sin RAG como fuente de cifras, sin SQL libre y sin calcular desde el video. Core de la materia: grounding por herramientas; el modelo solo redacta.

## Clarifications

### Session 2026-10-27

- Q: ¿El chat ampliado reemplaza el panel del chat mínimo en resultados, o coexisten dos modos distintos? → A: Un solo panel: el ampliado reemplaza el contrato del mínimo (mismas UI, más lecturas).
- Q: Cuando el analista pregunta desde el chat «¿cuál sesión tuvo más tráfico?», ¿cómo se eligen las sesiones del contraste? → A: Sesiones nombradas en la pregunta y/o «última» + sesión abierta, con las mismas reglas de elegibilidad que la comparación del producto.
- Q: Además de las cinco cifras del chat mínimo, funnel, patrones/grupos y posible compra estimada, ¿el chat ampliado puede citar también tasa de ingreso, salidas y pasos frente al local? → A: Sí: tasa, salidas y pasos además de las cinco + funnel/patrones/posible compra, cuando estén guardadas.
- Q: ¿El hilo de seguimiento (preguntas del estilo «¿y la permanencia?» sin repetir sesión/zona) queda comprometido en esta entrega o se deja fuera si no alcanza el tiempo? → A: Diferido: no bloquea cierre; preguntas independientes son suficientes.
- Q: ¿El chat de esta entrega debe poder contrastar también por día, franja horaria o zona, o solo sesión contra sesión? → A: También día, horario y zona desde el chat (mismo alcance P2 que la comparación del producto).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preguntar por más familias de cifras ya guardadas (Priority: P1)

Como analista, quiero preguntar en lenguaje natural por funnel, patrones o grupos estimados, posible compra estimada y las métricas comerciales ya conocidas de la sesión y zona que estoy viendo, y recibir una respuesta cuyas cifras salgan solo de lecturas ya registradas, para no depender solo del tablero ni de las cinco cifras del chat mínimo.

**Why this priority**: Es el núcleo de la Feature #11 frente al chat mínimo: ampliar el alcance interpretativo sin romper el principio de que el modelo no mide. Entrega valor con datos que el producto ya guarda.

**Independent Test**: Con una sesión de archivo completada y cifras/familias opcionales guardadas, un conjunto fijo de preguntas produce respuestas donde cada número citado coincide con una lectura consultada para esa pregunta. Se puede demostrar sin el servicio de redacción de pago. Si una familia no existe en esa sesión, la respuesta dice no disponible y no inventa el valor.

**Acceptance Scenarios**:

1. **Given** una sesión de archivo completada abierta en resultados con zona elegida y cifras base guardadas, **When** el analista pregunta por tráfico, entradas, salidas, pasos, tasa de ingreso, ocupación visible, permanencia, pico u otra métrica del catálogo cerrado para esa zona, **Then** la respuesta usa esos valores (o no disponible con motivo) y aclara el carácter de estimación u observación como en el tablero.
2. **Given** funnel, patrones/grupos o posible compra estimada guardados para esa sesión/zona, **When** el analista pregunta por ellos, **Then** la respuesta cita esas cifras como estimaciones cuando corresponda y no como venta confirmada ni identidad.
3. **Given** una familia opcional ausente en esa sesión, **When** se pregunta por ella, **Then** el chat indica que no hay dato guardado y no inventa un número ni ofrece recalcular desde el video.
4. **Given** el conjunto de preguntas de prueba, **When** se revisan los números citados, **Then** el 100 % proviene de una lectura consultada para esa pregunta; ninguna cifra se calcula en el modelo.
5. **Given** una sesión de cámara en vivo, **When** el analista intenta el chat comercial ampliado, **Then** no se exponen esas lecturas comerciales como si fueran el chat de archivo (misma exclusión de producto que el chat mínimo).

---

### User Story 2 - Preguntar por una comparación o un contraste entre sesiones (Priority: P1)

Como analista, quiero nombrar sesiones (o usar «la última» junto a la que estoy viendo) y preguntar cuál se comportó mejor en una cifra ya comparable —por sesión, por día, por franja horaria o por zona—, y recibir una respuesta respaldada por el mismo contraste que arma el producto (mismas reglas e ejes que la pantalla de comparaciones), para no abrir manualmente dos tableros ni inventar un ranking.

**Why this priority**: La Feature #11 pide explícitamente comparaciones e interpretación avanzada vía herramientas. Sin esto, el chat ampliado no supera al mínimo más allá de citar más filas de una sola sesión.

**Independent Test**: Con un conjunto de sesiones de archivo comparables (nombradas o abierta + última), una pregunta de contraste por sesión, día, horario o zona produce números que coinciden con el contraste consultable de esas sesiones y ese eje. Si faltan datos, hay ambigüedad o el eje no aplica, el chat lo dice sin inventar grupos.

**Acceptance Scenarios**:

1. **Given** la sesión abierta y otra nombrada (o «la última») ambas de archivo completadas y un nombre de zona, **When** el analista pregunta cuál tiene más tráfico (u otra cifra comparable) en esa zona con eje sesión, **Then** la respuesta indica el lado mayor o el empate usando ese contraste, no promedios inventados.
2. **Given** un conjunto de sesiones elegibles que permite eje día, horario o zona según las reglas del producto, **When** el analista pide ese contraste en el chat, **Then** los números y relaciones citados coinciden con el contraste de ese eje; si el eje no tiene grupos suficientes, se indica sin inventar columnas.
3. **Given** una cifra no disponible en un lado del contraste, **When** se pregunta por esa diferencia, **Then** el chat no inventa un delta: explica la no disponibilidad.
4. **Given** un pedido sin suficientes sesiones elegibles, con nombre ambiguo o sin indicar con qué comparar, **When** el analista pregunta, **Then** el chat pide aclaración o indica datos insuficientes, sin inventar columnas.
5. **Given** insights deterministas ya producidos por ese contraste, **When** el analista pide un resumen de diferencias, **Then** el chat puede reiterarlos solo si coinciden con esas afirmaciones; no inventa causas no medidas.
6. **Given** las consultas individuales de métricas/funnel/patrones/posible compra y el contraste de esas sesiones, **When** existe el chat ampliado, **Then** esas lecturas no cambian de valor por el hecho de chatear.
7. **Given** el analista no nombra otra sesión ni pide «la última» cuando el contraste las requiere, **When** pregunta «cuál fue mejor» en abstracto, **Then** el chat no elige un par al azar: pide que indique con qué comparar.

---

### User Story 3 - Seguir un hilo breve sin perder el grounding (Priority: P2) · Diferido

Como analista, quiero hacer una pregunta de seguimiento en el mismo panel (por ejemplo «¿y la permanencia?») sin repetir toda la sesión y la zona, y que la respuesta siga anclada a lecturas consultadas, para conversar con menos fricción en la demo.

**Why this priority**: Mejora la sensación de «agente», pero **no está comprometida en esta entrega**. US1 y US2 con preguntas independientes bastan para cerrar Feature #11.

**Independent Test** (cuando se implemente): Tras una pregunta contestada, un seguimiento sin repetir contexto usa la misma sesión/zona y solo cifras consultadas. Cambiar de sesión limpia el hilo.

**Acceptance Scenarios** (no bloquean el cierre de esta feature):

1. **Given** una respuesta ya mostrada sobre la sesión y zona abiertas, **When** el analista hace un seguimiento que no nombra otra sesión, **Then** el chat mantiene ese contexto y no mezcla otra sesión.
2. **Given** un seguimiento que pide una cifra nueva, **When** se responde, **Then** esa cifra también proviene de una lectura consultada (no de memoria inventada del modelo).
3. **Given** el analista abre otra sesión o cambia de zona, **When** mira el chat, **Then** el hilo anterior no se presenta como contexto de la nueva selección.
4. **Given** un seguimiento ambiguo, **When** se envía, **Then** el chat pide aclaración en lugar de adivinar.

---

### User Story 4 - Rechazar afirmaciones fuera de alcance y fallar con claridad (Priority: P1)

Como equipo, quiero que el chat ampliado siga negándose a confirmar compras, identidades o seguimiento entre cámaras, y que un fallo del servicio de modelo no rompa el tablero ni invente un análisis, para defender el alcance comprometido en la entrega final.

**Why this priority**: Ampliar herramientas aumenta el riesgo de lenguaje demasiado afirmativo (posible compra, grupos). El rechazo y el fallo seguro son tan críticos como en el chat mínimo.

**Independent Test**: Preguntas prohibidas se rechazan. Respuestas que afirmarían venta o identidad no se muestran así. Sin servicio de modelo, o con timeout, hay mensaje claro y el resto de la app sigue usable. La demostración de no inventar cifras sigue siendo posible sin el servicio de pago.

**Acceptance Scenarios**:

1. **Given** una pregunta que pide confirmar una compra, identificar a una persona o seguirla entre cámaras, **When** se envía, **Then** el chat la rechaza y no usa lecturas para «demostrar» esa afirmación.
2. **Given** una respuesta candidata que trataría posible compra (u otra estimación del catálogo) como hecho o venta, **When** se va a mostrar, **Then** se rechaza o se corrige el lenguaje antes de llegar al usuario.
3. **Given** el servicio de modelo no configurado, lento o vacío, **When** el analista pregunta, **Then** ve un error o espera claros; el tablero y la comparación siguen usables.
4. **Given** una pregunta ajena a analytics del producto, **When** se envía, **Then** el chat dice que no puede responder eso y no inventa un informe.

---

### Edge Cases

- No hay sesiones procesadas o la abierta no es elegible (incompleta, fallida, cancelada, vivo): el chat no presenta cifras como resultado final comparable.
- Zona no elegida y la pregunta no nombra una: el chat pide aclaración; no mezcla zonas.
- El usuario nombra una sesión ambigua: pide aclaración (misma regla que el chat mínimo).
- Pide un tramo del video para «recalcular» una métrica: no se arman cifras nuevas para el tramo; se usan las de toda la sesión o se indica el límite.
- Pide SQL, exportar la base o «mirar el video frame a frame»: se rechaza; no hay consulta libre ni procesamiento de video desde el chat.
- Contraste pedido con una sola sesión útil, sin «última» ni otro nombre, o con nombre ambiguo: se pide aclaración o se explica que hace falta contraste suficiente; no se elige un par al azar.
- Familia opcional presente en una sesión de un contraste y ausente en otra: se habla de no disponible; no se inventa diferencia.
- Secretos del servicio de modelo no aparecen en la UI ni en textos de error al usuario.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El chat ampliado MUST poder consultar, por sesión y zona cuando aplique, un catálogo cerrado de cifras ya registradas: las cinco del chat mínimo (tráfico, entradas, ocupación visible, permanencia observable, horario pico), más salidas, pasos frente al local, tasa de ingreso, y las familias opcionales funnel, patrones/grupos y posible compra estimada cuando existan. MUST NOT calcularlas desde el video ni ejecutar consultas libres sobre los datos.
- **FR-002**: El chat ampliado MUST poder obtener contrastes con las mismas reglas de elegibilidad, ejes (`session`, `day`, `time_of_day`, `zone`) y no disponibilidad que la Feature de comparaciones. El conjunto de sesiones del contraste MUST resolverse por nombres en la pregunta y/o por «la última» más la sesión abierta del panel; el eje MUST ser el que la pregunta indique o, si no lo indica y solo aplica sesión vs sesión, ese eje. Si no hay suficientes sesiones elegibles, el nombre es ambiguo, el eje no tiene grupos suficientes o no se indica con qué comparar, MUST pedir aclaración o indicar datos insuficientes. MUST NOT inventar columnas, agrupaciones, rankings ni deltas.
- **FR-003**: Todo número mostrado al usuario MUST provenir de una lectura o contraste consultado para esa pregunta. Una cifra no disponible MUST informarse como tal, con motivo si ya existe, y MUST NOT reemplazarse por cero. (Si en el futuro se implementa US3, el mismo anclaje MUST valer por turno.)
- **FR-004**: Tráfico, grupos y posible compra (y cualquier otra cifra del catálogo con rótulo de estimación) MUST citarse con el mismo carácter de estimación que el resto del producto. La atención estimada hacia vidrieras se consulta en el funnel del tablero, no como cifra propia del catálogo del chat. El chat MUST NOT confirmar compras, identidades reales ni seguimiento entre cámaras.
- **FR-005**: El modelo de lenguaje MUST usarse solo para interpretar la pregunta y redactar a partir de resultados de herramientas/lecturas. MUST NOT ser la fuente de verdad de las métricas. Un índice documental o recuperación por similitud (RAG) MUST NOT usarse como fuente de cifras comerciales en esta feature.
- **FR-006**: Las credenciales y las llamadas al servicio de modelo MUST permanecer en el backend. Cada pregunta independiente MUST respetar un presupuesto de llamadas acotado equivalente al del chat mínimo (sin ampliarlo por hilo en esta entrega).
- **FR-007**: El usuario MUST poder preguntar desde el panel junto a los resultados de la sesión que está viendo. Cambiar de sesión o zona MUST NOT mezclar cifras de otro contexto como si fueran del actual.
- **FR-008**: El panel MUST mostrar espera y errores claros. Un fallo del chat MUST NOT impedir usar el tablero ni la pantalla de comparaciones.
- **FR-009**: MUST ser posible demostrar que no se inventan cifras sin llamar al servicio de redacción de pago. Una prueba manual con ese servicio es deseable y no bloquea la aceptación de grounding.
- **FR-010**: Preguntas fuera de analytics del producto, o que pidan SQL libre / acceso al video crudo, MUST rechazarse con un mensaje claro.
- **FR-011**: El hilo de seguimiento (US3) queda **diferido**: MUST NOT bloquear el cierre de esta feature. Cada pregunta de esta entrega MUST tratarse como independiente respecto del historial de chat (el panel puede mostrar mensajes previos solo como UI local, sin exigir memoria de cifras entre turnos).
- **FR-012**: El chat ampliado MUST reemplazar el contrato de cifras citables del panel de resultados del chat mínimo: un solo panel, mismas reglas de aislamiento por sesión/zona, grounding, rechazo de compra/identidad y exclusión de webcam. MUST NOT mantener un segundo modo «solo cinco cifras» en esa UI. Las garantías de no inventar cifras y de prueba sin servicio de pago MUST conservarse.

### Key Entities

- **Lectura de analytics**: pedido acotado de una cifra o familia ya guardada (métricas de zona, pico, funnel, patrones, posible compra) para una sesión (y zona si aplica). Devuelve valor con rótulo o no disponible.
- **Contraste consultable**: resultado de comparación entre sesiones o grupos elegibles según las reglas del producto; incluye celdas, relación/delta cuando existen, e insights deterministas si ya los produce el producto.
- **Respuesta de chat ampliado**: texto al usuario atado a sesión/zona (y a contraste si hubo), con las cifras que lo respaldan y lenguaje de estimación cuando corresponde.
- **Hilo de seguimiento** (US3 diferido): fuera del compromiso de esta entrega; si se implementa después, secuencia breve en el mismo panel sin transferir contexto al cambiar de selección.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el conjunto de preguntas de prueba de una sola sesión, el 100 % de los números citados en las respuestas proviene de una lectura consultada para esa pregunta; el 100 % de las cifras no disponibles se informa como no disponible (nunca como cero inventado).
- **SC-002**: En el conjunto de preguntas de contraste, el 100 % de los números y relaciones citados coincide con un contraste consultable del producto; ningún ranking se inventa cuando faltan datos.
- **SC-003**: El 100 % de las preguntas documentadas sobre compra confirmada, identidad o seguimiento entre cámaras se rechaza o se reformula; ninguna respuesta mostrada confirma esos hechos.
- **SC-004**: Desde resultados, el analista completa al menos una pregunta ampliada y una de contraste sin salir del flujo de resultados/comparación; espera o error del chat dejan el resto de la UI usable.
- **SC-005**: El recorrido que demuestra grounding (números = lecturas) se completa sin el servicio de redacción de pago.
- **SC-006**: En una demo de curso, el equipo puede explicar en menos de dos minutos que el agente usa herramientas de analytics y no RAG ni SQL libre para las cifras.

## Assumptions

- El chat mínimo (Feature #8) aporta panel, guards y grounding; esta feature lo supersede en el panel de resultados con más lecturas. Métricas, funnel, patrones, posible compra y comparaciones/insights ya existen como lecturas de producto; no se redefinen denominadores ni se vuelve a medir desde el video.
- «Chat ampliado» = el mismo panel de resultados con más herramientas/lecturas + interpretación de contrastes; no es un segundo producto ni un agente con base vectorial obligatoria.
- RAG / knowledge store de Azure puede mencionarse en la defensa como alternativa descartada para cifras; no forma parte del alcance comprometido de esta feature.
- Webcam en vivo permanece fuera del chat comercial, igual que en el chat mínimo.
- El catálogo cerrado incluye las cinco del mínimo más salidas, pasos, tasa de ingreso, y funnel/patrones/posible compra cuando existan. Cifras fuera de ese catálogo siguen rechazadas (salvo contrastes del mismo catálogo vía US2).
- Los ejes de contraste desde el chat son los mismos que la pantalla de comparación (sesión, día UTC de cierre, franja de tiempo de video, zona); no se inventan calendarios ni unificación entre cámaras.
- Preguntas independientes bastan y son el compromiso de entrega; el hilo (US3) queda diferido y no bloquea Feature #11.
- El servicio de modelo es el ya validado por el equipo en Azure; no se cambia de proveedor en esta feature.
- No hay reconocimiento facial, identidad real, seguimiento entre cámaras ni confirmación de compras.
- Azure Boards Feature #11 se cierra al completar el alcance aquí; Features #9 y #10 de Boards corresponden a trabajo ya entregado en código y solo requieren actualización de estado en el tablero.
