# Feature Specification: Validación del servicio de modelo de Azure

**Feature Branch**: `003-validacion-modelo-azure`

**Azure Boards**: Feature #5, hija del Epic #2 `Validación técnica y entorno reproducible`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: Validar que el proyecto pueda consumir un modelo generativo mediante Azure (acceso, servicio, modelo, región, deployment, autenticación, llamada simple y tool calling con herramienta ficticia) para el futuro asistente analítico del MVP, sin implementar el chat del producto ni integrar métricas reales.

## Clarifications

### Session 2026-09-25

- Q: ¿La herramienta de prueba debe usar métricas reales de FlowSight? → A: No. Usar una herramienta ficticia `get_session_traffic(session_id)` con datos hardcodeados solo para validar el ciclo modelo → herramienta → backend → modelo → respuesta.
- Q: ¿Qué queda fuera de esta Feature? → A: Chat del producto, dashboard, métricas reales, integración con PostgreSQL para analytics, procesamiento de video y el agente completo de la Feature #16. Tampoco se cambia PostgreSQL local por una base compartida en Azure.
- Q: ¿Dónde viven las credenciales? → A: Solo en variables de entorno / `.env` local. El repositorio versiona nombres de variables de ejemplo, nunca secretos ni endpoints con claves.
- Q: ¿Se fija ya el servicio (Foundry vs Azure OpenAI) y el modelo? → A: El servicio es **Azure AI Foundry** (suscripción de estudiantes, ~100 USD). Se usa el **modelo/deployment habilitado** por el proyecto Foundry del equipo (evidencia: **`gpt-5-mini`**). Región, cuotas y tool calling se confirman en inventario/evidencia. SDK fijado tras validación: `openai` OpenAI-compatible.
- Q: ¿La validación debe ser repetible por otro integrante? → A: Sí. Debe quedar una guía y un resumen de evidencia anonimizado (sin secretos) que permita repetir la prueba con la misma cuenta o documentar bloqueos explícitos.
- Q: ¿Por qué Azure AI Foundry y no otro mecanismo? → A: El equipo dispone de suscripción de estudiantes con crédito (~100 USD) orientada a Foundry; no se evaluarán alternativas de servicio salvo bloqueo documentado de Foundry.
- Q: ¿Cómo debe autenticarse el backend contra Azure AI Foundry en esta validación? → A: API key (o clave de proyecto/recurso Foundry) solo en `.env` local.
- Q: ¿Cómo deben poder repetir la validación los demás integrantes del grupo? → A: Proyecto Foundry compartido del equipo; cada integrante con su `.env` local (clave repartida fuera de Git).
- Q: ¿Cómo se debe ejecutar esta validación desde el producto (sin ser el chat del MVP)? → A: Solo script/comando local de validación; sin endpoint HTTP de chat.
- Q: ¿Hay un tope de gasto o de corridas sobre el crédito de estudiantes (~100 USD)? → A: Solo las corridas mínimas necesarias para la evidencia (inventario + llamada simple + ciclo de tools); registrar consumo si es visible; sin tope fijo en USD.
- Q: Si en Foundry hay varios deployments/modelos, ¿con qué criterio se elige el candidato? → A: Usar el **modelo habilitado** por el equipo/proyecto Foundry. Si hay varios, preferir el de menor costo aparente que permita la validación y, si hace falta tools, priorizar tool calling. Documentar el nombre exacto (p. ej. `gpt-5-mini`).
- Q: Análisis post-tasks (2026-09-25): estados de tool calling → A: Usar en spec/plan/tasks/evidencia solo `demonstrated`, `not_supported` o `not_evaluated` (no “no viable” / “no evaluable” sueltos).
- Q: Análisis post-implement (2026-09-26): ¿“modelo antiguo” vs gpt-5-mini? → A: La restricción “solo modelos antiguos / modernos bloqueados” quedó **obsoleta**. Criterio vigente: modelo **habilitado** en Foundry; evidencia con `gpt-5-mini` y región `brazilsouth`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Comprobar acceso a Foundry y seleccionar deployment/modelo (Priority: P1)

Como integrante del Grupo 6, quiero verificar que la suscripción de estudiantes permite usar **Azure AI Foundry** y registrar región, deployment y modelo disponibles, para decidir con evidencia qué usará el chat mínimo del MVP.

**Why this priority**: Sin acceso comprobado a Foundry y sin deployment/modelo documentados, no se puede fijar autenticación, endpoint ni dependencias.

**Independent Test**: Se puede revisar un registro de inventario/acceso que indique Foundry usable o bloqueo explícito, región, deployment, modelo y autenticación por API key, sin ejecutar todavía tool calling.

**Acceptance Scenarios**:

1. **Given** hay credenciales o acceso a la suscripción de estudiantes configurados localmente, **When** se consulta Azure AI Foundry, **Then** se registra si los créditos (~100 USD) y permisos permiten operar o el motivo concreto del bloqueo, sin exponer secretos.
2. **Given** Foundry es accesible, **When** se completa el inventario, **Then** quedan documentados región, deployment y un modelo **habilitado** por el proyecto Foundry, con justificación de la elección.
3. **Given** hay varios modelos habilitados, **When** se elige el candidato, **Then** se documenta el motivo (costo aparente y, si aplica, soporte de tool calling) y el nombre exacto del deployment.
4. **Given** no hay acceso, faltan permisos o se agotaron/bloquean los créditos de Foundry, **When** se intenta la verificación, **Then** el resultado se marca como `blocked` o `not_evaluated` con causa accionable, y no se inventa un modelo ni un SDK definitivo.

---

### User Story 2 - Ejecutar una llamada simple al modelo desde el backend (Priority: P1)

Como desarrollador, quiero invocar el modelo desde código del backend con la configuración local para confirmar autenticación, endpoint y una respuesta mínima utilizable.

**Why this priority**: Demuestra el camino de red y autenticación que usará el asistente analítico, sin construir la UI de chat.

**Independent Test**: Un script o comando local con configuración en `.env` obtiene una respuesta textual del modelo o un error diagnóstico seguro; la prueba no requiere PostgreSQL, frontend ni un endpoint HTTP de chat.

**Acceptance Scenarios**:

1. **Given** la configuración de endpoint y autenticación es válida, **When** se envía una consulta mínima, **Then** el backend recibe una respuesta del modelo y registra el resultado sin guardar secretos en logs ni archivos versionados.
2. **Given** falta una variable obligatoria o la autenticación es inválida, **When** se ejecuta la llamada, **Then** el proceso falla antes o durante la llamada con un mensaje accionable que no revela secretos.
3. **Given** la llamada finaliza, **When** se revisa la evidencia, **Then** quedan registrados servicio, región, deployment, modelo y resultado (éxito o fallo) de forma anonimizable.

---

### User Story 3 - Validar tool calling con una herramienta ficticia (Priority: P1)

Como desarrollador, quiero comprobar que el modelo puede solicitar una herramienta, que el backend la ejecuta y que el modelo redacta una respuesta a partir del resultado, para validar el patrón del futuro chat analítico.

**Why this priority**: El MVP exige que el modelo no calcule métricas por sí mismo y use herramientas acotadas; esta prueba demuestra ese ciclo con datos ficticios.

**Independent Test**: Se ejecuta un flujo vía script/comando local con la herramienta `get_session_traffic(session_id)` hardcodeada y se observa la secuencia usuario → modelo → tool → backend → modelo → respuesta, sin consultar PostgreSQL ni métricas reales.

**Acceptance Scenarios**:

1. **Given** el modelo soporta tool/function calling con la herramienta ficticia registrada, **When** el usuario pide el tráfico de una sesión de ejemplo, **Then** el modelo solicita `get_session_traffic`, el backend devuelve datos hardcodeados y el modelo produce una respuesta basada en ese resultado.
2. **Given** el modelo o el deployment no soporta tool calling, **When** se intenta la prueba, **Then** el informe registra `tool_calling_status=not_supported` (o `not_evaluated` si hubo bloqueo previo), sin implementar un framework de agentes.
3. **Given** la herramienta recibe un `session_id` desconocido para la muestra ficticia, **When** se ejecuta, **Then** responde de forma controlada (por ejemplo, sin datos) y el modelo puede indicar la falta de información.

---

### User Story 4 - Documentar cuotas, configuración y evidencia reproducible (Priority: P2)

Como responsable de la planificación, quiero un paquete de evidencia y una guía de configuración por variables de entorno para que otro integrante pueda repetir la validación y para respaldar la presentación del TP.

**Why this priority**: Cierra la Feature con trazabilidad y evita secretos en el repositorio; depende de haber intentado las pruebas anteriores.

**Independent Test**: Otro integrante puede seguir la guía con `.env.example`, configurar el proyecto Foundry compartido en su `.env` local, ejecutar el mismo procedimiento y obtener el mismo tipo de resultado o un bloqueo documentado.

**Acceptance Scenarios**:

1. **Given** se completaron o intentaron las pruebas de acceso, llamada y tool calling con corridas mínimas, **When** se redacta la evidencia, **Then** incluye cuotas/límites/costos relevantes conocidos o declara explícitamente qué no pudo medirse, y no describe baterías exploratorias como parte del procedimiento.
2. **Given** la configuración requerida, **When** se revisa el repositorio, **Then** existen nombres de variables de entorno de ejemplo y ninguna credencial, clave ni archivo `.env` real versionado.
3. **Given** un integrante distinto sigue la guía y configura su `.env` local contra el proyecto Foundry compartido del equipo, **When** ejecuta la validación, **Then** puede repetir el flujo o registrar un bloqueo reproducible sin inventar resultados y sin que la clave hubiese estado en el repositorio.

### Edge Cases

- La cuenta puede existir pero sin créditos, cuota o permisos al modelo; el informe debe distinguir esos casos.
- Si Foundry no admite API key en el recurso usado, el informe registra el bloqueo; no se implementa Entra ID en esta Feature.
- Si el modelo habilitado no admite tools, se documenta `not_supported` y el impacto en la prueba de tool calling.
- La evidencia nombra el modelo realmente elegido (p. ej. `gpt-5-mini`) y la región cuando se conoce (p. ej. `brazilsouth`); si la región no se midió, se declara explícitamente.
- La red puede fallar o la región puede no estar autorizada; el error debe ser seguro y accionable.
- Variables parciales (endpoint sin clave, o a la inversa) deben detectarse antes de enviar peticiones inútiles.
- La herramienta ficticia no debe confundirse con una API de analytics del producto ni persistirse en PostgreSQL.
- El crédito compartido (~100 USD) no autoriza pruebas exploratorias masivas; solo corridas mínimas de evidencia.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El equipo DEBE comprobar si la suscripción de estudiantes / créditos (~100 USD) permiten utilizar **Azure AI Foundry** y registrar el resultado o el bloqueo.
- **FR-002**: La validación DEBE utilizar **Azure AI Foundry** como servicio e identificar la región (o declarar `not_measured`), el deployment y un **modelo habilitado** por el proyecto Foundry del equipo. El nombre exacto DEBE documentarse en la evidencia con el motivo de elección.
- **FR-003**: El backend DEBE autenticarse contra Azure AI Foundry mediante **API key** (o clave de proyecto/recurso) cargada solo desde variables de entorno / `.env` local, sin secretos en el repositorio ni autenticación Entra ID en esta Feature.
- **FR-004**: El proyecto DEBE ejecutar al menos una llamada simple al modelo desde código de backend invocado por un **script/comando local de validación**, y registrar éxito o fallo diagnóstico. NO DEBE exponer un endpoint HTTP de chat en esta Feature.
- **FR-016**: La interfaz de esta Feature DEBE limitarse al script/comando de validación y a la evidencia documentada; cualquier UI o API de chat pertenece a la Feature #16.
- **FR-005**: La validación DEBE determinar si el modelo/deployment soporta tool/function calling.
- **FR-006**: Si hay soporte de tools, el proyecto DEBE ejecutar un ciclo mínimo con la herramienta ficticia `get_session_traffic(session_id)` y datos hardcodeados.
- **FR-007**: La herramienta ficticia NO DEBE consultar PostgreSQL, métricas reales, videos ni el dashboard.
- **FR-008**: El modelo NO DEBE calcular métricas por sí mismo en esta prueba; DEBE basar la respuesta en el resultado de la herramienta cuando el ciclo de tools se ejecute.
- **FR-009**: La validación DEBE documentar cuotas, límites y costos relevantes conocidos para el TP, o declarar qué no fue medible. DEBE limitarse a las **corridas mínimas** de evidencia (inventario, una llamada simple y un ciclo de tool calling cuando aplique) y registrar el consumo observado si el portal o la API lo exponen.
- **FR-010**: El repositorio DEBE versionar solo nombres/descripciones de variables de entorno de ejemplo; `.env`, claves y tokens permanecen locales.
- **FR-011**: DEBE existir evidencia reproducible (guía + resumen anonimizado) para que otro integrante, usando el **proyecto Foundry compartido** y su propio `.env` local, repita la prueba. La API key se reparte fuera de Git.
- **FR-012**: Esta Feature NO DEBE implementar el chat del producto, el dashboard, métricas reales, procesamiento de video, el agente completo de la Feature #16 ni un endpoint HTTP de chat.
- **FR-013**: Esta Feature NO DEBE modificar el alcance ni la evidencia de las Features #4 y #6, ni adoptar PostgreSQL compartido en Azure.
- **FR-014**: Las verificaciones ordinarias de CI DEBEN poder ejecutarse sin credenciales de Azure; las llamadas reales al modelo se ejecutan en entorno local documentado.
- **FR-015**: Los fallos y logs DEBEN evitar imprimir secretos, tokens o cabeceras de autenticación.

### Key Entities

- **Inventario de acceso Azure**: resultado de comprobar cuenta, créditos/permisos, servicio, región, deployment, modelo y autenticación.
- **Configuración de modelo**: variables de entorno necesarias (endpoint, API key, deployment/modelo, región si aplica).
- **Prueba de llamada simple**: registro de una invocación mínima y su resultado.
- **Herramienta ficticia**: `get_session_traffic(session_id)` con respuesta hardcodeada para validar tool calling.
- **Ciclo de tool calling**: traza de solicitud de herramienta, ejecución local y respuesta final del modelo.
- **Evidencia de validación**: resumen anonimizado con hallazgos, limitaciones, cuotas/costos conocidos y pasos de reproducción.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Existe un registro que declara, para la cuenta usada, si el acceso fue posible o el bloqueo concreto (créditos, permisos, región u otro).
- **SC-002**: Quedan identificados servicio (Foundry), región (valor o `not_measured` justificado), deployment y modelo usado (habilitado en Foundry, con justificación), o una justificación explícita de imposibilidad.
- **SC-003**: Una llamada simple desde el backend completa con **texto no vacío** del modelo o con error diagnóstico seguro (`empty_response` incluido) en no más de 5 minutos de operación una vez configurado el entorno; la evidencia registra `latency_ms` o declara por qué no se midió.
- **SC-004**: El informe distingue soporte de tool calling con exactamente uno de: `demonstrated`, `not_supported`, `not_evaluated`.
- **SC-005**: Cuando el tool calling se demuestra, la evidencia muestra al menos una ejecución de `get_session_traffic` y una respuesta final que utiliza ese resultado.
- **SC-006**: `.env.example` (o equivalente versionado) lista las variables necesarias y el repositorio no contiene secretos de Azure.
- **SC-007**: Otro integrante puede seguir la guía, configurar su `.env` contra el proyecto Foundry compartido y obtener un resultado del mismo tipo (éxito comparable o bloqueo documentado) sin asistencia ad hoc no escrita y sin secretos en el repo.
- **SC-008**: Ningún artefacto versionado de esta Feature implementa chat de producto, dashboard, endpoint HTTP de chat, SQL de métricas reales ni cambio a PostgreSQL compartido.
- **SC-009**: La validación operativa se ejecuta mediante script/comando local documentado en la guía; no requiere levantar una UI de chat.
- **SC-010**: La evidencia indica que las pruebas reales contra Foundry se limitaron a las corridas mínimas acordadas, o justifica cualquier corrida extra; si el consumo no fue visible, queda `not_measured`.

## Assumptions

- El equipo dispone de suscripción de estudiantes de Azure con crédito (~100 USD) y un **proyecto/recurso Foundry compartido**; cada integrante usa `.env` local.
- La API key del recurso compartido se distribuye por un canal seguro fuera de Git; nunca se versiona.
- La validación se ejecuta desde el entorno local Windows del integrante, con red hacia Azure.
- PostgreSQL local del producto puede existir en la máquina, pero esta Feature no depende de él para la prueba del modelo.
- La autenticación de esta validación es por API key en `.env`; Entra ID queda fuera de alcance salvo bloqueo documentado que impida usar clave.
- El modelo candidato es el **habilitado** en Foundry del equipo (evidencia: `gpt-5-mini`); región, deployment y soporte de tools se confirman en la evidencia.
- El SDK o cliente HTTP concreto se elige después de inventariar deployments/modelos en Foundry; no se fija en la especificación.
- Esta Feature no agrega endpoint HTTP de chat; la ejecución es por script/comando local sobre el módulo de backend.
- Las corridas reales contra Foundry se limitan a lo mínimo para cerrar la evidencia; no hay tope fijo en USD, pero sí obligación de no hacer baterías exploratorias costosas.
