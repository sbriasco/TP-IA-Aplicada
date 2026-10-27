# Feature Specification: Evaluación de posible compra

**Feature Branch**: `feature/012-posible-compra`

**Azure Boards**: Feature #9, hija del Epic #3 `Evolución final para el 6 de noviembre de 2026`.

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "bueno vamos con la especifiacion siguiente" sobre la Feature #9: evaluar bolsas visibles como indicio experimental de posible compra. Nunca se presenta como una venta confirmada. Queda condicionada a continuidad del seguimiento y a evidencia específica de esa visita.

## Clarifications

### Session 2026-10-26

- Q: Si en el mismo instante hay una bolsa visible y una o más visitas, ¿qué debe cumplir la bolsa para quedar atada a una sola visita? → A: La bolsa queda atada solo si su recuadro se solapa con el de exactamente una visita. Si se solapa con dos o con ninguna, no cuenta.
- Q: ¿La posible compra estimada se cierra en el mismo análisis que ya cierra los hechos, el funnel y los patrones, o en otra pasada sobre el video? → A: Se cierra durante el mismo análisis, junto con los hechos ya observados, y se guarda solo el resultado.
- Q: ¿Qué debe quedar hecho para dar por cumplido el contraste manual de posible compra en esta feature? → A: Cumple con plantilla en `validation/` en «no ejecutado» y el aviso de precisión en pantalla; el ensayo con clip real se hace después y no bloquea la suite ni el cierre de código.
- Q: ¿Qué significa el criterio de éxito que habla de conteos que «coinciden» con bolsas y visitas calculadas a mano? → A: Ambos: la suite sintética con recuadros conocidos y, además, al menos un clip real anotado antes de cerrar la feature.
- Q: ¿Cómo debe nombrarse en la especificación el identificador de la visita que cuenta en la posible compra estimada? → A: «Visita vinculada» en texto de producto; equivale a `track_id` temporal de esa sesión y cámara (una sola glosa).
- Q: ¿Cuándo se considera que el recuadro de una bolsa «se solapa» con el de una visita? → A: Intersección de área > 0 (AABB); exclusivo = exactamente una visita.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Estimar una posible compra por una bolsa observada (Priority: P1)

Como analista, quiero que una visita vinculada cuente una sola vez como posible compra estimada cuando se observa una bolsa junto a esa visita durante el video, para tener un indicio experimental sin tratarlo como una venta ni como la identidad de una persona.

**Why this priority**: Es el resultado de la Feature #9. Se puede comprobar con observaciones de un caso sintético aunque todavía no esté la pantalla. No cambia el tráfico, las entradas, el funnel ni los patrones ya cerrados.

**Independent Test**: Con observaciones de un análisis de video, una visita cuyo recuadro se solapa con el de una bolsa durante al menos 1 segundo de video cuenta una vez. Una bolsa de menos de 1 segundo, una que se solapa con dos visitas o con ninguna, y un seguimiento que se pierde no cuentan. La misma visita no suma dos veces. No hace falta la pantalla ni un video real.

**Acceptance Scenarios**:

1. **Given** un análisis completado de una sesión de video, **When** se lee la posible compra estimada, **Then** cada indicio pertenece solo a esa sesión, esa cámara y ese análisis, y usa instantes del video. Una visita vinculada no se continúa en otra cámara ni con otro identificador.
2. **Given** el recuadro de una bolsa se solapa con el de exactamente esa visita durante al menos 1 segundo de video, sin perderse el seguimiento, **When** se cierra el indicio, **Then** esa visita cuenta una vez como posible compra estimada. El rótulo dice que es una estimación y que no es una venta confirmada. No identifica a la persona ni afirma que la bolsa se haya comprado en un local de la escena.
3. **Given** el solape con esa visita dura menos de 1 segundo de video, **When** se evalúa el indicio, **Then** esa visita no cuenta. Un parpadeo no alcanza.
4. **Given** el solape se interrumpe 1 segundo de video o menos y vuelve con la misma visita, **When** se evalúa el indicio, **Then** el hueco no parte el indicio ni inventa el solape durante ese hueco. Si el tiempo con solape llega a 1 segundo, la visita cuenta una vez.
5. **Given** la bolsa deja de verse más de 1 segundo de video, o el seguimiento se pierde mientras la bolsa está a la vista, **When** se cierra ese tramo, **Then** no se inventa el tiempo que falta ni se confirma el indicio con lo que no se vio. Una visita vinculada nueva no hereda la bolsa de la anterior.
6. **Given** la misma visita vuelve a mostrar una bolsa más tarde, después de un corte, **When** se cuenta la posible compra estimada de la sesión, **Then** esa visita sigue contando una sola vez.
7. **Given** el recuadro de una bolsa se solapa con el de dos visitas, o con el de ninguna, **When** se evalúa el indicio, **Then** no cuenta. No se reparte entre varias visitas ni se atribuye a la más cercana por adivinanza.
8. **Given** una visita entró a un local, se detuvo o tuvo una atención estimada, y ningún recuadro de bolsa se solapa solo con el suyo, **When** se evalúa la posible compra, **Then** no cuenta. La entrada, la detención y la atención no se reinterpretan como compra.
9. **Given** las mismas observaciones, **When** el indicio se calcula otra vez, **Then** las visitas contadas son las mismas. Las ocho métricas ya existentes, la tasa de ingreso, el funnel comercial y los patrones y grupos estimados no cambian.

---

### User Story 2 - Leer la estimación en el resultado (Priority: P2)

Como analista, quiero ver en el resultado de una sesión de video ya terminada cuántas visitas tuvieron una bolsa observada y leer que eso no es una venta, para interpretar el indicio sin volver a mirar el video.

**Why this priority**: La historia anterior ya produce el dato. Esta lo pone a la vista, con el límite de que la precisión no está comprometida. Las comparaciones entre sesiones y el chat ampliado no dependen de esta pantalla para que el dato exista.

**Independent Test**: Abrir el resultado de una sesión de video completada muestra la cantidad de visitas con posible compra estimada, el umbral de 1 segundo de video y el rótulo de que no es una venta confirmada. Elegir un tramo del video o un local no cambia esa cifra. Una sesión de cámara en vivo no la muestra. Cero bolsas se lee como cero, no como no disponible.

**Acceptance Scenarios**:

1. **Given** una sesión de video completada, **When** el analista abre el resultado, **Then** ve la cantidad de visitas con posible compra estimada de toda la sesión, el umbral de 1 segundo de video y el texto de que es una estimación y no es una venta confirmada.
2. **Given** ninguna visita cumplió el umbral, **When** se abre el resultado, **Then** la cantidad es cero y está disponible. No se muestra como no disponible.
3. **Given** el análisis no está completado, falló o fue cancelado, **When** se abre el resultado, **Then** la posible compra estimada no se presenta como un resultado de la sesión y no se reemplaza por un cero.
4. **Given** dos sesiones de video, **When** se abre una, **Then** no aparece la cifra de la otra.
5. **Given** una sesión de cámara en vivo, **When** se abre su resultado, **Then** esta estimación no se muestra y no se reemplaza con la de una sesión de video.
6. **Given** el chat mínimo del resultado, **When** se pregunta si hubo una compra o cuántas bolsas se vieron, **Then** no responde con esta cifra. Esas preguntas quedan para el chat ampliado.
7. **Given** la cifra ya visible, **When** el analista elige un tramo del video o otro local de la misma sesión, **Then** sigue siendo la de toda la sesión. Ese cambio no la recorta ni la vuelve a pedir.
8. **Given** todavía no existe el contraste manual de esta feature, **When** el analista lee el resultado, **Then** ve que la precisión de la posible compra estimada no está comprometida.

---

### User Story 3 - Contrastar con una observación manual (Priority: P2)

Como equipo, quiero dejar listo el lugar del contraste manual y ejecutarlo después sobre un clip del material elegido, para poder mostrar la estimación sin prometer exactitud mientras el ensayo no esté hecho.

**Why this priority**: La precisión no se compromete antes del contraste ejecutado. Las historias anteriores ya pueden mostrar el número como estimación con el aviso correspondiente. El clip real no bloquea el merge de código, pero sí el cierre de Feature #9 en Boards.

**Independent Test**: Existe `validation/contrast.md` en «no ejecutado» y el panel muestra que la precisión no está comprometida. El recorrido de prueba sin clip real da por válidas las otras historias. Antes de cerrar Feature #9, el ensayo con clip (o evidencia insuficiente) queda registrado.

**Acceptance Scenarios**:

1. **Given** la feature entregada en código, **When** se abre el informe de contraste, **Then** está en estado «no ejecutado» y describe el protocolo sin afirmar exactitud ni una venta.
2. **Given** un resultado de sesión mostrado con ese informe aún no ejecutado, **When** el analista lo lee, **Then** ve que la precisión de este dato todavía no está comprometida.
3. **Given** el recorrido habitual de pruebas del equipo, **When** se ejecuta sin el clip real ni la observación manual, **Then** las otras historias siguen pudiendo darse por válidas.
4. **Given** el cierre de Feature #9 en Boards, **When** el equipo ejecuta el contraste sobre un clip del material elegido, **Then** queda registrada cada diferencia y su clasificación, o el informe dice que la evidencia no alcanza.

---

### Edge Cases

- El análisis no está completado (sigue en curso, falló o fue cancelado): la posible compra estimada no se presenta como resultado de la sesión y no se inventa un cero.
- La bolsa se ve menos de 1 segundo de video: esa visita no cuenta.
- La bolsa desaparece 1 segundo de video o menos y reaparece junto a la misma visita: el indicio sigue y no se inventa la bolsa en ese hueco. Si falta más de 1 segundo, ese tramo se cierra.
- El seguimiento se pierde con la bolsa a la vista: no se completa el indicio ni se inventa duración. Una visita nueva no hereda la bolsa.
- La misma visita muestra la bolsa otra vez, después de un corte: en el conteo de la sesión suma una sola vez.
- El recuadro de la bolsa se solapa con dos visitas o con ninguna: no cuenta y no se reparte. No se elige la más cercana.
- Hubo entrada, detención o atención estimada y no hubo bolsa observada: no hay posible compra estimada. Esas etapas no se reinterpretan.
- No hubo ningún indicio: la cantidad es cero y está disponible.
- La sesión es de cámara en vivo: esta estimación no se calcula ni se muestra.
- Dos sesiones se consultan a la vez: ninguna ve la cifra de la otra.
- El analista elige un tramo del video o otro local: la cifra sigue siendo la de toda la sesión.
- El video termina cuando la bolsa ya llevaba al menos 1 segundo a la vista: el indicio se conserva hasta el último instante observado. Si no llegaba a 1 segundo, no se confirma.
- Una bolsa visible no dice en qué local se compró, no confirma un pago y no identifica a la persona.
- Una segunda pasada sobre el video ya analizado no vuelve a calcular ni corrige esta cifra: el resultado cerrado durante el análisis sigue igual.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Durante el mismo análisis de una sesión de video que ya cierra hechos, funnel y patrones, el sistema MUST cerrar la posible compra estimada de esa sesión y esa cámara a partir de los solapes observados entre recuadros de bolsa y de visita, y MUST guardar solo ese resultado. MUST usar instantes del video, nunca la duración del procesamiento. MUST NOT calcularla después en otra pasada sobre el video. Cada indicio MUST pertenecer a una sola sesión, una sola cámara y un solo análisis.
- **FR-002**: Una visita vinculada MUST contar como posible compra estimada solo cuando el recuadro de una bolsa se solapa con el de exactamente esa visita durante al menos 1 segundo de video y sin perderse el seguimiento. Hay solape si el área de intersección de los dos recuadros AABB es mayor que cero; el solape es exclusivo cuando exactamente una visita cumple eso para esa bolsa. El sistema MUST rotular el resultado como estimación y MUST decir que no es una venta confirmada. MUST NOT identificar a la persona, MUST NOT afirmar que la bolsa se compró en un local de la escena y MUST NOT confirmar un pago.
- **FR-003**: Un solape de menos de 1 segundo de video MUST NOT contar. Un hueco de hasta 1 segundo en el que deja de haber solape exclusivo MUST NOT partir el indicio ni inventar el solape en ese hueco. Más de 1 segundo, o la pérdida del seguimiento, MUST cerrar ese tramo sin inventar el tiempo que falta. Si el video termina y el solape exclusivo ya llevaba al menos 1 segundo, el indicio MUST conservarse hasta el último instante observado. Si no llegaba a 1 segundo, MUST NOT confirmarse.
- **FR-004**: Cada visita MUST contar a lo sumo una vez en la sesión, aunque el solape vuelva después de un corte. Una visita vinculada nueva MUST NOT heredar la bolsa de otra ni unirse con otro identificador. MUST NOT seguirse una visita entre cámaras.
- **FR-005**: Si el recuadro de la bolsa se solapa con dos visitas o con ninguna, MUST NOT contar y MUST NOT repartirse ni atribuirse a la más cercana. Una entrada, una detención o una atención estimada sin solape exclusivo con una bolsa MUST NOT contar como posible compra.
- **FR-006**: Calcular otra vez con las mismas observaciones MUST devolver las mismas visitas. Las ocho métricas ya existentes, la tasa de ingreso, el funnel comercial y los patrones y grupos estimados MUST permanecer iguales en nombre y en valor. La consulta que ya entrega esas ocho métricas MUST NOT incluir esta cifra.
- **FR-007**: Un análisis que no está completado MUST NOT presentarse como posible compra estimada de la sesión, y MUST NOT reemplazarse por un cero. Las consultas MUST aislar los datos entre sesiones. Una sesión de cámara en vivo MUST NOT calcular ni mostrar esta estimación.
- **FR-008**: El resultado de una sesión de video completada MUST mostrar la cantidad de visitas con posible compra estimada de toda la sesión, el umbral de 1 segundo y el rótulo de que no es una venta confirmada. Si no hubo indicios, la cantidad MUST ser cero y estar disponible. Elegir un tramo del video o otro local de la misma sesión MUST NOT cambiar esta cifra ni volver a pedirla. Mientras no exista el contraste manual de esta feature, el resultado MUST decir que la precisión no está comprometida. El chat mínimo MUST NOT responder con esta cifra.
- **FR-009**: Para dar por entregada esta feature en código, el equipo MUST dejar en `validation/` un informe de contraste con estado «no ejecutado» y el resultado MUST seguir diciendo que la precisión no está comprometida. Ejecutar el contraste sobre un clip real (anotar bolsas, clasificar diferencias; si el material no alcanza, decirlo) es trabajo posterior del equipo y MUST NOT bloquear la suite automatizada ni la aceptación de las otras historias. Ese contraste, cuando se ejecute, MUST NOT afirmar exactitud ni una venta.

### Key Entities

- **Visita vinculada**: Recorrido temporal dentro de una sesión y una cámara. En persistencia y API es el `track_id` de esa sesión/cámara. No es una persona única ni se continúa con otro identificador.
- **Bolsa observada**: Bolsa visible cuyo recuadro AABB se solapa (área de intersección > 0) con el de exactamente una visita durante un tramo del video. No es un producto identificado ni un comprobante de pago.
- **Posible compra estimada**: La misma visita cuenta una vez en la sesión cuando ese solape exclusivo alcanza al menos 1 segundo de video sin perder el seguimiento. Es una estimación. No es una venta confirmada ni se atribuye a un local.
- **Contraste manual de posible compra**: Informe en `validation/` que, al entregar el código, puede quedar en «no ejecutado». Cuando se ejecute, compara un clip elegido con el resultado de esa sesión y clasifica diferencias. Si no se pueden marcar bolsas, el informe lo dice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el caso sintético, una visita cuyo recuadro se solapa en exclusiva con el de una bolsa al menos 1 segundo de video cuenta una vez, y un solape de menos de 1 segundo no cuenta. Un hueco de hasta 1 segundo no inventa el solape ni parte el indicio. Si el seguimiento se pierde, la visita siguiente no hereda la bolsa. La misma visita no cuenta dos veces aunque el solape reaparezca.
- **SC-002**: Hay dos capas. (1) En el caso sintético automatizado, con recuadros conocidos y conteo esperado escrito de antemano, los números coinciden: una bolsa que se solapa con dos visitas o con ninguna no cuenta; una entrada, detención o atención sin solape exclusivo no cuenta; recalcular con las mismas observaciones no cambia ningún número. (2) Antes de dar por cerrada la Feature #9 en el tablero del equipo, al menos un clip real anotado a mano debe contrastarse con el resultado (o el informe debe decir que la evidencia no alcanza). La capa (2) no forma parte del recorrido de prueba automatizado ni bloquea la entrega de código; la capa (1) sí.
- **SC-003**: El 100 % de las posibles compras estimadas se leen como estimación y ninguna se describe como venta confirmada, pago, local de compra o identidad de una persona.
- **SC-004**: En el 100 % de las sesiones del caso de prueba, las ocho métricas ya existentes, la tasa de ingreso, el funnel comercial y los patrones y grupos estimados quedan iguales después de armar esta estimación. El 100 % de las consultas de esas ocho métricas sigue sin incluir esta cifra.
- **SC-005**: En el 100 % de las sesiones de video completadas sin indicios, la cantidad es cero y está disponible. En el 100 % de los análisis incompletos, fallidos o cancelados, la cifra no se presenta como resultado y no se reemplaza por cero. El 100 % de esas cifras pertenecen a la sesión pedida.
- **SC-006**: Un analista reconoce, en el resultado de una sesión de video completada y sin volver a abrir el video, la cantidad, el umbral de 1 segundo y que la precisión sigue sin comprometer. Al elegir un tramo o un local de la misma sesión, el 100 % de esa cifra permanece igual a la de toda la sesión. En una sesión de cámara en vivo, este dato no aparece.
- **SC-007**: Al entregar el código, existe el informe de contraste en `validation/` con estado «no ejecutado» y la pantalla mantiene el aviso de precisión no comprometida. El recorrido de prueba sin clip real valida las otras historias. Antes de cerrar Feature #9 en Boards, el equipo ejecuta ese contraste (capa 2 de SC-002): el informe pasa a incluir la observación manual, el resultado y las diferencias clasificadas sin declarar exactitud ni una venta, o dice que la evidencia no alcanza.

## Assumptions

- La sesión de video y un análisis completado ya existen. Esta feature no vuelve a definir la carga, el editor, el seguimiento, el funnel ni los patrones de visita. No agrega un paso nuevo de calibración.
- La única señal de esta feature es una bolsa visible cuyo recuadro AABB se solapa (área > 0) con el de exactamente una visita. Si se solapa con dos o con ninguna, no cuenta. Otras señales (ticket, pago, mirada a un producto, permanencia o atención) quedan fuera. La bolsa no se atribuye a un local y no agrega una etapa al funnel.
- La posible compra estimada se cierra durante el mismo análisis que hechos, funnel y patrones, y se guarda solo el resultado. No se recalcula en otra pasada sobre el video. Cubre siempre toda la sesión. Elegir un tramo del video o un local no la recalcula. La cámara en vivo queda fuera.
- Una visita vinculada es el término de producto para el `track_id` temporal de esa sesión y esa cámara. No es una persona única, no se reconoce el rostro y no se sigue entre cámaras. La pérdida del seguimiento corta el indicio. El hueco que no lo corta es el mismo que ya usa el producto: hasta 1 segundo de video.
- El umbral de 1 segundo de video evita contar un parpadeo. Se muestra junto al número. No se compromete como una medida de precisión del detector.
- Las ocho métricas ya existentes, la tasa de ingreso, el funnel comercial, los patrones y grupos estimados, el chat mínimo, el mapa de calor y el historial conservan su comportamiento. El chat mínimo no consulta esta cifra. Las comparaciones entre sesiones y el chat ampliado quedan fuera. El chat ampliado, cuando exista, tendrá que leer esta cifra y no calcularla desde el video.
- El contraste manual del código entregado es la plantilla en `validation/` en «no ejecutado» (no bloquea merge ni suite). El ensayo con clip real es posterior y es requisito para cerrar Feature #9 en Boards (SC-002 capa 2 / SC-007). Hasta ejecutarlo, la pantalla dice que la precisión no está comprometida. Cuando se ejecute, no promete coincidencia con la mano; si el material no alcanza para marcar bolsas, el informe lo dice y no aparece una venta.
- Los tiempos son tiempos del video. Una cifra sin datos para calcularse se muestra como no disponible, nunca como un cero inventado para tapar esa falta. La ausencia de indicios, cuando sí se pudo evaluar, es cero.
