# Feature Specification: Carga, configuración y editor visual de escenas

**Feature Branch**: `feature/004-configuracion-escenas`

**Azure Boards**: Feature #12, hija del Epic #1 `MVP 2/oct`. User Stories #53, #54 y #55.

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Feature #12 de Azure Boards (Epic #1 MVP 2/oct): carga, configuración y editor visual de escenas. Cubre las User Stories #53 (registrar un video local como sesión), #54 (definir y versionar la configuración espacial de una cámara) y #55 (editor visual de zonas y líneas sobre el frame de referencia), con los criterios de aceptación cargados en Boards. Extiende el data-model de specs/002 (`Session.source_kind = video_file`, migración Alembic, FK compuestas por sesión). La persistencia puede ser PostgreSQL local o Azure Flexible Server (misma `FLOWSIGHT_DATABASE_URL`), mientras los videos quedan en disco local: guardar el identificador del equipo de origen y el hash del archivo. Convenciones de zonas y línea A/B del experimento 001. Fuera de alcance: procesamiento YOLO/ByteTrack real, eventos, métricas, dashboard y chat."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar un video local como sesión (Priority: P1) · Boards #53

Como operador, quiero registrar un video grabado que está en mi equipo y obtener sus metadatos, para crear una sesión de análisis real sobre ese video.

**Why this priority**: Es la raíz del camino crítico del MVP. Sin una sesión con video y frame de referencia no se puede configurar la escena ni, más adelante, procesar el video (#56).

**Independent Test**: Registrar un video corto de prueba y comprobar que la sesión muestra resolución, fps, duración, frame de referencia, equipo de origen y hash, y que el archivo de video no se copió a la base de datos.

**Acceptance Scenarios**:

1. **Given** un archivo de video local legible y en un formato soportado, **When** el operador lo registra indicando un nombre de sesión y un identificador de cámara, **Then** se crea una sesión de tipo `video_file` con resolución, fps, duración, un frame de referencia, la ubicación del archivo, el identificador del equipo de origen y el hash del contenido.
2. **Given** una sesión de video registrada, **When** se consulta la base de datos, **Then** solo hay metadatos, ubicación y frame de referencia; el contenido del video permanece en el disco del equipo.
3. **Given** la base es compartida entre integrantes, **When** otro integrante abre la sesión desde un equipo que no tiene el video, **Then** el sistema indica que el video no está disponible en ese equipo, sin error genérico, y sigue mostrando los metadatos y el frame de referencia.
4. **Given** una sesión cuyo video no está en la ubicación registrada, **When** el operador indica una nueva ubicación del archivo en su equipo, **Then** el sistema la acepta solo si el hash coincide con el registrado y, si no coincide, la rechaza indicando que es otro archivo.
5. **Given** un archivo inexistente, ilegible, vacío, sin frames decodificables o en un formato no soportado, **When** el operador intenta registrarlo, **Then** no se crea ninguna sesión y se muestra un mensaje accionable que indica la causa y qué hacer.

---

### User Story 2 - Definir y versionar la configuración espacial de una cámara (Priority: P1) · Boards #54

Como operador, quiero cargar los locales, sus zonas y sus líneas de entrada para una cámara, para que el análisis use una escena definida y reproducible.

**Why this priority**: Todos los eventos y métricas del MVP (#63, #64) se calculan contra esta configuración. Sin versiones inmutables no se puede saber con qué escena se calculó un resultado.

**Independent Test**: Enviar una configuración válida y varias inválidas sin usar el editor visual; comprobar que la válida queda como versión nueva inmutable, que las inválidas se rechazan con el motivo, y que un trabajo de análisis registra la versión usada.

**Acceptance Scenarios**:

1. **Given** una sesión de video con frame de referencia, **When** el operador guarda una configuración con al menos un local que tiene zona frontal, línea de entrada con lados A/B asociados a entrada y salida, y opcionalmente zona interior y zona de vidriera, **Then** se guarda como una versión nueva, numerada y con fecha de creación.
2. **Given** una configuración, **When** se guarda, **Then** todas las coordenadas quedan normalizadas al rango [0, 1] respecto del ancho y alto del frame de referencia.
3. **Given** un polígono con menos de 3 vértices, con lados que se autointersectan o con área nula, o una línea cuyos extremos coinciden, **When** se intenta guardar, **Then** se rechaza la configuración completa y se indica qué elemento y qué regla fallaron.
4. **Given** una versión guardada, **When** alguien intenta modificarla o eliminarla, **Then** el sistema no lo permite; los cambios siempre generan una versión nueva.
5. **Given** una cámara sin ninguna configuración válida, **When** se intenta iniciar un análisis de una sesión de video de esa cámara, **Then** el sistema lo rechaza con un mensaje que pide configurar la escena primero.
6. **Given** una cámara con varias versiones, **When** se inicia un análisis, **Then** el trabajo queda asociado a una versión concreta, que sigue siendo consultable aunque después se guarden versiones más nuevas.

---

### User Story 3 - Editor visual de zonas y líneas sobre el frame de referencia (Priority: P1) · Boards #55

Como operador, quiero dibujar y editar zonas y líneas sobre el frame de referencia, para configurar un video nuevo sin editar archivos a mano.

**Why this priority**: Decidido el 2026-09-26 como obligatorio para el MVP del 2/oct. Es la forma prevista de producir configuraciones de la User Story 2.

**Independent Test**: Abrir el editor para una sesión, dibujar un local completo, mover vértices, cambiar el sentido de entrada, redimensionar la ventana, guardar y verificar que la versión nueva tiene las mismas coordenadas normalizadas que se ven en pantalla.

**Acceptance Scenarios**:

1. **Given** una sesión con frame de referencia, **When** el operador abre el editor, **Then** ve el frame y, si existe, la última versión de la configuración de la cámara dibujada encima.
2. **Given** el editor abierto, **When** el operador crea un polígono o una línea, mueve sus vértices o extremos, o los elimina, **Then** el dibujo se actualiza en el momento y cada elemento queda asociado a un local y a un rol (interior, frontal, vidriera o línea de entrada).
3. **Given** una línea de entrada, **When** el operador elige el sentido de entrada, **Then** el editor muestra claramente qué lado es A, qué lado es B y cuál de los dos sentidos cuenta como entrada.
4. **Given** una configuración dibujada, **When** la vista se redimensiona (ventana, zoom del navegador o pantalla distinta), **Then** los elementos siguen alineados con los mismos puntos de la imagen y las coordenadas guardadas no cambian.
5. **Given** cambios sin guardar, **When** el operador guarda, **Then** se crea una versión nueva mediante las mismas reglas de validación de la User Story 2; si la validación falla, el editor señala los elementos inválidos y no pierde el dibujo.
6. **Given** cambios sin guardar, **When** el operador intenta salir del editor, **Then** se le advierte que perderá los cambios.

---

### Edge Cases

- Videos cuya cantidad de frames declarada no es fiable (p. ej. MPEG): la duración y la cantidad de frames deben obtenerse de forma que no dependan solo del encabezado (lección del experimento 001).
- Video con fps variable o ausente en el encabezado: se registra el valor que se pueda medir y se marca como estimado, o se rechaza con motivo si no se puede determinar.
- El mismo archivo (mismo hash) registrado dos veces: se permite crear otra sesión, y el sistema avisa que ya existe una sesión con ese video.
- El video se mueve, renombra o borra después de registrarlo: la sesión sigue existiendo y se marca como video no disponible en ese equipo.
- Archivos muy grandes: calcular el hash no debe bloquear la interfaz sin indicar progreso.
- Polígonos con vértices fuera del frame: se rechazan; las coordenadas normalizadas deben quedar dentro de [0, 1].
- Una línea de entrada que no toca ni atraviesa la zona frontal ni, si existe, la interior del mismo local: se permite, pero se advierte.
- Local sin zona interior (la cámara no ve el interior del comercio): es válido; los análisis posteriores no pueden inferir permanencia ni ocupación interior de ese local y deben mostrarlas como no disponibles.
- Zonas de distintos locales que se superponen: se permite (pasillos y vidrieras vecinas pueden solaparse en la imagen), pero se advierte.
- Dos personas guardan una versión de la misma cámara al mismo tiempo con la base compartida: ambas versiones se guardan con números distintos y ninguna sobrescribe a la otra.
- Una sesión de otra cámara con distinta resolución usa la configuración de la cámara: las coordenadas normalizadas se aplican igual, pero el sistema advierte si la relación de aspecto del video no coincide con la del frame de referencia de la versión.

## Requirements *(mandatory)*

### Functional Requirements

**Registro de video (US #53)**

- **FR-001**: El sistema DEBE permitir registrar un archivo de video local como una sesión nueva, con nombre de sesión e identificador de cámara indicados por el operador.
- **FR-002**: El sistema DEBE verificar que el archivo existe, se puede leer y tiene al menos un frame decodificable antes de crear la sesión.
- **FR-003**: El sistema DEBE guardar por sesión: resolución (ancho y alto en píxeles), fps, duración en segundos del video, cantidad de frames, ubicación del archivo en el equipo de origen, identificador del equipo de origen, hash del contenido del archivo y fecha de registro.
- **FR-004**: El sistema DEBE extraer y conservar un frame de referencia de la sesión, junto con su índice de frame y su timestamp del video. Por defecto se usa el primer frame decodificable.
- **FR-005**: El sistema NO DEBE almacenar el contenido del video en la base de datos; el archivo permanece en el disco del equipo.
- **FR-006**: El sistema DEBE distinguir las sesiones de video de las sintéticas existentes mediante el tipo de origen `video_file`, sin alterar las sesiones sintéticas ya creadas.
- **FR-007**: El sistema DEBE indicar, para cada sesión de video, si el archivo está disponible en el equipo actual, comprobando el equipo de origen, la ubicación y el hash.
- **FR-008**: El sistema DEBE permitir indicar una nueva ubicación del video de una sesión en el equipo actual, y aceptarla solo si el hash coincide con el registrado.
- **FR-009**: Ante un archivo inexistente, ilegible, vacío, sin frames o en formato no soportado, el sistema DEBE rechazar el registro sin crear datos parciales y mostrar un mensaje que indique la causa y la acción sugerida.
- **FR-010**: El identificador del equipo de origen NO DEBE exponer datos personales ni secretos; debe ser estable para un mismo equipo.
- **FR-011**: Los mensajes de error NO DEBEN exponer rutas completas de otros equipos, credenciales ni la cadena de conexión.

**Configuración espacial versionada (US #54)**

- **FR-012**: El sistema DEBE permitir guardar una configuración espacial para una cámara, compuesta por uno o más locales identificados manualmente.
- **FR-013**: Cada local DEBE tener un nombre, una zona frontal y exactamente una línea de entrada; la zona interior y la zona de vidriera son opcionales (a lo sumo una de cada rol por local).
- **FR-014**: Cada línea de entrada DEBE definir un segmento con inicio y fin, sus lados A y B según la convención del experimento 001 (A a la derecha del vector inicio→fin, B a la izquierda), y qué sentido (A→B o B→A) corresponde a entrada; el opuesto corresponde a salida.
- **FR-015**: Todas las coordenadas DEBEN almacenarse normalizadas en [0, 1] respecto del ancho y alto del frame de referencia sobre el que se dibujaron, y la versión DEBE registrar la resolución de ese frame.
- **FR-016**: El sistema DEBE rechazar polígonos con menos de 3 vértices, con aristas que se autointersectan, con área nula o con vértices fuera de [0, 1], y líneas de longitud cero.
- **FR-017**: El sistema DEBE rechazar configuraciones con nombres de local repetidos dentro de la misma versión, sin ningún local o con algún local sin zona frontal o sin línea de entrada.
- **FR-018**: Al rechazar una configuración, el sistema DEBE informar qué local, qué elemento y qué regla fallaron.
- **FR-019**: Cada configuración guardada DEBE ser una versión inmutable, con número secuencial por cámara, fecha de creación y la sesión cuyo frame de referencia se usó.
- **FR-020**: El sistema NO DEBE permitir editar ni borrar una versión guardada; toda modificación crea una versión nueva.
- **FR-021**: El sistema DEBE permitir consultar la última versión y cualquier versión anterior de una cámara.
- **FR-022**: El sistema DEBE rechazar el inicio de un análisis de una sesión de video si su cámara no tiene una versión de configuración válida.
- **FR-023**: Cada trabajo de análisis de una sesión de video DEBE registrar la versión de configuración que usa; esa asociación no cambia aunque luego se creen versiones más nuevas.
- **FR-024**: Las versiones, locales, zonas y líneas DEBEN quedar asociados a su cámara y a su sesión de referencia de forma que no puedan mezclarse datos de otra sesión (patrón de integridad de specs/002).

**Editor visual (US #55)**

- **FR-025**: El sistema DEBE ofrecer un editor que muestre el frame de referencia de una sesión y dibuje encima la última versión de configuración de su cámara, si existe.
- **FR-026**: El editor DEBE permitir crear, mover vértices y eliminar polígonos y líneas, asignarlos a un local y a un rol, y crear, renombrar y eliminar locales.
- **FR-027**: El editor DEBE permitir elegir el sentido de entrada de cada línea y mostrar visualmente los lados A/B y la dirección de entrada.
- **FR-028**: El editor DEBE mantener la correspondencia entre lo que se ve y las coordenadas normalizadas al redimensionar la vista; redimensionar no DEBE alterar las coordenadas guardadas.
- **FR-029**: Guardar desde el editor DEBE crear una versión nueva usando las mismas reglas de validación que FR-016 a FR-018, y mostrar los errores sobre los elementos afectados sin descartar el dibujo.
- **FR-030**: El editor DEBE advertir antes de salir si hay cambios sin guardar.
- **FR-031**: El editor DEBE ser operable con controles nativos y etiquetas accesibles para las acciones principales (crear, eliminar, elegir rol, elegir sentido, guardar).

### Key Entities *(include if feature involves data)*

- **Session (extendida)**: Sesión de análisis. Ahora puede ser de origen `synthetic` (specs/002) o `video_file`. Para `video_file` agrega los metadatos del video, la ubicación del archivo, el equipo de origen, el hash y el frame de referencia.
- **Frame de referencia**: Imagen fija de un video con su índice de frame, su timestamp del video y su resolución. Sirve de lienzo para dibujar la configuración.
- **Configuración espacial (versión)**: Versión inmutable y numerada de la escena de una cámara. Registra la sesión de referencia, la resolución del frame usado y la fecha. Contiene uno o más locales.
- **Local**: Comercio identificado manualmente dentro de una versión. Tiene nombre, zona frontal, una línea de entrada y, opcionalmente, zona interior y zona de vidriera.
- **Zona**: Polígono normalizado con un rol (interior, frontal o vidriera) que pertenece a un local.
- **Línea de entrada**: Segmento normalizado con lados A/B y el sentido que cuenta como entrada, que pertenece a un local.
- **ProcessingJob (extendido)**: Trabajo de specs/002. Para sesiones de video referencia la versión de configuración usada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un operador registra un video local de hasta 5 minutos y ve sus metadatos y el frame de referencia en menos de 30 segundos en la PC de desarrollo.
- **SC-002**: El 100 % de los archivos del conjunto de prueba de errores (inexistente, vacío, corrupto, formato no soportado) se rechazan sin crear sesión y con un mensaje que nombra la causa.
- **SC-003**: Un operador sin experiencia previa configura un local con zona frontal, zona interior, zona de vidriera y una línea con sentido de entrada con el editor en menos de 5 minutos, sin editar archivos.
- **SC-004**: Tras redimensionar la vista a al menos tres tamaños distintos, las coordenadas guardadas difieren en menos de 0,5 % del ancho o alto del frame respecto de las dibujadas.
- **SC-005**: El 100 % de las configuraciones inválidas del conjunto de prueba (menos de 3 vértices, autointersección, área nula, línea de longitud cero, fuera de rango) se rechazan indicando el elemento y la regla.
- **SC-006**: Ninguna versión guardada cambia su contenido después de creada; el 100 % de los trabajos de análisis de sesiones de video referencian una versión existente.
- **SC-007**: Un integrante que abre desde otro equipo una sesión registrada en la base compartida ve correctamente si el video está disponible en su equipo, sin errores genéricos.
- **SC-008**: Ninguna consulta de configuración devuelve datos de una cámara o sesión distinta a la pedida (verificado con datos de al menos dos sesiones y dos cámaras).

## Assumptions

- **Alcance**: Solo la Feature #12. No incluye procesamiento real con YOLO/ByteTrack (#56, Feature #13), cálculo de eventos ni métricas (#14), dashboard (#15) ni chat (#16). Esta feature deja listas la compuerta "sin configuración no hay análisis" y la asociación trabajo → versión; el tipo de trabajo que procesa video real llega con #56.
- **Persistencia**: Se usa la misma base relacional de specs/002, seleccionada solo por configuración (local o compartida en Azure). Los cambios de esquema se aplican con migraciones versionadas que extienden el data-model de specs/002, sin romper las sesiones y trabajos sintéticos existentes.
- **Videos en disco local**: El video nunca se sube a la nube ni a la base. El frame de referencia es una imagen pequeña y se conserva de forma que la configuración se pueda ver y editar desde cualquier equipo conectado a la base compartida, aunque el video no esté en ese equipo.
- **Configuración por cámara**: La configuración se versiona por identificador de cámara, porque una cámara fija conserva la misma escena entre videos. Cada versión recuerda sobre qué sesión se dibujó.
- **Zona interior opcional**: El experimento 001 concluyó que la permanencia interior continua y la ocupación total del local no son viables con el material evaluado, y muchas cámaras de pasillo no ven el interior. Por eso la zona interior es opcional; solo la zona frontal y la línea de entrada son obligatorias.
- **Convención A/B**: Se adopta la del experimento 001 (`scene.example.json`): lado A a la derecha del vector inicio→fin, lado B a la izquierda, y el cruce se evalúa contra el segmento, no contra la recta infinita.
- **Formatos soportados**: Los que el componente de lectura de video ya aprobado decodifique en la PC de referencia; como mínimo MPEG (material del experimento 001) y MP4.
- **Usuarios**: Un único rol, operador. No hay autenticación ni permisos por usuario en el MVP (entorno local o base compartida del equipo).
- **Identificador del equipo**: Un valor estable por equipo que no revela el nombre de usuario; se define en el plan (p. ej. configurable por variable de entorno).
- **Frame de referencia**: En el MVP es el primer frame decodificable; elegir otro frame queda como mejora posible.
- **Referencia de UI**: El editor de canvas de ProyectoShopping sirve de referencia de interacción; la tecnología del editor se fija en el plan según el stack acordado.
