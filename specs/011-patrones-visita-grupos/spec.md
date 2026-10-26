# Feature Specification: Patrones de visita y grupos estimados

**Feature Branch**: `feature/011-patrones-visita-grupos`

**Azure Boards**: Feature #8, hija del Epic #3 `Evolución final para el 6 de noviembre de 2026`.

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "bueno vamos con esa" sobre la Feature #8: analizar secuencias y transiciones entre zonas o locales dentro de una misma cámara, y estimar grupos por proximidad, dirección y duración, sin interpretarlos como parentesco ni relaciones reales. Queda condicionada a una escena válida de esa cámara y a umbrales verificables.

## Clarifications

### Session 2026-10-24

- Q: Si el pie de una visita queda dentro de dos áreas configuradas al mismo tiempo, ¿cuándo se cuenta el paso de una a la otra? → A: Mientras el pie está en las dos, no hay transición. El paso se cuenta cuando sale de una y, en no más de 1 segundo de video y sin perder el seguimiento, queda en la otra.
- Q: ¿Los patrones de recorrido y los grupos de 2 segundos se cierran durante el análisis, con las observaciones que ya cierran los hechos de la escena, o se calculan después con la muestra de posiciones del mapa de calor? → A: Se cierran durante el análisis, con las mismas observaciones de los hechos de la escena. Se guarda el resultado. La muestra del mapa de calor no se usa como fuente.

### Session 2026-10-26

- Q: Si una visita cumple a la vez las condiciones de dos grupos que empezaron juntos y tienen la misma cantidad de integrantes, y además comparten el identificador más chico, ¿en cuál queda? → A: Queda en el conjunto que, al ordenar sus identificadores, es menor en la primera posición que difiere.
- Q: Si a un grupo le falta una visita durante un instante y esa visita reaparece, ¿el grupo sigue siendo el mismo? → A: Un hueco de hasta 1 segundo de video conserva el grupo y no inventa posiciones. Más de 1 segundo lo cierra.
- Q: Si el analista elige otro local en el resultado de la misma sesión, ¿los patrones y los grupos siguen siendo los de toda la sesión? → A: Siguen siendo los de toda la sesión. Elegir otro local no los recorta ni los vuelve a pedir.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver cómo se recorre la escena (Priority: P1)

Como analista, quiero ver en qué orden las visitas vinculadas pasaron por las áreas configuradas y entre qué locales cambiaron, dentro de una misma cámara, para reconocer recorridos repetidos sin tratar dos visitas distintas como la misma persona.

**Why this priority**: Es la primera mitad de la Feature #8 y se puede leer aunque todavía no existan grupos. No cambia el tráfico, las entradas ni el funnel que ya están cerrados.

**Independent Test**: Con las observaciones de un análisis de video y una escena con al menos dos áreas, un caso sintético comprueba un recorrido A luego B, una repetición de la misma área, una pérdida de seguimiento entre dos áreas y una pausa de más de un segundo de video. Cada visita cuenta una sola vez en cada transición. La muestra del mapa de calor no entra en ese cálculo. No hace falta la pantalla ni un video real.

**Acceptance Scenarios**:

1. **Given** un análisis completado de una sesión de video y la escena guardada de esa cámara, **When** se leen los patrones, **Then** cada transición y cada secuencia pertenecen solo a esa sesión, esa cámara y ese análisis, y usan instantes del video. Una visita vinculada no se continúa en otra cámara ni con otro identificador.
2. **Given** la misma visita entra en un área configurada y después entra en otra, sin perderse y sin que pasen más de 1 segundo de video entre salir de la primera y entrar en la segunda, **When** se arma el patrón, **Then** queda la transición de la primera área a la segunda y la secuencia en ese orden.
3. **Given** la misma visita vuelve a entrar en el área en la que ya estaba, sin haber pasado por otra, **When** se arma la secuencia, **Then** esa área no se repite seguida. La transición no aumenta por el vaivén en el mismo borde.
4. **Given** la misma visita repite más tarde la misma transición entre dos áreas, **When** se cuenta el patrón, **Then** esa visita suma una sola vez a esa transición y una sola vez a esa secuencia.
5. **Given** el seguimiento se pierde, o pasan más de 1 segundo de video fuera de las áreas, **When** la visita vuelve a aparecer, **Then** la secuencia anterior queda cerrada. Lo que sigue es otra secuencia. Una visita nueva no hereda la anterior.
6. **Given** dos áreas seguidas pertenecen a locales distintos, **When** se lee el patrón de locales, **Then** queda la transición de un local al otro. Dos áreas seguidas del mismo local no cuentan como cambio de local.
7. **Given** la escena de ese análisis no tiene áreas configuradas, **When** se piden los patrones, **Then** quedan no disponibles, con el motivo de que no hay áreas, y no se inventa un recorrido.
8. **Given** los mismos recorridos, **When** los patrones se calculan otra vez, **Then** las transiciones y las secuencias son las mismas. Las ocho métricas ya existentes, la tasa de ingreso y el funnel comercial no cambian.
9. **Given** el pie de la misma visita queda dentro de dos áreas configuradas a la vez, **When** se arma el patrón, **Then** esa presencia no es una transición ni adelanta la secuencia. El paso de la primera a la segunda queda cuando sale de una y, en no más de 1 segundo de video y sin perderse el seguimiento, queda en la otra.

---

### User Story 2 - Estimar quiénes iban juntos (Priority: P1)

Como analista, quiero una estimación de grupos de visitas que se mantuvieron cerca, con una dirección de movimiento parecida y durante un tiempo mínimo de video, para ver compañía observable sin afirmar parentesco ni una relación real.

**Why this priority**: Es la otra mitad de la Feature #8. Se puede comprobar con posiciones de un caso sintético aunque los patrones de áreas no se muestren.

**Independent Test**: En un caso con las posiciones observadas durante el análisis, dos visitas que cumplen cercanía, dirección y 2 segundos de video forman un grupo estimado. Una visita quieta, una tercera que queda lejos y un acercamiento de menos de 2 segundos no entran. La muestra del mapa de calor no entra en ese cálculo. El rótulo dice que es una estimación.

**Acceptance Scenarios**:

1. **Given** un análisis completado con la escena guardada de esa cámara, **When** dos visitas vinculadas mantienen los pies a no más de ocho centésimas del ancho del encuadre, con direcciones de movimiento que no se apartan más de 45 grados, durante al menos 2 segundos de video, **Then** forman un grupo estimado. El rótulo dice que es una estimación: no afirma parentesco, amistad ni ninguna relación real, y no identifica a las personas.
2. **Given** esas dos visitas se separan más de ese umbral, se apartan más de 45 grados o una falta más de 1 segundo de video antes de los 2 segundos, **When** se evalúa el grupo, **Then** no se confirma ese grupo ni se alarga el tiempo que falta. Un hueco de hasta 1 segundo conserva el grupo y no inventa las posiciones de ese hueco. Más de 1 segundo lo cierra.
3. **Given** el video termina y esas visitas ya llevaban juntos al menos 2 segundos de video, **When** se cierran los grupos, **Then** el grupo se conserva hasta el último instante observado. Si todavía no llegaban a 2 segundos, no se confirma.
4. **Given** una visita casi no se mueve y no hay una dirección de movimiento, **When** se evalúa si acompaña a otra, **Then** no entra en un grupo. La cercanía sola no alcanza.
5. **Given** tres visitas y solo dos se mantienen dentro del umbral entre sí, **When** se arma el grupo, **Then** el grupo estimado tiene esas dos. La tercera no se suma por estar cerca de una sola si queda lejos de la otra.
6. **Given** una visita cumpliría a la vez las condiciones de dos grupos, **When** se asignan los integrantes, **Then** queda en un solo grupo: el que empezó antes y, si empezaron juntos, el de más integrantes. Si también empatan en tamaño y comparten el identificador más chico, queda en el conjunto que, al ordenar sus identificadores, es menor en la primera posición que difiere. No se cuenta dos veces en el mismo instante.
7. **Given** un grupo se desarma y los que quedan vuelven a cumplir los tres umbrales durante otros 2 segundos de video, **When** se cierra ese tramo, **Then** es otro grupo estimado. No se pega al anterior.
8. **Given** los mismos recorridos, **When** los grupos se calculan otra vez, **Then** la cantidad de grupos y sus integrantes son los mismos. Las métricas, la tasa de ingreso y el funnel comercial no cambian.

---

### User Story 3 - Leer patrones y grupos en el resultado (Priority: P2)

Como analista, quiero ver los patrones de áreas, los cambios de local y los grupos estimados en el resultado de una sesión de video ya terminada, con los umbrales y el motivo de lo que no se pudo calcular, para interpretarlos sin volver a mirar el video.

**Why this priority**: Las dos historias anteriores ya producen el dato. Esta lo pone a la vista. Las comparaciones entre sesiones y el chat ampliado no dependen de esta pantalla para que el dato exista.

**Independent Test**: Abrir el resultado de una sesión de video completada muestra las transiciones, las secuencias, los grupos estimados, los umbrales de cercanía, dirección y 2 segundos, y el rótulo de estimación. Elegir un tramo del video o otro local de la misma sesión no cambia esas cifras. Una sesión de cámara en vivo no las muestra.

**Acceptance Scenarios**:

1. **Given** una sesión de video completada, **When** el analista abre el resultado, **Then** ve las transiciones entre áreas, las secuencias, los cambios de local y los grupos estimados de toda la sesión, con el umbral de ocho centésimas del ancho del encuadre, el de 45 grados y el de 2 segundos de video. Junto a los grupos se lee que son una estimación y que no afirman una relación real.
2. **Given** la escena no tiene áreas, **When** se abre el resultado, **Then** los patrones de áreas y de locales figuran como no disponibles, con el motivo de que no hay áreas. Los grupos estimados siguen visibles si la escena de ese análisis existe.
3. **Given** no hubo ningún grupo que cumpliera los tres umbrales, **When** se abre el resultado, **Then** la cantidad de grupos estimados es cero y no se muestra como no disponible.
4. **Given** dos sesiones de video, **When** se abre una, **Then** no aparecen patrones ni grupos de la otra.
5. **Given** una sesión de cámara en vivo, **When** se abre su resultado, **Then** estos patrones y estos grupos no se muestran y no se reemplazan con los de una sesión de video.
6. **Given** el chat mínimo del resultado, **When** se pregunta por recorridos, transiciones o grupos, **Then** no responde con estas cifras. Esas preguntas quedan para el chat ampliado.
7. **Given** los patrones y los grupos ya visibles, **When** el analista elige un tramo del video, **Then** siguen siendo los de toda la sesión. El tramo no los recalcula ni los pone en cero. La lista de hechos sí queda limitada a ese tramo.
8. **Given** los patrones y los grupos ya visibles, **When** el analista elige otro local de la misma sesión, **Then** siguen siendo los de toda la sesión. Ese cambio no los recorta ni los vuelve a pedir.
9. **Given** todavía no existe el contraste manual de esta feature, **When** el analista lee el resultado, **Then** ve que la precisión de los patrones y de los grupos estimados no está comprometida.

---

### User Story 4 - Contrastar con una observación manual (Priority: P2)

Como equipo, quiero comparar en al menos un clip del material elegido los patrones de recorrido y los grupos estimados contra una observación hecha a mano, para poder mostrarlos sin prometer que la estimación es exacta.

**Why this priority**: La precisión no se compromete antes de ese contraste. Las historias anteriores ya pueden mostrar el número como estimación.

**Independent Test**: Sobre un clip del material elegido, con transiciones y grupos anotados a mano, queda un informe de diferencias clasificadas. El recorrido de prueba sin ese clip sigue pudiendo dar por válidas las otras historias.

**Acceptance Scenarios**:

1. **Given** un clip del material elegido y una observación manual de transiciones entre áreas, cambios de local y grupos estimados, **When** se contrasta con el resultado de esa sesión, **Then** queda registrada cada diferencia y su clasificación.
2. **Given** ese contraste, **When** se lee el informe, **Then** no afirma que los patrones ni los grupos sean exactos: describe en qué coincidió y en qué no.
3. **Given** un resultado de sesión mostrado antes de que exista ese contraste, **When** el analista lo lee, **Then** ve que la precisión de estos datos todavía no está comprometida.
4. **Given** el recorrido habitual de pruebas del equipo, **When** se ejecuta sin el clip real ni la observación manual, **Then** las otras historias siguen pudiendo darse por válidas.

---

### Edge Cases

- El análisis no está completado (sigue en curso, falló o fue cancelado): los patrones y los grupos no se presentan como resultado completo de la sesión.
- El seguimiento se pierde entre dos áreas, o pasan más de 1 segundo de video fuera de ellas: la secuencia se corta. Una visita nueva no la continúa.
- El pie oscila en el borde de la misma área: esa área no se repite en la secuencia y la visita cuenta una sola vez la transición hacia la siguiente.
- El pie está dentro de dos áreas a la vez: eso no es una transición. El paso queda cuando sale de una y, en no más de 1 segundo de video y sin perderse el seguimiento, queda en la otra.
- La misma visita repite más tarde la misma transición: en el conteo del patrón suma una sola vez.
- Dos áreas seguidas son del mismo local: hay transición de áreas y no hay cambio de local.
- La escena no tiene áreas: los patrones quedan no disponibles, con el motivo de que no hay áreas. No se inventa un recorrido. Los grupos estimados siguen si la escena de ese análisis existe.
- Dos visitas se acercan menos de 2 segundos de video, una está quieta, o una tercera queda lejos de alguno de los otros: no forman el grupo que no cumple los tres umbrales.
- A un grupo le falta una visita 1 segundo de video o menos y reaparece: el grupo sigue y no se inventan posiciones en ese hueco. Si falta más de 1 segundo, el grupo se cierra.
- El video termina cuando ya llevaban juntos al menos 2 segundos: el grupo se conserva hasta el último instante observado. Si no llegaban a 2 segundos, no se confirma.
- Una visita encajaría en dos grupos al mismo tiempo: queda en uno solo, el que empezó antes; si empezaron juntos, en el de más integrantes; si también empatan ahí y comparten el identificador más chico, en el conjunto que al ordenar sus identificadores es menor en la primera posición que difiere. No se cuenta dos veces en ese instante.
- Un grupo se desarma y los que quedan vuelven a cumplir los umbrales otros 2 segundos: es otro grupo, no una continuación del anterior.
- No hubo grupos: la cantidad es cero y está disponible.
- La sesión es de cámara en vivo: estos patrones y estos grupos no se calculan ni se muestran.
- Dos sesiones se consultan a la vez: ninguna ve patrones ni grupos de la otra.
- El analista elige un tramo del video: los patrones y los grupos siguen siendo los de toda la sesión. El tramo filtra la lista de hechos y no los recalcula.
- El analista elige otro local de la misma sesión: los patrones y los grupos siguen siendo los de toda la sesión. Ese cambio no los recorta ni los vuelve a pedir.
- Estar juntos no es una compra, no es parentesco y no identifica a nadie.
- La muestra de posiciones del mapa de calor no arma ni corrige estos patrones ni estos grupos. Si esa muestra cambia o falta, el resultado cerrado durante el análisis sigue igual.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Durante el análisis de una sesión de video, el sistema MUST cerrar los patrones de recorrido y los grupos estimados de esa sesión y esa cámara con las mismas observaciones que ya cierran los hechos de la escena, y MUST guardar solo ese resultado. MUST usar las áreas de la escena con la que se analizó y los instantes del video, nunca la duración del procesamiento. MUST NOT calcularlos después desde la muestra de posiciones del mapa de calor, ni guardar por esto un registro permanente de cada visita en cada instante. Cada patrón y cada grupo MUST pertenecer a una sola sesión, una sola cámara y un solo análisis.
- **FR-002**: Una transición entre dos áreas MUST contar cuando la misma visita vinculada sale de la primera y, sin perderse el seguimiento y en no más de 1 segundo de video, queda en la segunda. Si el pie está dentro de las dos a la vez, esa presencia MUST NOT contar como transición ni adelantar la secuencia. Una secuencia MUST ser esa cadena de áreas en el orden observado. Volver a entrar en la misma área sin pasar por otra MUST NOT repetirla en la secuencia.
- **FR-003**: Cada visita MUST contar a lo sumo una vez en cada transición ordenada y a lo sumo una vez en cada secuencia, aunque repita el recorrido. Si el seguimiento se pierde, o si pasan más de 1 segundo de video fuera de las áreas, la secuencia MUST cerrarse. Una visita vinculada nueva MUST NOT heredar la secuencia anterior ni unirse con otro identificador. MUST NOT seguirse una visita entre cámaras.
- **FR-004**: Si dos áreas seguidas pertenecen a locales distintos, el sistema MUST contar además la transición de local. Dos áreas seguidas del mismo local MUST NOT contar como cambio de local. El patrón de locales MUST ser el de toda la sesión.
- **FR-005**: Si la escena de ese análisis no tiene áreas configuradas, los patrones de áreas y de locales MUST quedar no disponibles, con el motivo de que no hay áreas. El sistema MUST NOT inventar áreas ni recorridos.
- **FR-006**: El sistema MUST estimar grupos de al menos dos visitas vinculadas de la misma sesión y la misma cámara. Un grupo MUST confirmarse solo cuando, durante al menos 2 segundos de video, todos los pares se mantienen a no más de ocho centésimas del ancho del encuadre y las direcciones de movimiento no se apartan más de 45 grados. MUST rotularse como estimación. MUST NOT afirmar parentesco, amistad ni ninguna relación real, y MUST NOT identificar a las personas.
- **FR-007**: Si se separan más del umbral, si la dirección se aparta más de 45 grados, si una visita no tiene dirección porque casi no se mueve, o si una visita falta más de 1 segundo de video antes de los 2 segundos, el sistema MUST NOT confirmar ese grupo ni inventar el tiempo que falta. Un hueco de hasta 1 segundo MUST conservar el grupo y MUST NOT inventar posiciones. Si el video termina y ya cumplían los 2 segundos, el grupo MUST conservarse hasta el último instante observado. Si no los cumplían, MUST NOT confirmarse.
- **FR-008**: Una visita MUST pertenecer a lo sumo a un grupo en el mismo instante. Si cumpliría dos, MUST quedar en el que empezó antes y, si empezaron juntos, en el de más integrantes. Si también empatan en tamaño y comparten el identificador más chico, MUST quedar en el conjunto que, al ordenar sus identificadores, es menor en la primera posición que difiere. Un integrante que queda lejos de alguno de los otros MUST NOT sumarse. Si un grupo se cierra y los que quedan vuelven a cumplir los tres umbrales durante otros 2 segundos de video, MUST contarse como otro grupo.
- **FR-009**: Calcular otra vez con los mismos recorridos MUST devolver las mismas transiciones, las mismas secuencias y los mismos grupos. Las ocho métricas ya existentes, la tasa de ingreso y el funnel comercial MUST permanecer iguales en nombre y en valor. La consulta que ya entrega esas ocho métricas MUST NOT incluir estos patrones ni estos grupos.
- **FR-010**: Un análisis que no está completado MUST NOT presentarse como patrones o grupos completos. Las consultas MUST aislar los datos entre sesiones. Una sesión de cámara en vivo MUST NOT calcular ni mostrar estos patrones ni estos grupos.
- **FR-011**: El resultado de una sesión de video completada MUST mostrar las transiciones entre áreas, las secuencias, los cambios de local y los grupos estimados de toda la sesión, junto con los tres umbrales y el rótulo de estimación. Si no hay áreas, los patrones MUST verse no disponibles con ese motivo y los grupos MUST seguir si la escena existe. Si no hubo grupos, la cantidad MUST ser cero y estar disponible. Elegir un tramo del video MUST NOT cambiar estas cifras ni recalcularlas. Ese tramo MUST seguir limitando solo la lista de hechos. Elegir otro local de la misma sesión MUST NOT recortar estas cifras ni volver a pedirlas. Mientras no exista el contraste manual de esta feature, el resultado MUST decir que la precisión no está comprometida. El chat mínimo MUST NOT responder con estas cifras.
- **FR-012**: El equipo MUST contrastar, en al menos un clip del material elegido, las transiciones entre áreas, los cambios de local y los grupos estimados contra una observación manual, y MUST dejar escritas las diferencias y su clasificación. Ese contraste MUST NOT afirmar exactitud y MUST NOT ser requisito para dar por válidas las otras historias en el recorrido de prueba.

### Key Entities

- **Visita vinculada**: Recorrido de un identificador temporal dentro de una sesión y una cámara. No es una persona única ni se continúa con otro identificador.
- **Transición de áreas**: Paso observado de una visita desde un área configurada hacia otra, en ese orden, dentro de la misma sesión y la misma cámara. Se cuenta al salir de la primera y quedar en la segunda dentro de 1 segundo de video. Estar en las dos a la vez no es el paso. Cada visita cuenta una sola vez por cada par ordenado.
- **Secuencia de visita**: Cadena ordenada de áreas de una visita mientras el seguimiento no se pierde y no hay una pausa de más de 1 segundo de video fuera de las áreas.
- **Transición de locales**: Cambio de local cuando dos áreas seguidas de esa secuencia pertenecen a locales distintos. No es una entrada oficial ni una compra.
- **Grupo estimado**: Conjunto de al menos dos visitas que, durante al menos 2 segundos de video, se mantuvieron cerca y con una dirección de movimiento parecida. Se cierra durante el análisis con esas observaciones y se guarda el resultado. No se reconstruye desde la muestra del mapa de calor. Es una estimación. No es parentesco ni una relación real.
- **Contraste manual de patrones y grupos**: Comparación, para un clip elegido, entre la observación a mano y el resultado de esa sesión, con las diferencias clasificadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el caso sintético, una visita que va de un área a otra cuenta una transición y una secuencia en ese orden. El vaivén en la misma área no repite el paso. Si el pie está en dos áreas a la vez, esa presencia no suma transición; el paso aparece cuando sale de una y queda en la otra dentro de 1 segundo de video. Si el seguimiento se pierde o pasan más de 1 segundo de video fuera de las áreas, la secuencia siguiente no se pega a la anterior. Repetir la misma transición no aumenta el conteo de esa visita.
- **SC-002**: En un caso con transiciones y secuencias calculadas a mano, los conteos coinciden, incluido un cambio de local solo cuando las dos áreas seguidas son de locales distintos. Calcular de nuevo con las mismas observaciones no cambia ningún número. Quitar o cambiar la muestra del mapa de calor tampoco lo cambia.
- **SC-003**: En un caso con posiciones conocidas, dos visitas que cumplen cercanía, 45 grados y 2 segundos de video forman un grupo estimado, y una tercera que queda lejos de una de ellas no entra. Una visita quieta y un acercamiento de menos de 2 segundos no forman grupo. El 100 % de esos grupos se lee como estimación y ninguno se describe como parentesco o relación real.
- **SC-004**: En el 100 % de las sesiones del caso de prueba, las ocho métricas ya existentes, la tasa de ingreso y el funnel comercial quedan iguales después de armar patrones y grupos. El 100 % de las consultas de esas ocho métricas sigue sin incluir estas cifras.
- **SC-005**: En el 100 % de las escenas sin áreas, los patrones se muestran como no disponibles con el motivo de que no hay áreas. En el 100 % de las sesiones sin grupos, la cantidad es cero y está disponible. El 100 % de esas cifras pertenecen a la sesión pedida.
- **SC-006**: Un analista reconoce, en el resultado de una sesión de video completada y sin volver a abrir el video, las transiciones, las secuencias, los grupos estimados, los tres umbrales y si la precisión sigue sin comprometer. Al elegir un tramo o otro local de la misma sesión, el 100 % de esas cifras permanece igual al de toda la sesión. En una sesión de cámara en vivo, estos datos no aparecen.
- **SC-007**: En al menos un clip del material elegido, el informe de contraste incluye la observación manual y el resultado de transiciones, cambios de local y grupos, y clasifica cada diferencia sin declarar exactitud. El recorrido de prueba sin ese clip sigue pudiendo validar las otras historias.

## Assumptions

- La sesión de video, la escena guardada de esa cámara y un análisis completado ya existen. Esta feature no vuelve a definir la carga, el editor ni el seguimiento, y no agrega un paso nuevo de calibración. La escena con la que se analizó la sesión es la referencia válida. Si esa escena no tiene áreas, los patrones quedan no disponibles y los grupos estimados siguen, porque usan la posición en el encuadre.
- Los patrones y los grupos se cierran durante el análisis de una sesión de video, con las mismas observaciones de los hechos de la escena, y se guarda solo el resultado. La muestra del mapa de calor no es la fuente y no se conserva un registro permanente de cada visita en cada instante. Cubren siempre toda la sesión. Elegir un tramo del video no los recalcula: ese tramo solo filtra la lista de hechos. Elegir otro local de la misma sesión tampoco los recorta ni los vuelve a pedir. La cámara en vivo queda fuera.
- Una visita vinculada es un identificador temporal de esa sesión y esa cámara. No es una persona única, no se reconoce el rostro y no se sigue entre cámaras.
- Un área es una zona que el analista ya configuró en la escena. La secuencia colapsa las entradas seguidas a la misma área. Si el pie queda en dos áreas a la vez, eso no es una transición: el paso se cuenta al salir de una y quedar en la otra, dentro de 1 segundo de video y sin perder el seguimiento. La pausa que corta la secuencia es la misma que ya usa el producto: más de 1 segundo de video sin continuidad, o la pérdida del seguimiento.
- El patrón de locales se deriva de esa secuencia. Solo cuenta cuando el local cambia. No modifica las entradas oficiales ni el funnel.
- Un grupo exige las tres condiciones a la vez: pies a no más de ocho centésimas del ancho del encuadre, direcciones de movimiento dentro de 45 grados y al menos 2 segundos de video. La dirección es la del desplazamiento, no la mirada. Quien está quieto no aporta dirección y no entra. Un hueco de hasta 1 segundo de video no parte el grupo ni inventa posiciones; más de 1 segundo lo cierra. Esos umbrales se muestran junto al número.
- El grupo es una estimación de compañía observable. No dice quién es familiar de quién, no confirma una relación y no es una compra.
- Las ocho métricas ya existentes, la tasa de ingreso, el funnel comercial, el chat mínimo, el mapa de calor y el historial conservan su comportamiento. El chat mínimo no consulta patrones ni grupos. La posible compra, las comparaciones entre sesiones y el chat ampliado quedan fuera. El chat ampliado, cuando exista, tendrá que leer estas cifras y no calcularlas desde el video.
- El contraste manual usa un clip del material elegido y no promete coincidencia con la mano. Hasta ese informe, la pantalla dice que la precisión no está comprometida.
- Los tiempos son tiempos del video. Una cifra sin datos para calcularse se muestra como no disponible, nunca como un cero inventado para tapar esa falta. La ausencia de grupos, cuando sí se pudo evaluar, es cero.
