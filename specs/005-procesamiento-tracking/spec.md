# Feature Specification: Procesamiento y seguimiento con vista en vivo

**Feature Branch**: `feature/005-procesamiento-tracking`

**Azure Boards**: Feature #13, hija del Epic #1 `MVP 2/oct`. User Stories #56, #57, #58, #59 y #60.

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Feature #13 de Azure Boards (Epic #1 MVP 2/oct): procesar un video real ya registrado y configurado, mostrar el seguimiento anónimo mientras corre, informar el avance y los conteos parciales, poder cancelar, y dejar evidencia de cómo se comportó en el equipo de referencia. Depende de una sesión con video disponible y de una versión de escena válida (Feature #12). Fuera de alcance: el tablero, el chat, el mapa de calor y el resto de métricas comerciales comprometidas."

## Clarifications

### Session 2026-09-29

- Q: ¿Las entradas, las salidas y la ocupación visible que quedan cuando un análisis termina bien son los números oficiales de esa sesión? → A: Sí. Al terminar bien, esos tres conteos son los oficiales de la sesión. El tablero y el resto de las métricas los leen y no los reemplazan con otro cálculo.
- Q: Cuando el operador cancela un análisis que todavía no terminó, ¿en qué estado queda el trabajo? → A: Queda en «cancelado», distinto de «fallido». Los demás estados son pendiente, procesando, completado y fallido. Una caída del proceso sigue en fallido.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Procesar un video real y conservar el seguimiento anónimo (Priority: P1) · Boards #56

Como operador, quiero iniciar el análisis de un video ya registrado y, al terminar, tener el seguimiento anónimo de las personas atado al instante del video, para poder consultar después qué pasó en esa sesión.

**Why this priority**: Es el camino crítico de la Feature #13. Sin un análisis completado no hay vista en vivo útil, avance ni conteos.

**Independent Test**: Con una sesión que ya tiene video disponible y una escena válida, se inicia el análisis y, al llegar a un estado terminal, la sesión conserva seguimientos anónimos con instante de video. Un recorrido de prueba, sin video real ni el equipo de referencia, debe poder demostrar el mismo cierre.

**Acceptance Scenarios**:

1. **Given** una sesión con video disponible en este equipo y una versión de escena elegida de la misma cámara, **When** el operador inicia el análisis, **Then** el trabajo pasa de pendiente a procesando, queda asociado solo a esa sesión y guarda esa versión.
2. **Given** un análisis procesando, **When** termina sin error, **Then** el trabajo queda completado y cada observación conserva el instante del video, el identificador temporal de seguimiento y el punto de referencia en los pies, y queda registrada la versión del método de detección y de seguimiento usada.
3. **Given** un análisis completado, **When** se consulta la sesión, **Then** las trayectorias quedan como una muestra asociada a la sesión, no como un registro permanente de cada persona en cada instante.
4. **Given** un video que no se puede analizar (archivo ausente, escena inválida o fallo del método), **When** el análisis no puede continuar, **Then** el trabajo queda fallido con un motivo estable y reconocible, sin marcar la sesión como analizada.
5. **Given** el recorrido de prueba sin video real, **When** se ejecuta el análisis de demostración, **Then** el trabajo llega a un estado terminal y deja el mismo tipo de resultado que un análisis real.

---

### User Story 2 - Ver el video con el seguimiento mientras se analiza (Priority: P1) · Boards #57

Como operador, quiero ver el video con recuadros, identificadores temporales, zonas, línea de entrada y hechos recientes, para comprobar que el análisis sigue a las personas de esa escena.

**Why this priority**: Permite confiar en el resultado antes de mirar números. No promete verse a la misma velocidad que el video.

**Independent Test**: Durante un análisis procesando, la vista muestra una imagen cuyo instante coincide con el instante informado, con el seguimiento y la escena de esa sesión dibujados encima.

**Acceptance Scenarios**:

1. **Given** un análisis procesando de una sesión configurada, **When** el operador abre la vista en vivo, **Then** ve recuadros, identificadores temporales, las zonas, la línea de entrada y los hechos recientes de esa sesión.
2. **Given** una imagen de la vista en vivo, **When** se compara con el instante que declara, **Then** ambos corresponden al mismo momento del video.
3. **Given** un observador que recibe las imágenes con demora, **When** mira la vista, **Then** ve la imagen más reciente disponible para ese instante, sin mezclar momentos de otra sesión.
4. **Given** un video real procesado en el equipo del operador, **When** termina la vista, **Then** queda registrada la velocidad observada, sin comprometer que iguale la del video.

---

### User Story 3 - Seguir el avance y los conteos parciales (Priority: P1) · Boards #58

Como operador, quiero ver cuánto del video ya se analizó y conteos todavía parciales de entradas, salidas y ocupación visible, para no esperar al final sin saber si el análisis avanza.

**Why this priority**: El procesamiento puede tardar más que la duración del video. El avance tiene que medirse sobre el video, no sobre el reloj de la computadora.

**Independent Test**: Mientras un análisis corre, el avance crece según el tiempo o los fotogramas ya recorridos, y los tres conteos aparecen marcados como parciales hasta el cierre.

**Acceptance Scenarios**:

1. **Given** un análisis procesando, **When** el operador consulta el avance, **Then** ve el tramo de video ya analizado (tiempo o fotogramas) y no el tiempo que lleva el proceso.
2. **Given** un análisis que todavía no está completado, **When** se muestran entradas, salidas y ocupación visible, **Then** cada valor está marcado como parcial.
3. **Given** un análisis que queda completado, **When** se vuelven a consultar esas tres medidas, **Then** los valores finales reemplazan a los parciales y quedan como los números oficiales de entradas, salidas y ocupación visible de esa sesión.
4. **Given** un tramo sin personas o sin cruces, **When** se calculan los conteos, **Then** el resultado es cero o no disponible, y una división sin denominador se muestra como no disponible.

---

### User Story 4 - Dejar evidencia en el equipo de referencia (Priority: P1) · Boards #60

Como equipo, queremos dejar asentado cómo se comportó el análisis de un video real en el equipo de referencia, para saber si el procesador gráfico sirvió y a qué ritmo se procesó.

**Why this priority**: El MVP no puede prometer velocidad hasta medirla. La evidencia cierra esa duda sin bloquear a quien no tiene ese equipo.

**Independent Test**: En el equipo de referencia se analiza un video real corto y queda un registro con el equipo usado, las versiones del método y los fotogramas procesados por segundo de procesamiento. Si el procesador gráfico no puede usarse, el mismo video termina en el procesador principal y la limitación queda escrita.

**Acceptance Scenarios**:

1. **Given** el equipo de referencia y un video real ya configurado, **When** el análisis termina, **Then** el registro indica el equipo usado, las versiones del método y la velocidad de procesamiento observada.
2. **Given** que el procesador gráfico no está disponible o el análisis allí falla, **When** se reintenta por el procesador principal, **Then** el video igual puede terminar y la limitación queda documentada.
3. **Given** el recorrido habitual de pruebas del equipo, **When** se ejecuta sin el equipo de referencia, **Then** no exige ese procesador gráfico para dar por válido el resto de la feature.

---

### User Story 5 - Cancelar un análisis (Priority: P2) · Boards #59

Como operador, quiero cancelar un análisis que no quiero terminar, para que deje de consumir el equipo y lo ya guardado no se presente como un resultado completo.

**Why this priority**: Es deseable para el MVP, pero el análisis, la vista y el avance ya entregan valor sin cancelación.

**Independent Test**: Con un análisis procesando se pide cancelar; el trabajo queda cancelado, no sigue con fotogramas nuevos y lo ya persistido queda marcado como incompleto, sin reiniciarse solo.

**Acceptance Scenarios**:

1. **Given** un análisis procesando, **When** el operador lo cancela, **Then** el trabajo pasa a cancelado, no a fallido, y el procesamiento se detiene en el límite del fotograma en curso.
2. **Given** un análisis cancelado que ya había guardado observaciones o conteos, **When** se consulta la sesión, **Then** esos datos figuran como incompletos.
3. **Given** un análisis cancelado o fallido, **When** nadie vuelve a iniciarlo, **Then** no se reanuda ni se reintenta por su cuenta.

---

### Edge Cases

- El video de la sesión no está en este equipo: el análisis no empieza, o queda fallido, con un motivo estable, y no se mezclan datos de otra sesión.
- La escena falta, es de otra cámara, o la proporción del video difiere en más de 1 % de la del frame de la versión elegida: el análisis no empieza y se indica que hay que corregir la configuración.
- El seguimiento de una persona se pierde: no se inventa permanencia ni se reutiliza su identificador temporal como si fuera la misma persona.
- Un identificador temporal cambia sobre la línea de entrada: ese cambio no suma una entrada ni confirma una salida.
- Una persona oscila sobre la línea de entrada: no se cuentan entradas o salidas duplicadas por ese vaivén.
- El análisis se interrumpe porque se detiene el proceso (no por cancelación del operador): el trabajo pasa a fallido, con motivo de interrupción, y lo ya guardado no se presenta como resultado final. No se reintenta solo.
- La vista en vivo se abre tarde o va más lenta que el análisis: muestra el último momento ya disponible de esa sesión, sin acumular imágenes viejas como si fueran el presente.
- No hay personas, no hay cruces o el denominador de una tasa es cero: el conteo es cero o no disponible, nunca un valor inventado.
- Dos análisis de sesiones distintas compiten en el mismo equipo: solo uno está procesando; el otro espera o informa que debe esperar, sin mezclar resultados.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir iniciar el análisis solo de una sesión con video disponible en el equipo y solo con una versión de escena de la misma cámara. MUST guardar en el trabajo la versión elegida (la última, o una anterior si el operador la cambia) y MUST bloquear el inicio si la proporción del video difiere en más de 1 % de la del frame de esa versión.
- **FR-002**: El sistema MUST ejecutar como máximo un análisis procesando por equipo y MUST aislar observaciones, trayectorias y conteos de una sesión respecto de las demás.
- **FR-003**: El sistema MUST registrar, para cada observación, el instante del video, el identificador temporal de seguimiento y el punto de los pies como referencia de posición.
- **FR-004**: El sistema MUST tratar cada identificador temporal como propio de esa sesión y esa cámara, sin presentarlo como identidad de una persona ni reutilizarlo entre sesiones.
- **FR-005**: El sistema MUST conservar una muestra de trayectorias asociada a la sesión, y MUST NOT guardar un registro permanente por persona y por instante del video.
- **FR-006**: El sistema MUST registrar en el análisis la versión del método de detección, la versión del seguimiento y los parámetros con los que se obtuvo el resultado.
- **FR-007**: El sistema MUST medir tiempos de negocio con los instantes del video, nunca con la duración del procesamiento.
- **FR-008**: Si el análisis no puede completarse, el sistema MUST dejar el trabajo en estado fallido con un motivo estable y reconocible, y MUST NOT presentar la sesión como analizada por completo.
- **FR-009**: El sistema MUST ofrecer un recorrido de prueba, sin video real y sin el equipo de referencia, que llegue a un estado terminal con el mismo tipo de resultado de negocio.
- **FR-010**: Durante un análisis, el sistema MUST mostrar una vista con recuadros, identificadores temporales, zonas, línea de entrada y hechos recientes de esa sesión, sincronizada con el instante del video de cada imagen.
- **FR-011**: Si la vista no puede seguir el ritmo del análisis, el sistema MUST mostrar el momento más reciente disponible de esa sesión.
- **FR-012**: El sistema MUST informar el avance según el tiempo o los fotogramas del video ya analizados.
- **FR-013**: Mientras el análisis no terminó, el sistema MUST mostrar entradas, salidas y ocupación visible marcadas como parciales. La ocupación visible MUST distinguirse de cualquier ocupación total del local.
- **FR-014**: Al quedar completado, el sistema MUST reemplazar esas tres medidas parciales por los valores finales de la misma sesión. Esos valores MUST ser los números oficiales de entradas, salidas y ocupación visible de la sesión. Las features posteriores MUST consultarlos y MUST NOT reemplazarlos con un segundo cálculo.
- **FR-015**: El sistema MUST evitar entradas o salidas duplicadas por oscilación sobre la línea. Un cambio de identificador temporal MUST NOT sumar por sí solo una entrada ni una salida. El sistema MUST mostrar como no disponible cualquier tasa cuyo denominador sea cero.
- **FR-016**: El operador MUST poder cancelar un análisis procesando. El trabajo MUST pasar a cancelado, no a fallido. El procesamiento MUST detenerse en el límite del fotograma en curso, lo ya guardado MUST quedar marcado como incompleto, y el trabajo MUST NOT reintentarse solo. Una interrupción del proceso MUST dejar el trabajo en fallido.
- **FR-017**: En el equipo de referencia, un análisis de video real MUST dejar registro del equipo usado, de las versiones del método y de la velocidad observada en fotogramas por segundo de procesamiento. Si el procesador gráfico no puede usarse, el mismo flujo MUST poder terminar en el procesador principal y la limitación MUST quedar documentada.
- **FR-018**: El sistema MUST NOT prometer que la vista o el análisis igualen la velocidad del video. La velocidad queda como medición, no como compromiso.

### Key Entities

- **Análisis**: Trabajo de una sesión. Tiene estado pendiente, procesando, completado, fallido o cancelado (antes llamados «en curso» y «terminado»), motivo cuando falla, versión de escena elegida, versión del método y parámetros, avance sobre el video y marca de resultado completo o incompleto.
- **Observación**: Persona anónima vista en un instante del video, con identificador temporal, recuadro y punto de referencia en los pies. Pertenece a un solo análisis y sesión.
- **Muestra de trayectoria**: Recorrido resumido de un identificador temporal dentro de la sesión, asociado a la sesión para consulta posterior.
- **Conteo parcial**: Entradas, salidas u ocupación visible todavía no definitivas, siempre distinguibles de los valores finales de la misma sesión. Al cierre exitoso, esos finales son los números oficiales de la sesión.
- **Evidencia de ejecución**: Registro de en qué equipo corrió el análisis, qué versiones se usaron y a qué ritmo se procesó.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En la prueba de referencia, el 100% de las observaciones guardadas de una sesión analizada tiene instante de video, identificador temporal y sesión propia, y ninguna se consulta desde otra sesión.
- **SC-002**: En la vista en vivo, cada imagen coincide con el instante de video que declara (desfase de instante igual a cero) en la muestra revisada de esa sesión.
- **SC-003**: El avance mostrado corresponde al tramo de video ya recorrido. En un video de duración conocida, al 50% de los fotogramas analizados el avance informado es el 50%, con una tolerancia de un fotograma.
- **SC-004**: Hasta el cierre, entradas, salidas y ocupación visible se muestran como parciales. Tras un cierre exitoso, esos tres valores son los oficiales de la sesión, coinciden con su recuento y ya no figuran como parciales. Ninguna consulta posterior los sustituye por otro cálculo.
- **SC-005**: Tras cancelar, no se procesan fotogramas posteriores al fotograma en curso, lo ya guardado queda marcado incompleto y el análisis no se reinicia solo.
- **SC-006**: En el equipo de referencia, un video real de menos de dos minutos termina de analizarse y el registro incluye equipo, versiones del método y fotogramas procesados por segundo de procesamiento. Si el procesador gráfico no está disponible, el mismo video termina por el procesador principal y la limitación queda escrita.
- **SC-007**: Los seis integrantes pueden reproducir el recorrido de prueba sin video real y obtener un análisis en estado terminal, con avance y cierre, sin usar el equipo de referencia.

## Assumptions

- La sesión, el video en el equipo, el frame de referencia y una versión de escena válida ya existen (Feature #12). Esta feature no vuelve a definir la carga ni el editor.
- El método de detección y de seguimiento es el ya evaluado como viable con los videos disponibles. Esta feature registra qué versión se usó. Comparar otro método queda fuera, salvo que esa evidencia se vuelva a abrir en una decisión aparte.
- Las únicas medidas de esta feature son entradas, salidas y ocupación visible: parciales durante el análisis y, al terminar bien, los números oficiales de la sesión. El tablero, el chat, el mapa de calor y el resto de métricas comerciales quedan para features posteriores, y esas features leen estos tres valores sin recalcularlos.
- La ocupación que se muestra es la visible en cámara. No se infiere ocupación total del local ni permanencia cuando el seguimiento se pierde.
- Un identificador temporal no es una persona real y no se sigue entre cámaras.
- La vista en vivo reutiliza el canal de avance ya previsto para la sesión. El límite de tamaño de la vista de prueba no se aplica al video real. Un observador lento recibe solo el momento más reciente y no detiene el análisis. No se define aquí un canal nuevo ni se compromete fluidez en tiempo real.
- Hace falta un solo análisis procesando por equipo. El equipo de referencia tiene un procesador gráfico dedicado, pero el flujo habitual debe funcionar sin él.
- La evidencia del equipo de referencia se redacta sin rutas absolutas, nombres de máquina ni datos personales.
- La cancelación es parte del MVP, con prioridad menor que el análisis, la vista y el avance.
