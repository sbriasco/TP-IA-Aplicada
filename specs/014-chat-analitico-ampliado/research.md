# Research: Chat analítico ampliado

## R1 — Mismo `POST /chat`, no un segundo agente

**Decision**: Ampliar el contrato y las herramientas de `POST /chat` y el panel de resultados. No crear `/chat/extended` ni un segundo modo UI.

**Rationale**: Clarify: un solo panel supersede el mínimo. Dos endpoints duplicarían guards y confundirían la demo de materia.

**Alternatives considered**: Endpoint nuevo solo para contraste (fragmenta el agente). Modo «mínimo/ampliado» conmutable (dos contratos).

## R2 — Catálogo cerrado de cifras de una sesión

**Decision**: Una lectura/tool de sesión (evolución de `get_session_figures`) devuelve el catálogo: `traffic_total`, `entries`, `exits`, `store_pass`, `entry_rate`, `visible_occupancy`, `dwell_mean_seconds`, `dwell_median_seconds`, pico, y si existen funnel (`linked_entry` u etapas ya expuestas), `group_count` de patrones y `visit_count` de posible compra — con rótulos y `unavailable` del producto. Tramo de video en la pregunta no cambia el alcance (sigue toda la sesión).

**Rationale**: Align con tablero + 013; supersede el veto de 008 a salidas/pasos/tasa.

**Alternatives considered**: Mantener veto de 008 (chat diría «no puedo» sobre cifras visibles). Tools por cada cifra (más rondas/tokens).

## R3 — Contraste vía servicio de comparación, no recálculo

**Decision**: Tool interna `compare_sessions` (nombre de producto en contrato) que resuelve IDs/eje/zona y llama al ensamblado de `services/comparison.py` (misma semántica que `POST /comparisons`). El chat no reimplementa sumas ni insights.

**Rationale**: Constitución II/VI y FR-002; evita drift entre UI de comparación y chat.

**Alternatives considered**: El modelo inventa deltas (prohibido). Duplicar lógica en chat (doble mantenimiento). Solo narrar si el usuario ya abrió la pantalla de comparación (rechazado en clarify).

## R4 — Resolución de sesiones y eje para el contraste

**Decision**: Backend resuelve el conjunto: sesión abierta del panel + nombres citados y/o «la última» (`finished_at`, reglas 008). El eje lo indica la pregunta vía argumento acotado de la tool (`session` | `day` | `time_of_day` | `zone`); si no hay señal de eje y el pedido es «cuál de estas dos», default `session`. Ambigüedad o &lt;2 elegibles → `needs_clarification` / datos insuficientes, cero llamadas al modelo si se detecta antes, o tool que devuelve error estructurado sin inventar columnas. Webcam e incompletas fuera (009/013).

**Rationale**: Clarify B + ejes P2 (A).

**Alternatives considered**: Siempre abierta vs última sin nombres (poco flexible). Elegir par al azar (prohibido).

## R5 — Sin RAG; grounding = tool results

**Decision**: No Azure AI Search, embeddings ni knowledge store para cifras. El system prompt ordena usar solo resultados de tools. Prueba de grounding con redactor falso que recibe el payload de tools.

**Rationale**: FR-005, constitución VI, demo de materia.

**Alternatives considered**: RAG de glosario (fuera de alcance cifras; se puede mencionar en defensa como descartado). SQL tool (prohibido).

## R6 — Filtros previos/posteriores actualizados

**Decision**: Pre-filtro: compra confirmada, identidad, multi-cámara, SQL/video crudo, fuera de analytics. Post-filtro: todo número del borrador ∈ payload de tools de esa pregunta; estimaciones no como hechos/ventas. Preguntas del catálogo ampliado ya no se cortan como en 008 (salidas/tasa/pasos permitidos).

**Rationale**: US4 + supersesión de 008.

**Alternatives considered**: Confiar solo en el modelo (riesgo de venta/identidad).

## R7 — Presupuesto de llamadas e independencia de turnos

**Decision**: Máximo 2 llamadas al modelo por pregunta; timeout existente. Sin memoria de cifras entre turnos (US3 diferido). El panel puede mostrar mensajes locales pero cada `POST /chat` es autocontenido.

**Rationale**: Clarify US3=B; crédito no medido.

**Alternatives considered**: Hilo con historial en el request (aplazado). Más de 2 rondas por multi-tool (costo/timeout).

## R8 — Sin migración ni paquetes nuevos

**Decision**: Solo código de servicios/API/UI/tests. Sin Alembic. Sin dependencias npm/pip nuevas.

**Rationale**: Stack acordado; datos ya persistidos por 006–013.

**Alternatives considered**: Tabla de historial de chat (no pedida). SDK de agentes Foundry (sobrepeso para el MVP de #11).
