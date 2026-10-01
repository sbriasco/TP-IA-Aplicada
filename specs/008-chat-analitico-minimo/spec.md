# Feature Specification: Chat analítico mínimo

**Feature Branch**: `feature/008-chat-analitico-minimo`

**Azure Boards**: Feature #16, hija del Epic #1 `MVP funcional para el 2 de octubre de 2026`. User Stories #68, #69, #70, #71 y #72.

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "vamos con la feature #16"

## Clarifications

### Session 2026-09-30

- Q: ¿El alineamiento con las features ya especificadas obliga a cambiar esta spec? → A: No. Las cinco cifras siguen siendo las ya registradas de toda la sesión. La herramienta de prueba con datos fijos no responde el chat del producto.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar solo las cifras ya registradas (Priority: P1) · Boards #68

Como equipo, quiero que el chat solo pueda citar cinco cifras ya registradas de una sesión y un local, para que ninguna respuesta calcule tráfico, ingresos, ocupación, permanencia ni horario pico por su cuenta.

**Why this priority**: Si el chat inventa una cifra, el analista no puede fiarse del resto del producto. Es el camino crítico de la Feature #16 y no depende de redactar una respuesta en lenguaje natural.

**Independent Test**: Con una sesión completada y sus cifras ya registradas, cada una de las cinco consultas devuelve exactamente esa cifra, o «no disponible» cuando la cifra ya estaba no disponible. No hace falta formular la pregunta en lenguaje natural ni usar el servicio de redacción.

**Acceptance Scenarios**:

1. **Given** una sesión completada y un local, **When** se consultan las cifras que el chat puede usar, **Then** están el tráfico, los ingresos de ese local, la ocupación visible, la permanencia observable y el horario pico, y cada una coincide con la cifra ya registrada de ese local para toda la sesión.
2. **Given** una de esas cifras marcada como no disponible, **When** se consulta, **Then** el resultado es no disponible, con el motivo si ya existía, y no un cero inventado.
3. **Given** dos sesiones, **When** se consulta una, **Then** ninguna cifra pertenece a la otra.
4. **Given** una pregunta por salidas, pasos, tasa de ingreso u otra cifra que no sea una de esas cinco, **When** se consulta, **Then** no se inventa el número ni se calcula desde el video.

---

### User Story 2 - Preguntar por una sesión y recibir cifras respaldadas (Priority: P1) · Boards #69

Como usuario, quiero preguntar por una sesión y recibir una respuesta cuyas cifras salgan de lo ya registrado, para no tener que leer el tablero cifra por cifra.

**Why this priority**: Es la pregunta que el MVP promete responder. Sin una respuesta respaldada, las consultas de la historia anterior no llegan al usuario.

**Independent Test**: Un conjunto fijo de preguntas sobre una sesión completada produce respuestas en las que cada número citado coincide con una cifra consultada de esa sesión y ese local. La prueba de que no hay cifras inventadas se puede hacer sin el servicio de redacción de pago. Una prueba manual con ese servicio es deseable y no bloquea el recorrido.

**Acceptance Scenarios**:

1. **Given** una sesión completada abierta en resultados, **When** el usuario pregunta por el tráfico, los ingresos, la ocupación, la permanencia o el horario pico, **Then** la respuesta cita el local, aclara que la cifra es de toda la sesión y usa el valor ya registrado.
2. **Given** una estimación de visitas o una permanencia observable, **When** aparece en la respuesta, **Then** se distingue de una observación, con las mismas palabras que ya usa el tablero.
3. **Given** el servicio de redacción tarda, **When** la pregunta está en curso, **Then** se ve un estado de espera y, si no llega una respuesta usable, un mensaje claro. El tablero sigue usable.
4. **Given** el servicio no está configurado, falla o no devuelve contenido usable, **When** el usuario pregunta, **Then** el chat lo explica y el resto de la aplicación sigue funcionando.
5. **Given** el conjunto de preguntas de prueba, **When** se revisan las respuestas, **Then** ningún número citado falta en las cifras consultadas para esa pregunta.

---

### User Story 3 - No afirmar ventas ni identidades (Priority: P1) · Boards #70

Como equipo, quiero que el chat se niegue a confirmar ventas, a identificar personas y a contestar fuera de las métricas, para no prometer algo que el producto no observa.

**Why this priority**: Una cifra correcta dicha como si fuera una venta o una persona identificada rompe el alcance comprometido. Tiene que valer aunque el servicio de redacción intente afirmarlo.

**Independent Test**: Un conjunto documentado de preguntas prohibidas y de respuestas límite se rechaza o se reformula. Ninguna confirma una venta, nombra a una persona ni presenta una estimación como un hecho.

**Acceptance Scenarios**:

1. **Given** una pregunta que pide confirmar una compra, identificar a una persona o seguirla entre cámaras, **When** se envía, **Then** el chat la rechaza y no consulta cifras para responderla.
2. **Given** una pregunta ajena a las cinco cifras y a las sesiones, **When** se envía, **Then** el chat dice que no puede responder eso y no inventa un análisis.
3. **Given** una respuesta que, pese al límite, afirmaría una venta, una identidad o trataría una estimación como observación, **When** se va a mostrar, **Then** no se muestra así: se rechaza o se corrige el lenguaje antes de llegar al usuario.

---

### User Story 4 - Chatear sobre la sesión que se está viendo (Priority: P1) · Boards #72

Como usuario, quiero un panel de chat junto a la sesión que estoy viendo, para preguntar sin salir de sus resultados.

**Why this priority**: Sin el panel, las respuestas no tienen lugar en el recorrido del tablero. Puede demostrarse con la sesión ya abierta, aunque todavía no se nombren otras sesiones.

**Independent Test**: En la pantalla de resultados de una sesión, el panel muestra la espera, el error y la respuesta, e indica qué cifras la respaldan. Cambiar de sesión no arrastra la respuesta de la anterior.

**Acceptance Scenarios**:

1. **Given** la pantalla de resultados de una sesión, **When** se abre el chat, **Then** las preguntas se refieren a esa sesión mientras el usuario no nombre otra.
2. **Given** una pregunta en curso, **When** el usuario mira el panel, **Then** ve espera. Si hay un error, ve el mensaje de error y puede seguir usando los resultados.
3. **Given** una respuesta mostrada, **When** el usuario la lee, **Then** ve qué cifras la respaldan: local, alcance de toda la sesión y valores usados.
4. **Given** el usuario abre otra sesión, **When** mira el chat, **Then** no se presentan las cifras de la sesión anterior como si fueran de la nueva.

---

### User Story 5 - Referirse a una sesión anterior (Priority: P2) · Boards #71

Como usuario, quiero nombrar una sesión anterior o pedir la última, para no tener que abrirla en el tablero antes de preguntar.

**Why this priority**: Completa el chat, pero el panel de la sesión abierta ya entrega el MVP. Si esta historia no entra, las historias anteriores siguen siendo válidas.

**Independent Test**: Con al menos dos sesiones de nombres distintos, «la última» elige la de procesamiento más reciente y un nombre elige esa sesión. Un nombre que coincide con más de una sesión no elige solo: el chat pregunta.

**Acceptance Scenarios**:

1. **Given** varias sesiones procesadas, **When** el usuario pide la última, **Then** la pregunta usa la sesión de procesamiento más reciente y no otra.
2. **Given** una sesión identificable por su nombre, **When** el usuario la nombra, **Then** las cifras de la respuesta son las de esa sesión.
3. **Given** dos sesiones que el pedido no distingue, **When** el usuario pregunta, **Then** el chat pide que aclare y no elige una al azar.

---

### Edge Cases

- No hay sesiones procesadas: el chat lo dice y no inventa una sesión ni una cifra.
- El análisis sigue en curso, falló o fue cancelado: el chat no presenta las cinco cifras como un resultado final. Si hay motivo de falla o cancelación, puede decirlo. No usa las tres cifras parciales del tablero como si ya fueran el cierre.
- Una cifra ya está no disponible: la respuesta dice no disponible y no la reemplaza por cero.
- Hay más de un local y la pregunta no dice cuál: si en resultados hay un local elegido, se usa ese. Si no hay uno elegido, el chat pregunta en lugar de mezclar locales.
- El usuario pide un tramo del video: las cinco cifras siguen siendo las de toda la sesión. El chat no arma cifras nuevas para el tramo ni parte un minuto del flujo.
- El usuario pide salidas, pasos, tasa de ingreso u otra cifra fuera de las cinco: el chat no la calcula ni la inventa.
- El video no está en este equipo: el chat igual puede citar las cifras ya registradas de esa sesión.
- El video no tiene fecha real: el horario pico se cita como tramo del video, no como hora del reloj.
- El servicio de redacción no está, tarda demasiado o vuelve vacío: hay un mensaje claro, el tablero sigue, y no se muestra una respuesta a medias como si fuera definitiva.
- Una pregunta prohibida llega disfrazada de pregunta por métricas: sigue rechazada, sin confirmar venta ni identidad.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El chat MUST poder consultar solo estas cinco cifras ya registradas, por sesión y por local: tráfico, ingresos de ese local, ocupación visible, permanencia observable y horario pico.
- **FR-002**: Cada cifra MUST coincidir con la ya registrada de ese local para toda la sesión. El chat MUST NOT calcularlas de nuevo desde el video, MUST NOT armar una cifra distinta para un tramo y MUST NOT consultar ni ejecutar una pregunta libre sobre los datos.
- **FR-003**: Si una de esas cifras no está disponible, el chat MUST decirlo, con el motivo cuando ya exista, y MUST NOT reemplazarla por cero.
- **FR-004**: El tráfico MUST citarse como estimación de visitas. La ocupación MUST citarse como visible y MUST distinguirse de la ocupación total del local. La permanencia MUST citarse como observable. El horario pico MUST ser el ya registrado y, si el video no tiene fecha real, MUST citarse como tramo del video.
- **FR-005**: Una respuesta mostrada al usuario MUST citar el local y dejar explícito que las cinco cifras son de toda la sesión. Todo número de la respuesta MUST provenir de una cifra consultada para esa pregunta.
- **FR-006**: Mientras el análisis no esté completado, o si falló o fue cancelado, el chat MUST NOT presentar las cinco cifras como resultado final.
- **FR-007**: El usuario MUST poder preguntar desde la sesión que está viendo. Cambiar de sesión MUST NOT mezclar las cifras de otra.
- **FR-008**: El panel MUST mostrar espera mientras la pregunta sigue, y un error claro si no hay respuesta usable. Ese fallo MUST NOT impedir usar el tablero. Si el servicio de redacción no está configurado, el resto de la aplicación MUST seguir funcionando.
- **FR-009**: El chat MUST rechazar confirmar una compra, identificar a una persona, seguirla entre cámaras o responder fuera de las sesiones y de las cinco cifras. Ese rechazo MUST valer antes de consultar cifras y también sobre el texto que se iba a mostrar.
- **FR-010**: El usuario MUST poder pedir la última sesión procesada o nombrar una. Si el pedido coincide con más de una sesión, o con más de un local y no hay un local ya elegido, el chat MUST pedir una aclaración y MUST NOT elegir solo.
- **FR-011**: Una pregunta MUST NOT disparar consultas de más ni dejar el uso del servicio de redacción sin límite. Los secretos de ese servicio MUST permanecer fuera del proyecto, de lo que ve el usuario y de lo que quede anotado de la pregunta.
- **FR-012**: Poder demostrar que las respuestas no inventan cifras MUST ser posible sin llamar al servicio de redacción de pago. Una prueba manual con ese servicio MUST NOT ser requisito para dar por válida esta feature.

### Key Entities

- **Consulta de cifra**: el pedido de una de las cinco cifras ya registradas para una sesión y un local. Puede volver un valor con su rótulo, o no disponible con un motivo.
- **Respuesta de chat**: el texto que ve el usuario, atado a una sesión, con el local, el alcance de toda la sesión y las cifras que lo respaldan.
- **Referencia de sesión**: la sesión abierta, la última procesada, o un nombre. Si no alcanza para distinguir una sola sesión, queda pendiente de aclaración.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una sesión completada de prueba, el 100 % de las cinco cifras consultadas coincide con las ya registradas de ese local para toda la sesión. Una cifra no disponible se informa así en el 100 % de esos casos.
- **SC-002**: En el conjunto de preguntas de prueba, el 100 % de los números que aparecen en las respuestas proviene de una cifra consultada para esa pregunta. Ninguna respuesta mezcla dos sesiones.
- **SC-003**: El 100 % de las preguntas documentadas sobre compras, identidad o temas ajenos a las métricas se rechaza, y ninguna respuesta mostrada confirma una venta ni identifica a una persona.
- **SC-004**: Desde la pantalla de resultados, el usuario hace una pregunta sin salir de esa sesión. La espera o el error se ven en el panel, y un fallo del chat deja el tablero usable.
- **SC-005**: Con dos sesiones, «la última» usa la de procesamiento más reciente en el 100 % de los intentos de prueba. Un nombre ambiguo no elige una sesión: el chat pide aclaración.
- **SC-006**: El recorrido que demuestra que no se inventan cifras se completa sin el servicio de redacción de pago.

## Assumptions

- La sesión, la escena, el análisis y las cifras ya registradas existen (Features #14 y #15). Esta feature no define métricas nuevas ni vuelve a calcularlas.
- Las cinco cifras son las de toda la sesión, con la misma regla que el tablero: un tramo del video no las cambia. «Ingresos por local» son las entradas oficiales ya registradas. «Ocupación máxima» del encargo es la ocupación visible ya registrada, no una ocupación total ni un máximo nuevo. La permanencia es la observable. El horario pico es el ya guardado.
- Salidas, pasos, tasa de ingreso y el detalle del flujo no son cifras que el chat pueda citar. El tablero sigue mostrándolas.
- Si el análisis no está completado, el chat no usa las cifras parciales del tablero como resultado final.
- Si en la pantalla de resultados hay un local elegido, el chat lo usa cuando la pregunta no nombra otro. Si hay varios locales y ninguno está elegido, pregunta.
- «La última sesión» es la de fecha de procesamiento más reciente, no la de un reloj dentro del video.
- El servicio de redacción es el que el equipo ya validó. No se incorpora otro. Una pregunta puede tardar lo bastante como para mostrar espera; si no hay respuesta usable, se corta con un mensaje y el tablero sigue.
- El chat ampliado, las comparaciones, los grupos, la atención y la posible compra quedan fuera. El contraste manual de la historia #64 también.
- No hay reconocimiento facial, identidad real, seguimiento entre cámaras ni confirmación de compras.
