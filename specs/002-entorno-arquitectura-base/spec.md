# Feature Specification: Entorno local reproducible y arquitectura base

**Feature Branch**: `feature/entorno-arquitectura-base`

**Azure Boards**: Feature #6, hija del Epic #2 `Validación técnica y entorno reproducible`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: Especificar una base local reproducible para FlowSight que permita iniciar sus componentes, persistir sesiones y trabajos, procesar datos sintéticos con aislamiento y validar la previsualización y la compatibilidad en CPU y en la PC de referencia.

## Clarifications

### Session 2026-09-15

- Q: Si el worker se detiene mientras procesa un trabajo, ¿en qué estado debe quedar ese trabajo cuando el entorno vuelve a iniciarse? → A: Marcarlo como fallido al recuperar el entorno, indicando que la ejecución fue interrumpida.
- Q: Cuando un cliente de previsualización es más lento que el procesamiento, ¿qué actualizaciones debe recibir? → A: Reemplazar la actualización pendiente y entregar siempre la más reciente.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducir el entorno local (Priority: P1)

Como integrante del Grupo 6, quiero preparar y verificar el entorno desde un repositorio recién clonado para poder desarrollar FlowSight sin depender de la configuración privada de otra persona.

**Why this priority**: Las demás funcionalidades necesitan una base común que los integrantes puedan iniciar y diagnosticar.

**Independent Test**: Un integrante puede seguir las instrucciones desde un clon limpio, configurar valores locales de ejemplo, iniciar los componentes base y obtener una verificación satisfactoria sin usar videos, pesos ni credenciales reales.

**Acceptance Scenarios**:

1. **Given** un equipo compatible y un clon limpio, **When** el integrante sigue la guía de preparación, **Then** obtiene una configuración local válida y puede verificar que los componentes base están disponibles.
2. **Given** falta una dependencia o configuración obligatoria, **When** se ejecuta la verificación inicial, **Then** se identifica el requisito faltante con una indicación accionable y sin exponer secretos.
3. **Given** dos integrantes preparan el entorno en equipos distintos, **When** ejecutan la misma verificación, **Then** ambos obtienen los mismos componentes y contratos básicos a partir de los artefactos versionados.

---

### User Story 2 - Persistir sesiones y trabajos sintéticos (Priority: P1)

Como desarrollador, quiero crear una sesión y ejecutar un trabajo sintético con estados persistidos para comprobar el flujo base antes de integrar el procesamiento real de videos.

**Why this priority**: Las sesiones y los trabajos son la unidad de aislamiento y coordinación del procesamiento futuro.

**Independent Test**: Se crea una sesión con un trabajo sintético, se observan sus cambios de estado hasta completar o fallar y se comprueba que esos datos permanecen disponibles después de reiniciar los componentes.

**Acceptance Scenarios**:

1. **Given** un almacenamiento local inicializado, **When** se crea una sesión con un trabajo sintético, **Then** ambos reciben identificadores distintos y el trabajo comienza en estado pendiente.
2. **Given** un trabajo pendiente, **When** el proceso encargado lo toma y finaliza correctamente, **Then** quedan registrados los estados pendiente, procesando y completado con sus momentos correspondientes.
3. **Given** un trabajo encuentra un error controlado, **When** finaliza la ejecución, **Then** queda en estado fallido con una explicación diagnóstica que no contiene secretos.
4. **Given** existen sesiones y trabajos persistidos, **When** se reinicia el entorno, **Then** pueden volver a consultarse sin recrearlos.
5. **Given** el worker se detuvo mientras procesaba un trabajo, **When** se recupera el entorno, **Then** el trabajo pasa a fallido y conserva como motivo que la ejecución fue interrumpida.

---

### User Story 3 - Mantener trazabilidad y aislamiento por sesión (Priority: P1)

Como integrante del equipo, quiero relacionar datos sintéticos de procesamiento con su sesión, cámara, frame y timestamp para comprobar que las futuras métricas no mezclen videos ni sesiones.

**Why this priority**: La trazabilidad temporal y el aislamiento son restricciones constitucionales y condicionan toda la analítica posterior.

**Independent Test**: Se procesan dos sesiones sintéticas que reutilizan identificadores internos y se verifica que sus frames, observaciones y eventos continúan separados y trazables.

**Acceptance Scenarios**:

1. **Given** dos sesiones con datos sintéticos, **When** ambas usan el mismo identificador temporal de seguimiento, **Then** sus observaciones y eventos permanecen asociados a la sesión y cámara correctas.
2. **Given** una observación o evento sintético, **When** se consulta su trazabilidad, **Then** se puede llegar a la sesión, cámara, frame y timestamp del video que lo originaron.
3. **Given** se registran tiempos de procesamiento y timestamps del video, **When** se consultan, **Then** se presentan como conceptos distintos y no se usa el tiempo operativo para representar comportamiento observado.

---

### User Story 4 - Previsualizar sin bloquear el trabajo (Priority: P2)

Como usuario que supervisa un trabajo, quiero recibir una previsualización del avance sin que una conexión lenta o interrumpida detenga el procesamiento.

**Why this priority**: La previsualización será necesaria para observar el proceso, pero no puede controlar la velocidad ni la finalización del trabajo.

**Independent Test**: Un trabajo sintético produce actualizaciones de previsualización mientras un cliente normal, uno lento y uno que se desconecta observan el flujo; el trabajo alcanza igualmente un estado terminal.

**Acceptance Scenarios**:

1. **Given** un trabajo en procesamiento y un cliente conectado, **When** hay una nueva actualización disponible, **Then** el cliente recibe el identificador de sesión, trabajo, frame y timestamp correspondientes.
2. **Given** un cliente consume actualizaciones más lentamente que el productor, **When** existe una actualización pendiente y se produce otra, **Then** la nueva reemplaza a la anterior, el cliente recibe luego la más reciente y el trabajo continúa.
3. **Given** el cliente se desconecta, **When** el trabajo continúa, **Then** la desconexión no cambia por sí sola el estado del trabajo ni impide su finalización.

---

### User Story 5 - Validar equipos de referencia (Priority: P2)

Como responsable de la planificación, quiero registrar la ejecución de la base en CPU y en la PC de referencia con GPU para saber qué configuraciones puede reproducir el equipo y qué limitaciones deben conservarse.

**Why this priority**: FlowSight debe funcionar sin asumir una GPU específica y, a la vez, documentar la evidencia disponible para el equipo de mayor capacidad.

**Independent Test**: Se ejecuta el mismo flujo sintético y las verificaciones base en un equipo CPU y en la PC de referencia, registrando ambiente, resultado y limitaciones sin prometer rendimiento de video en tiempo real.

**Acceptance Scenarios**:

1. **Given** un equipo sin GPU compatible, **When** ejecuta el flujo sintético, **Then** completa la verificación base en CPU sin requerir aceleración.
2. **Given** está disponible la PC de referencia, **When** se ejecuta la misma verificación, **Then** se registra el resultado y la capacidad de aceleración detectada por separado.
3. **Given** una de las configuraciones no puede evaluarse, **When** se informa el resultado, **Then** se declara como no evaluada o limitada y no se extrapolan tiempos ni capacidades.

### Edge Cases

- Una configuración local puede contener una variable faltante, vacía o inválida; la verificación debe fallar antes de iniciar trabajos.
- El almacenamiento puede estar vacío, desactualizado o no disponible; la preparación debe distinguir cada caso y no borrar datos para recuperarse.
- Un proceso puede detenerse mientras un trabajo está en curso; al reiniciar, el trabajo debe pasar a fallido con un motivo de interrupción y no debe reintentarse automáticamente.
- Dos sesiones pueden reutilizar el mismo identificador de cámara, frame o track; la combinación completa de contexto debe mantenerlas separadas.
- Un timestamp puede ser nulo, negativo o no monótono; esos datos deben rechazarse o marcarse como inválidos.
- Un cliente de previsualización puede conectarse tarde, consumir lentamente o desconectarse sin aviso; cada cliente conserva como máximo una actualización pendiente y la reemplaza por la más reciente sin bloquear al productor.
- Un cliente puede conectarse o reconectarse cuando el trabajo ya terminó; debe consultar el estado persistido y no se reconstruyen previsualizaciones descartadas.
- Una migración puede fallar antes de completarse; la preparación debe detenerse, conservar la revisión y los datos previos y comunicar la revisión actual y la acción manual necesaria, sin borrar ni degradar el esquema automáticamente.
- La PC con GPU puede no estar disponible o tener una configuración incompatible; la ejecución CPU continúa siendo obligatoria y la limitación GPU se documenta.
- Una segunda ejecución de la preparación o de las migraciones no debe duplicar datos sintéticos ni dejar el entorno en un estado inconsistente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El proyecto DEBE proporcionar instrucciones versionadas para preparar, iniciar, verificar y detener el entorno local desde un clon limpio.
- **FR-002**: El entorno DEBE utilizar configuración local basada en ejemplos versionados, sin incluir credenciales, videos, pesos, bases locales ni resultados privados.
- **FR-003**: La preparación DEBE validar los requisitos obligatorios y devolver mensajes accionables cuando falte una dependencia o configuración.
- **FR-004**: El equipo DEBE poder inicializar y actualizar el esquema de almacenamiento local mediante cambios versionados y repetibles, sin depender de una base preexistente de otro integrante.
- **FR-005**: El proyecto DEBE incluir datos sintéticos mínimos, deterministas y seguros para verificar el flujo sin videos reales.
- **FR-006**: El sistema DEBE persistir sesiones y trabajos con identificadores propios y, como mínimo, los estados pendiente, procesando, completado y fallido.
- **FR-007**: Cada cambio de estado DEBE conservar el momento correspondiente y los fallos DEBEN incluir información diagnóstica sin secretos.
- **FR-008**: Tras reiniciar el entorno, las sesiones y los trabajos persistidos DEBEN poder consultarse; todo trabajo que hubiera quedado procesando DEBE pasar a fallido con un motivo de interrupción y NO DEBE reintentarse automáticamente.
- **FR-009**: Los datos de procesamiento sintéticos DEBEN mantener aislamiento por sesión y cámara aunque se reutilicen identificadores temporales en sesiones diferentes.
- **FR-010**: Cada observación y evento sintético DEBE poder relacionarse con su sesión, cámara, frame y timestamp del video.
- **FR-011**: El sistema DEBE distinguir timestamps del video, momentos de cambios de estado y duración operativa del procesamiento.
- **FR-012**: La ejecución base DEBE procesar los trabajos pendientes de a uno y evitar que dos procesos reclamen simultáneamente el mismo trabajo.
- **FR-013**: La previsualización DEBE identificar la sesión, el trabajo, el frame y el timestamp de cada actualización entregada.
- **FR-014**: Un cliente de previsualización lento o desconectado NO DEBE bloquear el procesamiento; cada cliente DEBE conservar como máximo una actualización pendiente y reemplazarla por la más reciente cuando llegue una nueva.
- **FR-015**: El flujo sintético y las verificaciones base DEBEN poder ejecutarse en CPU sin requerir una GPU específica.
- **FR-016**: La validación DEBE registrar por separado el ambiente y el resultado obtenidos en el equipo CPU y en la PC de referencia con GPU, sin extrapolar capacidades no medidas.
- **FR-017**: El proyecto DEBE ofrecer verificaciones automáticas repetibles sobre configuración, persistencia, estados, aislamiento, trazabilidad y previsualización que no dependan de archivos locales excluidos.
- **FR-018**: Esta Feature NO DEBE implementar el editor visual, dashboard, chat, métricas comerciales finales ni procesamiento completo con el modelo de visión.
- **FR-019**: Si una migración falla, la preparación DEBE detenerse sin borrar datos ni ejecutar una migración descendente automática, informar la revisión actual y permitir reanudar solo después de corregir la causa.
- **FR-020**: La previsualización sintética DEBE utilizar JPEG de 320×180, con un máximo de 100 KiB por actualización y una frecuencia máxima configurable cuyo valor de ejemplo sea 5 actualizaciones por segundo.
- **FR-021**: Los informes completos de ambiente DEBEN permanecer locales y excluidos de Git; solo se podrá versionar un resumen sin nombre de equipo, usuario, rutas absolutas, direcciones de red ni secretos.
- **FR-022**: La preparación DEBE documentar el orden PostgreSQL, API, worker y frontend; API y worker DEBEN fallar antes de operar si PostgreSQL o la configuración obligatoria no están disponibles, y el frontend DEBE informar que la API no está disponible.

### Key Entities

- **Entorno local**: configuración reproducible de un integrante, con los requisitos y resultados de verificación correspondientes.
- **Sesión**: unidad aislada de análisis asociada a una cámara o fuente y contenedora de trabajos y resultados.
- **Trabajo**: solicitud persistida que atraviesa estados controlados y registra momentos, resultado o fallo.
- **Frame sintético**: unidad de entrada de prueba identificada por sesión, cámara, índice y timestamp del video.
- **Observación sintética**: dato temporal asociado a un frame y limitado al contexto de su sesión y cámara.
- **Evento sintético**: resultado derivado de observaciones, trazable al frame y timestamp que lo originan.
- **Actualización de previsualización**: representación descartable del avance de un trabajo; su consumo no condiciona el resultado persistido.
- **Evidencia de ambiente**: registro de equipo, capacidad detectada, verificaciones ejecutadas, resultado y limitaciones.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un integrante puede pasar de un clon limpio a una verificación satisfactoria del entorno en 30 minutos o menos, excluyendo el tiempo de descarga de herramientas externas.
- **SC-002**: El 100% de los requisitos obligatorios faltantes probados produce un mensaje que identifica el elemento y una acción de corrección, sin revelar secretos.
- **SC-003**: La inicialización y dos ejecuciones consecutivas de actualización del almacenamiento terminan sin duplicar datos sintéticos ni requerir borrado manual.
- **SC-004**: Un trabajo sintético exitoso registra, en orden, los estados pendiente, procesando y completado; un trabajo fallido o interrumpido termina en fallido y conserva una explicación.
- **SC-005**: Una prueba con al menos dos sesiones que reutilizan identificadores temporales produce cero observaciones o eventos asociados a la sesión incorrecta.
- **SC-006**: El 100% de las observaciones y eventos sintéticos generados puede rastrearse a sesión, cámara, frame y timestamp del video.
- **SC-007**: Un cliente de previsualización deliberadamente lento conserva como máximo una actualización pendiente y recibe la última actualización publicada antes del estado terminal; un cliente desconectado o reconectado no impide la finalización y obtiene el estado actual mediante REST.
- **SC-008**: Todas las verificaciones automáticas pueden ejecutarse desde un clon limpio utilizando únicamente configuración y datos sintéticos versionados.
- **SC-009**: La validación registra un resultado reproducible en CPU y un resultado o limitación explícita para la PC de referencia con GPU, sin afirmar rendimiento de video no medido.
- **SC-010**: Ninguna credencial, video, peso, base local ni resultado privado aparece entre los archivos versionados de la Feature.
- **SC-011**: Tres ejecuciones consecutivas del fixture base, con PostgreSQL local y un único worker en el mismo equipo CPU registrado, presentan su mediana y cumplen un tiempo total menor a 30 segundos; tres consultas locales consecutivas a `/health` presentan su mediana y cumplen menos de 1 segundo.

## Assumptions

- Los integrantes desarrollan principalmente en Windows y cuentan con permisos para instalar las herramientas acordadas; los contenedores no son un requisito del entorno inicial.
- Todos los componentes se ejecutan localmente durante esta Feature; no se requieren servicios cloud para el flujo sintético.
- La autenticación y los permisos de usuarios finales están fuera de este alcance; la base se usa en un entorno de desarrollo confiable.
- La primera versión utiliza un solo proceso encargado de tomar un trabajo por vez; una cola distribuida queda fuera de alcance.
- Los datos sintéticos validan contratos, persistencia y aislamiento, pero no demuestran precisión ni rendimiento del procesamiento real de videos.
- La ejecución CPU es obligatoria. La PC con RTX 5080 se usa como referencia adicional cuando esté disponible y su ausencia temporal se registra sin convertir la GPU en requisito general.
- La previsualización valida transporte, identificación y comportamiento ante consumidores lentos; no incluye todavía el diseño de la interfaz final.
- La prueba técnica de `specs/001-validacion-videos-tracking/` conserva su propósito experimental y no se convierte automáticamente en la arquitectura definitiva.
