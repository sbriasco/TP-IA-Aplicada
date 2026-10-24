# Feature Specification: Exposición, detención, atención estimada y funnel comercial

**Feature Branch**: `feature/010-exposicion-atencion-funnel`

**Azure Boards**: Feature #7, hija del Epic #3 `Evolución final para el 6 de noviembre de 2026`.

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "dale, hacelo" sobre la Feature #7: incorporar exposición a vidrieras, detención y atención estimada, y construir el funnel paso, exposición, detención, atención e ingreso usando visitas vinculadas y secuencias observadas.

## Clarifications

### Session 2026-10-23

- Q: Cuando el analista recorta un tramo del video en el resultado, ¿el funnel sigue siendo el de toda la sesión? → A: Sí. El funnel es de toda la sesión y el tramo no lo cambia.
- Q: Cuando una visita entra a la vidriera, ¿la exposición del funnel es la entrada de zona que ya se registra, o un hecho aparte? → A: Es la entrada de zona de vidriera ya existente, sin un segundo hecho.
- Q: Junto a la tasa de ingreso que ya muestra el resultado, ¿cómo se nombran las tasas del funnel? → A: Cada tasa del funnel se nombra por sus dos etapas. La tasa de ingreso ya existente queda igual.
- Q: Si un local no tiene zona de vidriera, ¿el ingreso vinculado queda no disponible, igual que la exposición, la detención y la atención? → A: Sí. El ingreso vinculado queda no disponible, con el motivo de que no hay zona de vidriera. El paso observado y las entradas ya cerradas siguen disponibles.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Distinguir exposición y detención en la vidriera (Priority: P1)

Como analista, quiero saber qué visitas vinculadas llegaron a la vidriera de un local y cuáles se detuvieron allí, para no tratar igual un roce con el borde y una parada observable.

**Why this priority**: Sin exposición y detención no hay atención ni funnel. Es el primer resultado nuevo de la Feature #7 y se puede leer aunque las etapas siguientes no existan.

**Independent Test**: Con una sesión de video ya analizada y un local con zona de vidriera, un caso sintético comprueba cuatro situaciones: el pie entra y sale enseguida, el pie permanece al menos el umbral y sale, el seguimiento se pierde adentro, y el pie oscila en el borde. La entrada a la vidriera no se guarda por segunda vez. No hace falta la pantalla del funnel ni un video real.

**Acceptance Scenarios**:

1. **Given** un análisis completado de una sesión con un local que tiene zona de vidriera, **When** se cierra una detención, **Then** ese hecho pertenece solo a esa sesión, esa cámara y ese análisis, y queda atado al instante del video en que ocurrió. La exposición no se guarda otra vez.
2. **Given** el pie de una visita vinculada que entra en la zona de vidriera de ese local y luego la deja sin perderse el seguimiento, **When** se evalúa la zona, **Then** la exposición es la entrada de zona ya registrada. No aparece un segundo hecho por el mismo ingreso. Esa entrada no genera permanencia observable ni suma ocupación.
3. **Given** la misma visita permanece dentro de la vidriera al menos 3 segundos de video y después la deja sin perderse el seguimiento, **When** se cierra esa estadía, **Then** queda una detención frente a la vidriera, además de la entrada de zona ya registrada.
4. **Given** la visita permanece en la vidriera menos de 3 segundos de video y la deja sin perderse, **When** se cierra esa estadía, **Then** queda la entrada de zona ya registrada y no queda la detención.
5. **Given** el seguimiento se pierde con el pie todavía dentro de la vidriera, **When** desaparece la visita, **Then** no se cierra una detención ni se inventa una duración. Una visita vinculada nueva no hereda el hecho de la anterior.
6. **Given** el video termina con el pie todavía dentro de la vidriera, **When** se cierran los hechos, **Then** no se confirma una detención por ese tramo inconcluso.
7. **Given** el mismo pie oscila en el borde de la vidriera, **When** se arma el funnel, **Then** esa visita cuenta una sola vez en la etapa de exposición. Las entradas de zona ya registradas no se borran ni se reescriben, y la ventana de oscilación de la línea de entrada no cambia.
8. **Given** un local sin zona de vidriera, **When** se piden exposición y detención, **Then** quedan no disponibles, con un motivo reconocible, y no se inventa una vidriera.

---

### User Story 2 - Armar el funnel con visitas vinculadas (Priority: P1)

Como analista, quiero el funnel de cada local en cinco etapas —paso observado, exposición, detención, atención estimada e ingreso vinculado— contando la misma visita solo si la secuencia se observó en ese orden, para ver la conversión sin mezclar visitas distintas y sin cambiar las métricas que ya defendimos.

**Why this priority**: Es el entregable de negocio de la Feature #7. Usa los hechos de la historia anterior y las entradas que el análisis ya cerró.

**Independent Test**: Sobre un caso con las cinco etapas calculadas a mano, los conteos y las tasas coinciden. Una visita que entró al local sin una atención estimada previa no aparece en la última etapa. Calcular de nuevo no cambia ningún número y las ocho métricas de la sesión siguen iguales.

**Acceptance Scenarios**:

1. **Given** un análisis completado y un local con zona frontal, **When** se arma el funnel, **Then** el paso observado cuenta las visitas vinculadas distintas cuyo pie estuvo en la zona frontal, incluidas las que después entraron al local. Ese conteo no reemplaza la métrica ya existente de paso frente al local, que sigue excluyendo a quienes entraron.
2. **Given** esas visitas de paso observado, **When** se cuentan las etapas siguientes, **Then** la exposición, la detención y la atención estimada son subconjuntos anidados de ese paso, siempre de la misma visita, y cada visita cuenta a lo sumo una vez por etapa.
3. **Given** una detención frente a la vidriera que dura al menos 8 segundos de video, **When** se evalúa la atención, **Then** esa visita cuenta como atención estimada. El rótulo dice que es una estimación: no afirma que la persona haya mirado la vidriera, no observa el rostro y no la identifica.
4. **Given** una detención de al menos 3 segundos y de menos de 8 segundos de video, **When** se evalúa la atención, **Then** la visita cuenta como detención y no como atención estimada.
5. **Given** la misma visita tiene una entrada ya cerrada por el análisis y el instante de esa entrada es posterior al inicio de su atención estimada, **When** se evalúa el ingreso del funnel, **Then** cuenta como ingreso vinculado. Una entrada de esa visita anterior a la atención no cuenta en esta etapa.
6. **Given** una visita que entró al local sin exposición, sin detención o sin atención estimada, **When** se lee el funnel, **Then** esa entrada no sube el ingreso vinculado. El conteo de entradas ya cerrado por el análisis permanece igual y puede ser mayor que el ingreso vinculado.
7. **Given** el paso observado es cero, o una etapa anterior es cero, **When** se pide la tasa hacia la etapa siguiente, **Then** la tasa figura como no disponible y se nombra por esas dos etapas. La tasa de ingreso ya existente no cambia de nombre ni de valor.
8. **Given** los mismos hechos, **When** el funnel se calcula otra vez, **Then** los cinco conteos y las tasas disponibles son los mismos. Las ocho métricas ya existentes de la sesión no cambian.
9. **Given** una visita cuyo pie estuvo en la vidriera y nunca en la zona frontal de ese local, **When** se arma el funnel, **Then** esa visita no entra en la exposición del funnel y queda visible como excluida, con el motivo de que no hubo paso observado.

---

### User Story 3 - Leer el funnel en el resultado de la sesión (Priority: P2)

Como analista, quiero ver el funnel de cada local junto al resultado de una sesión de video ya terminada, con los umbrales, el rótulo de estimación y el motivo de lo que no se pudo calcular, para interpretarlo sin volver a mirar el video.

**Why this priority**: Las dos historias anteriores ya producen el número. Esta lo pone a la vista. El chat ampliado, las comparaciones y las demás señales de la entrega final no dependen de esta pantalla para que el funnel exista.

**Independent Test**: Abrir el resultado de una sesión de video completada muestra las cinco etapas, las tasas disponibles, los umbrales de 3 y 8 segundos y el rótulo de estimación. Elegir un tramo del video no cambia esas etapas ni esas tasas. Otra sesión no muestra esos datos. Una sesión de cámara en vivo no muestra este funnel.

**Acceptance Scenarios**:

1. **Given** una sesión de video completada y un local de su escena, **When** el analista abre el resultado, **Then** ve el paso observado, la exposición, la detención, la atención estimada y el ingreso vinculado, las tasas que se pudieron calcular con el nombre de las dos etapas que comparan, y la aclaración de que la atención es una estimación y de que el ingreso vinculado no es el total de entradas ni una compra. La tasa de ingreso ya existente sigue visible con su nombre y su valor.
2. **Given** ese resultado, **When** se lee la detención y la atención, **Then** se ven los umbrales usados: al menos 3 segundos de video para la detención y al menos 8 segundos de video para la atención estimada.
3. **Given** un local sin zona de vidriera, **When** se abre el resultado, **Then** la exposición, la detención, la atención y el ingreso vinculado figuran como no disponibles, con el motivo de que no hay zona de vidriera. El paso observado y las entradas ya cerradas siguen visibles si existen.
4. **Given** visitas solo en la vidriera, sin paso por el frente, **When** se abre el resultado, **Then** se muestra cuántas quedaron fuera del funnel y por qué.
5. **Given** dos sesiones de video, **When** se abre una, **Then** no aparecen etapas ni tasas de la otra.
6. **Given** una sesión de cámara en vivo, **When** se abre su resultado, **Then** este funnel no se muestra y no se reemplaza con el de una sesión de video.
7. **Given** el chat mínimo del resultado, **When** se pregunta por exposición, detención, atención o por este funnel, **Then** no responde con estas cifras. Esas preguntas quedan para el chat ampliado.
8. **Given** el funnel ya visible de un local, **When** el analista elige un tramo del video, **Then** las cinco etapas y sus tasas siguen siendo las de toda la sesión. El tramo no las recalcula ni las pone en cero. La lista de hechos sí queda limitada a ese tramo.

---

### User Story 4 - Contrastar el funnel con una observación manual (Priority: P2)

Como equipo, quiero comparar en al menos un clip del material elegido las cinco etapas contra una observación hecha a mano, para poder mostrar el funnel sin prometer que la estimación es exacta.

**Why this priority**: La precisión de la exposición, la detención y la atención no se compromete antes de ese contraste. Las historias anteriores ya pueden mostrar el número como estimación.

**Independent Test**: Sobre un clip del material elegido, con las cinco etapas anotadas a mano, queda un informe de diferencias clasificadas. El recorrido de prueba sin ese clip sigue pudiendo dar por válidas las otras historias.

**Acceptance Scenarios**:

1. **Given** un clip del material elegido y una observación manual de paso observado, exposición, detención, atención estimada e ingreso vinculado, **When** se contrasta con el funnel de esa sesión, **Then** queda registrada cada diferencia y su clasificación.
2. **Given** ese contraste, **When** se lee el informe, **Then** no afirma que el funnel sea exacto: describe en qué coincidió y en qué no.
3. **Given** un resultado de sesión mostrado antes de que exista ese contraste, **When** el analista lo lee, **Then** ve que la precisión de estas etapas todavía no está comprometida.
4. **Given** el recorrido habitual de pruebas del equipo, **When** se ejecuta sin el clip real ni la observación manual, **Then** las otras historias siguen pudiendo darse por válidas.

---

### Edge Cases

- El análisis no está completado (sigue en curso, falló o fue cancelado): el funnel no se presenta como resultado completo de la sesión.
- El seguimiento se pierde dentro de la vidriera: no hay detención, no hay atención estimada y no se inventa la duración que falta. Una visita nueva no continúa la anterior.
- El video termina con la visita todavía dentro de la vidriera: no se confirma la detención de ese tramo.
- La visita oscila en el borde de la vidriera: el funnel la cuenta una sola vez en la exposición. Las entradas de zona ya registradas siguen ahí y no se reescriben.
- La estadía en la vidriera dura menos de 3 segundos de video: hay exposición y no hay detención ni atención.
- La detención dura entre 3 y menos de 8 segundos de video: hay detención y no hay atención estimada.
- La visita entra al local antes de iniciar una atención estimada, o entra sin haber pasado por las etapas previas: no suma ingreso vinculado. Las entradas ya cerradas no se modifican.
- El local no tiene zona de vidriera: exposición, detención, atención e ingreso vinculado quedan no disponibles, con el motivo de que no hay zona de vidriera. No se dibuja una vidriera implícita. El paso observado y las entradas ya cerradas siguen si existen.
- El pie está en la vidriera y nunca en la zona frontal: la visita queda fuera del funnel y el resultado lo dice. No se suma a la exposición de la etapa.
- Dos locales tienen vidrieras superpuestas: cada local cuenta la visita en su propia vidriera. El funnel es por local y no convierte eso en una persona única.
- La misma visita entra y sale de la vidriera más de una vez: en el funnel cuenta una sola vez por etapa si alguna de esas estadías cumple el umbral.
- No hay visitas, o la etapa anterior es cero: el conteo de una etapa vacía es cero y la tasa hacia la siguiente es no disponible.
- La sesión es de cámara en vivo: este funnel no se calcula ni se muestra.
- Dos sesiones se consultan a la vez: ninguna ve etapas de la otra.
- La zona interior no sustituye a la vidriera: estar adentro no es exposición, detención ni atención hacia la vidriera.
- El analista elige un tramo del video: las cinco etapas y sus tasas siguen siendo las de toda la sesión. El tramo filtra la lista de hechos y no recalcula el funnel.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A partir de un análisis completado de una sesión de video, el sistema MUST generar hechos de detención frente a la vidriera para cada local que tenga zona de vidriera. MUST NOT generar un segundo hecho de exposición: la exposición del funnel es la entrada a la zona de vidriera que ya quedó registrada.
- **FR-002**: Cada detención MUST pertenecer a una sola sesión, una sola cámara y un solo análisis, y MUST guardar el instante del video en que ocurrió. Los tiempos MUST calcularse con el video, nunca con la duración del procesamiento.
- **FR-003**: La etapa de exposición MUST leer las entradas ya registradas a la zona de vidriera y MUST NOT registrar un hecho paralelo por el mismo ingreso. Esas entradas MUST NOT generar permanencia observable ni ocupación. Esas dos medidas MUST seguir limitadas a la zona frontal, como ya están definidas. La etapa puede ser menor que la cantidad de entradas de zona, porque solo cuenta visitas con paso observado y a cada visita una sola vez.
- **FR-004**: Una detención frente a la vidriera MUST contar solo cuando la misma visita permanece dentro de la zona de vidriera al menos 3 segundos de video y después la deja sin perderse el seguimiento. Una estadía más corta MUST dejar la entrada de zona ya registrada y MUST NOT contar como detención. Si el video termina con la visita todavía adentro, o si el seguimiento se pierde adentro, el sistema MUST NOT confirmar esa detención ni inventar la duración. Una visita vinculada nueva MUST NOT heredar hechos de la anterior.
- **FR-005**: Aunque el pie oscile en el borde y queden varias entradas de zona, el funnel MUST contar a lo sumo una exposición de esa visita. Esta feature MUST NOT borrar ni reescribir esas entradas de zona y MUST NOT cambiar la ventana de oscilación de la línea de entrada.
- **FR-006**: El paso observado de un local MUST contar las visitas vinculadas distintas cuyo pie estuvo en la zona frontal, incluidas las que después tuvieron una entrada al local. MUST mostrarse con un nombre que lo distinga de la métrica ya existente de paso frente al local. Esa métrica existente MUST conservar su definición y MUST NOT absorber a quienes entraron.
- **FR-007**: En el funnel, la exposición, la detención y la atención estimada MUST ser subconjuntos anidados del paso observado de la misma visita. Cada visita MUST contar a lo sumo una vez por etapa, aunque haya repetido la zona. Una visita que estuvo en la vidriera y nunca en la zona frontal MUST quedar fuera del funnel y MUST mostrarse como excluida, con el motivo reconocible.
- **FR-008**: La atención estimada MUST contar solo cuando la detención de esa visita dura al menos 8 segundos de video. MUST rotularse como estimación. MUST NOT afirmar que la persona miró la vidriera, MUST NOT observar el rostro y MUST NOT tratar la visita como una identidad real.
- **FR-009**: El ingreso vinculado MUST contar solo cuando la misma visita tiene una entrada ya cerrada por el análisis y el instante de video de esa entrada es posterior al inicio de su atención estimada. Las entradas ya cerradas MUST NOT modificarse. El resultado MUST mostrar el ingreso vinculado y el total de entradas ya cerrado como cifras distintas cuando no coincidan.
- **FR-010**: La tasa entre dos etapas seguidas MUST ser el conteo de la etapa posterior dividido por el de la anterior y MUST nombrarse por esas dos etapas: paso observado a exposición, exposición a detención, detención a atención estimada, y atención estimada a ingreso vinculado. MUST NOT usar el nombre tasa de ingreso. Si la anterior es cero, o si no hay detenciones cerradas al pedir atención, la tasa MUST mostrarse como no disponible.
- **FR-011**: Calcular el funnel otra vez con los mismos hechos MUST devolver los mismos conteos y las mismas tasas. Las ocho métricas ya existentes de la sesión, incluida la tasa de ingreso, MUST permanecer iguales en nombre y en valor. La consulta que ya entrega esas ocho métricas MUST NOT incluir las etapas ni las tasas de este funnel.
- **FR-012**: Un análisis que no está completado MUST NOT presentarse como funnel completo. Las consultas MUST aislar los datos entre sesiones. Una sesión de cámara en vivo MUST NOT calcular ni mostrar este funnel.
- **FR-013**: Si a un local le falta la zona de vidriera, la exposición, la detención, la atención estimada y el ingreso vinculado MUST quedar no disponibles, con el motivo de que no hay zona de vidriera. El sistema MUST NOT inventar la vidriera. El paso observado y las entradas ya cerradas MUST seguir disponibles si existen.
- **FR-014**: El resultado de una sesión de video completada MUST mostrar, por local, las cinco etapas, las tasas disponibles con el nombre de sus dos etapas, los umbrales de 3 y de 8 segundos de video, el rótulo de estimación y la aclaración de que el ingreso vinculado no es una compra ni el total de entradas. La tasa de ingreso ya existente MUST seguir viéndose con su nombre y su valor. Esas etapas y esas tasas MUST ser las de toda la sesión. Elegir un tramo del video MUST NOT cambiarlas ni recalcularlas. Ese tramo MUST seguir limitando solo la lista de hechos. Mientras no exista el contraste manual de esta feature, el resultado MUST decir que la precisión de estas etapas no está comprometida. El chat mínimo MUST NOT responder con estas cifras.
- **FR-015**: El equipo MUST contrastar, en al menos un clip del material elegido, el paso observado, la exposición, la detención, la atención estimada y el ingreso vinculado contra una observación manual, y MUST dejar escritas las diferencias y su clasificación. Ese contraste MUST NOT afirmar exactitud y MUST NOT ser requisito para dar por válidas las otras historias en el recorrido de prueba.

### Key Entities

- **Visita vinculada**: Recorrido de un identificador temporal dentro de una sesión y una cámara. No es una persona única ni se continúa con otro identificador.
- **Hecho de vidriera**: Detención frente a la vidriera de una visita vinculada en un local. Pertenece a una sesión, una cámara y un análisis, y tiene instante de video. La exposición no es un hecho nuevo: es la entrada de zona de vidriera ya registrada.
- **Etapa del funnel**: Paso observado, exposición, detención, atención estimada o ingreso vinculado de un local en toda una sesión completada. Cada etapa cuenta visitas vinculadas distintas. Un tramo del video no la recorta.
- **Tasa entre etapas**: Conversión entre dos etapas seguidas del mismo local, nombrada por esas dos etapas. No es la tasa de ingreso. Si falta el denominador, queda no disponible.
- **Contraste manual del funnel**: Comparación, para un clip elegido, entre la observación a mano de las cinco etapas y el funnel de esa sesión, con las diferencias clasificadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el caso sintético de oscilación, el funnel cuenta una sola exposición de esa visita aunque queden varias entradas de zona, y esas entradas siguen presentes. En el caso de una visita que se pierde dentro de la vidriera, y en el caso de un video que termina con la visita adentro, no hay detención ni atención inventadas.
- **SC-002**: En un caso con las cinco etapas calculadas a mano, los conteos y las tasas coinciden con ese resultado, incluida una entrada sin atención previa que no suma ingreso vinculado. Calcular de nuevo no cambia ningún número.
- **SC-003**: En el 100 % de las sesiones del caso de prueba, las ocho métricas ya existentes quedan iguales después de armar el funnel, la tasa de ingreso conserva su nombre y su valor, y el total de entradas ya cerrado no se reemplaza por el ingreso vinculado. Ninguna tasa del funnel se llama tasa de ingreso.
- **SC-004**: En el 100 % de los locales sin zona de vidriera, la exposición, la detención, la atención y el ingreso vinculado se muestran como no disponibles con el motivo de que no hay zona de vidriera. En el 100 % de las tasas sin etapa anterior, el valor se muestra como no disponible.
- **SC-005**: En una sesión completada, la atención estimada es menor o igual que la detención, la detención es menor o igual que la exposición y la exposición es menor o igual que el paso observado. El ingreso vinculado es menor o igual que la atención estimada y menor o igual que las entradas ya cerradas. El 100 % de esas cifras pertenecen a la sesión pedida.
- **SC-006**: Un analista reconoce, en el resultado de una sesión de video completada y sin volver a abrir el video, las cinco etapas, los dos umbrales, el rótulo de estimación y si la precisión sigue sin comprometer. Al elegir un tramo, el 100 % de esas etapas y de sus tasas permanece igual al de toda la sesión. En una sesión de cámara en vivo, este funnel no aparece.
- **SC-007**: En al menos un clip del material elegido, el informe de contraste incluye la observación manual y el funnel de las cinco etapas, y clasifica cada diferencia sin declarar exactitud. El recorrido de prueba sin ese clip sigue pudiendo validar las otras historias.

## Assumptions

- La sesión de video, la escena y un análisis completado ya existen. El local ya puede tener zona frontal, zona interior, zona de vidriera y una línea de entrada con sentido. Esta feature no vuelve a definir la carga, el editor ni el seguimiento.
- El funnel se calcula solo para sesiones de video ya analizadas y siempre sobre toda la sesión. Elegir un tramo del video no lo recalcula: ese tramo solo filtra la lista de hechos. La cámara en vivo queda fuera: su resultado no incluye estas etapas.
- Una visita vinculada es un identificador temporal de esa sesión y esa cámara. No es una persona única, no se reconoce el rostro y no se sigue entre cámaras.
- El paso observado incluye a quienes después entraron. La métrica ya existente de paso frente al local no cambia: sigue siendo quien estuvo en el frente y no entró. Por eso el funnel no usa esa métrica como primera etapa.
- La exposición del funnel es la entrada de zona de vidriera ya registrada. No se guarda un segundo hecho por el mismo ingreso. La etapa exige además que la misma visita haya estado en la zona frontal. Quien solo pisa la vidriera, sin paso observado, se muestra aparte y no infla la etapa.
- La detención son al menos 3 segundos de video dentro de la vidriera, cerrados porque la misma visita la dejó. La atención estimada son al menos 8 segundos de esa detención. Esos umbrales se muestran junto al número. No observan la mirada: una parada más larga se toma como estimación de atención, no como prueba de que miró la vidriera.
- La permanencia observable y la ocupación visible no cambian. La zona interior y la vidriera siguen sin generarlas.
- Las entradas, las salidas y la ocupación visible siguen siendo las que el análisis completado ya cerró. El ingreso vinculado es un subconjunto posterior a la atención estimada, no un recálculo de las entradas.
- La ventana de oscilación sigue aplicando solo a la línea de entrada. Si el pie vaivenea en el borde de la vidriera, el funnel cuenta una sola exposición y no reescribe las entradas de zona ya registradas.
- Las ocho métricas ya existentes, el chat mínimo, el mapa de calor y el historial de video conservan su comportamiento. La tasa de ingreso no cambia de nombre ni de valor. Cada tasa del funnel se nombra por el par de etapas que compara. El chat mínimo no consulta estas etapas ni estas tasas, y la consulta de las ocho métricas no las incluye.
- Los grupos, la posible compra, las comparaciones entre sesiones y el chat ampliado quedan fuera. El chat ampliado, cuando exista, tendrá que leer estas cifras y no calcularlas desde el video.
- El contraste manual usa un clip del material elegido y no promete coincidencia con la mano. Hasta ese informe, la pantalla dice que la precisión no está comprometida.
- Los tiempos son tiempos del video. Una división sin denominador se muestra como no disponible.
