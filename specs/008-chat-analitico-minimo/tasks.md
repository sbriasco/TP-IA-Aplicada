---

description: "Lista de tareas de la feature 008: chat analítico mínimo"
---

# Tasks: Chat analítico mínimo

**Input**: Documentos de diseño de `/specs/008-chat-analitico-minimo/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [contracts/metric-tools.md](./contracts/metric-tools.md), [contracts/chat-ui.md](./contracts/chat-ui.md), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #16 (Epic #1). US1 = #68, US2 = #69, US3 = #70, US4 = #72, US5 = #71. Bajo #68: #123 (T003) y #124 (T004). Bajo #69: #125 (T001), #126 (T002), #127 (T005), #128 (T006) y #129 (T015). Bajo #70: #130 (T007) y #131 (T008). Bajo #72: #132–#135 (T009–T012). Bajo #71: #136 (T013) y #137 (T014).

**Tests**: Se incluyen porque el plan y [quickstart.md](./quickstart.md) los nombran, y la constitución pide pruebas del recorrido. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1 a US5).
- No hay migración. No se toca `backend/src/flowsight/llm/fake_tools.py` ni `backend/src/flowsight/llm/tool_loop.py`.
- No se agrega un SDK ni una librería de interfaz. El detector de la suite sigue siendo `fake`.

---

## Phase 1: Setup

**Purpose**: El tope de espera existe y la API sigue arrancando sin Azure.

- [x] T001 Agregar `FLOWSIGHT_CHAT_TIMEOUT_SECONDS` con default 20 en `backend/src/flowsight/core/config.py` y en `.env.example`, junto a las variables de Azure que ya documenta specs/003. La API tiene que arrancar si esas variables de Azure no están. No editar `backend/src/flowsight/llm/fake_tools.py` ni `backend/src/flowsight/llm/tool_loop.py`.

**Checkpoint**: El default es 20 segundos y la ausencia de la clave de Azure no impide levantar la API.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: El cuerpo de `POST /chat` existe antes de que una historia lo devuelva.

**⚠️ CRITICAL**: Ninguna User Story que responda por HTTP empieza hasta completar esta fase. US1 puede leer cifras sin este cuerpo, pero el pedido de chat no.

- [x] T002 Declarar `ChatRequest`, `ChatResponse` y `ChatFigure` en `backend/src/flowsight/api/schemas.py`, con `extra` prohibido, según [contracts/openapi.yaml](./contracts/openapi.yaml) y [data-model.md](./data-model.md). No agregar todavía la ruta.

**Checkpoint**: Los tres modelos rechazan un campo desconocido y aceptan los estados `answered`, `refused`, `needs_clarification`, `unavailable` y `error`.

---

## Phase 3: User Story 1 — Consultar solo las cifras ya registradas (Priority: P1) · #68 🎯 MVP

**Goal**: Cinco lecturas devuelven la cifra ya registrada de una sesión y un local, o no disponible. No llaman al modelo.

**Independent Test**: Con una sesión completada, cada lectura coincide con lo ya registrado para toda la sesión. Una cifra no disponible no vuelve como cero. Otra sesión no se mezcla. Un análisis sin `result_complete` no devuelve las cinco. Salidas, pasos y tasa no tienen lectura.

### Tests for User Story 1

- [x] T003 [US1] Escribir `backend/tests/unit/test_chat_metrics.py` contra [contracts/metric-tools.md](./contracts/metric-tools.md). Usa la base de `destructive_database_url()` como `backend/tests/contract/test_scene_metrics_api.py`. Cubre tráfico, entradas, ocupación visible, media y mediana de permanencia, y el pico (`start_seconds`, `track_count`). Una no disponible conserva el motivo. Un tramo pedido no cambia el valor. Otra sesión no aparece. Sin `result_complete`, no hay cifras finales ni las tres parciales. No existe lectura de salidas, pasos ni tasa. La prueba debe fallar antes de T004.

### Implementation for User Story 1

- [x] T004 [US1] Crear `backend/src/flowsight/services/chat_metrics.py`. Cada lectura llama a `load_shop_metrics` y no recalcula. El pico es el bucket ya guardado, citado como tramo del video. Ignorar un tramo si alguien lo pasa. Hasta T003 en verde.

**Checkpoint**: Las cinco lecturas se prueban sin redactor y sin Azure.

---

## Phase 4: User Story 2 — Preguntar por una sesión y recibir cifras respaldadas (Priority: P1) · #69

**Goal**: `POST /chat` responde con cifras de la sesión abierta y el local elegido. Un fallo del redactor no tira el tablero.

**Independent Test**: Todo número de una respuesta contestada está en las lecturas de esa pregunta. Hay como máximo dos llamadas. Sin configuración, con el tiempo agotado o con texto vacío, el estado es `error` y el pedido de métricas de esa sesión sigue respondiendo.

### Tests for User Story 2

- [x] T005 [US2] Escribir `backend/tests/contract/test_chat_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml). Inyecta un redactor falso: no llama a Azure. Cubre una pregunta por tráfico con local y alcance `whole_session`; un número que el falso no recibió de una lectura no puede quedar en `answered`; `model_calls` como máximo 2; pregunta vacía en 400; sesión inexistente en 404; sin configuración, tiempo agotado y contenido vacío en `error`, sin cifras, y `GET /sessions/{id}/shops/{shop_id}/metrics` sigue en 200. La prueba debe fallar antes de T006.

### Implementation for User Story 2

- [x] T006 [US2] Crear `backend/src/flowsight/services/chat.py` y `POST /chat` en `backend/src/flowsight/api/routes.py`. Usa T002 y T004. La sesión y el local son los del pedido. El redactor es el cliente ya validado en specs/003, reemplazable en la prueba. Tope de dos llamadas y de `FLOWSIGHT_CHAT_TIMEOUT_SECONDS`. El registro anota la cantidad de llamadas y el código de error, no la clave, ni la pregunta, ni el borrador. Hasta T005 en verde.

**Checkpoint**: Una pregunta sobre la sesión abierta cita solo cifras leídas. Azure no hace falta para la prueba.

---

## Phase 5: User Story 3 — No afirmar ventas ni identidades (Priority: P1) · #70

**Goal**: El chat rechaza compras, identidades y temas ajenos antes de leer cifras, y no muestra un borrador que igual lo afirmaría.

**Independent Test**: El conjunto de preguntas prohibidas vuelve `refused` con `model_calls` en 0. Un borrador que confirma una venta, nombra a una persona o trata una estimación como observación no se muestra así. Un pedido de salidas, pasos o tasa no trae un número.

### Tests for User Story 3

- [x] T007 [US3] Escribir `backend/tests/unit/test_chat_guard.py` y extender `backend/tests/contract/test_chat_api.py`. El filtro previo rechaza compra, identidad, seguimiento entre cámaras y un tema ajeno a las cinco cifras, sin lecturas. Salidas, pasos y tasa se responden sin número. El filtro posterior rechaza un borrador con una venta, una identidad o un número que no está en las lecturas. `POST /chat` de esos casos queda en `refused` y `model_calls` 0. La prueba debe fallar antes de T008.

### Implementation for User Story 3

- [x] T008 [US3] Crear `backend/src/flowsight/services/chat_guard.py` y llamarlo desde `backend/src/flowsight/services/chat.py` antes de las lecturas y antes de devolver el texto. Si el borrador no pasa, la respuesta es un rechazo, no el borrador. Hasta T007 en verde.

**Checkpoint**: Ninguna respuesta mostrada confirma una venta ni identifica a una persona.

---

## Phase 6: User Story 4 — Chatear sobre la sesión que se está viendo (Priority: P1) · #72

**Goal**: El panel de resultados muestra espera, error y las cifras que respaldan la respuesta. Cambiar de sesión no arrastra el hilo.

**Independent Test**: En resultados se pregunta sin salir de la sesión. Se ve espera o error. Una respuesta contestada muestra local, toda la sesión y los valores. Al abrir otra sesión el panel queda vacío y los indicadores siguen si el chat falla.

### Tests for User Story 4

- [x] T009 [P] [US4] Escribir `frontend/tests/SessionChatPanel.test.tsx` contra [contracts/chat-ui.md](./contracts/chat-ui.md). El campo tiene etiqueta visible. Al enviar se ve espera. `answered` muestra el texto, el local, toda la sesión y los rótulos «estimación de visitas», «visible», «observable» o «no disponible». `refused`, `needs_clarification` y `unavailable` no muestran cifras. `error` muestra el mensaje. La prueba debe fallar antes de T011.
- [x] T010 [P] [US4] Extender `frontend/tests/SessionResultsPage.test.tsx`. El panel viaja con la sesión abierta y el local elegido. Al cambiar el id de sesión, el hilo anterior no está. Un `error` del chat no oculta los indicadores. La prueba debe fallar antes de T011.

### Implementation for User Story 4

- [x] T011 [US4] Crear `frontend/src/api/chat.ts`, `frontend/src/components/SessionChatPanel.tsx` y `frontend/src/components/SessionChatPanel.module.css`. Montar el panel desde `frontend/src/pages/SessionResultsPage.tsx`. El pedido lleva la sesión de la página y el local elegido, o `shop_id` vacío si no hay uno. No persistir el hilo. Hasta T009 y T010 en verde.
- [x] T012 [US4] Escribir `frontend/e2e/session-chat.spec.ts` y engancharlo al recorrido que ya corre `frontend/e2e/run-e2e.mjs`. En resultados envía una pregunta, ve la espera y después el local y el alcance. Abre otra sesión y el panel queda vacío. El redactor es el falso de la suite, no Azure.

**Checkpoint**: El panel de la sesión abierta se puede usar sin nombrar otras sesiones.

---

## Phase 7: User Story 5 — Referirse a una sesión anterior (Priority: P2) · #71

**Goal**: «La última» y un nombre eligen una sesión procesada. Si hay más de una coincidencia, el chat pregunta y no elige solo.

**Independent Test**: Con dos sesiones de distinto nombre, «la última» es la de `finished_at` más reciente. Un nombre único elige esa sesión. Un nombre que coincide con dos no elige una y `model_calls` queda en 0.

### Tests for User Story 5

- [x] T013 [US5] Extender `backend/tests/contract/test_chat_api.py`. «La última» usa el mayor `finished_at`; si empatan, el `job_id` mayor. Un nombre, sin distinguir mayúsculas, elige esa sesión. Dos nombres iguales vuelven `needs_clarification` y `model_calls` 0. Sin sesiones procesadas, el mensaje lo dice y no inventa cifras. La prueba debe fallar antes de T014.

### Implementation for User Story 5

- [x] T014 [US5] Resolver la sesión en `backend/src/flowsight/services/chat.py` antes del redactor, leyendo el listado de `backend/src/flowsight/services/processed_sessions.py`. La sesión abierta gana salvo «la última» o un nombre. Un análisis sin `result_complete` no se reemplaza por uno anterior completo. El listado que vea el redactor trae `session_id`, `name`, `finished_at` y `result_complete`, sin métricas. Hasta T013 en verde.

**Checkpoint**: US4 sigue valiendo si esta historia no se entrega. Con ella, un nombre ambiguo no mezcla sesiones.

---

## Phase 8: Polish

**Purpose**: Correr la validación del quickstart. La corrida manual de Azure no bloquea.

- [x] T015 Correr los comandos de [quickstart.md](./quickstart.md): `backend/tests/unit/test_chat_metrics.py`, `backend/tests/contract/test_chat_api.py`, `npm test` y `npm run test:e2e` en `frontend/`. No llamar a Azure desde esa suite. No anotar una medición nueva del detector.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: puede empezar ya. La usa US2.
- **Foundational (Phase 2)**: bloquea el `POST /chat`. No bloquea escribir T003.
- **US1 (Phase 3)**: puede empezar después de Phase 1. No depende de US2.
- **US2 (Phase 4)**: después de Phase 2 y US1.
- **US3 (Phase 5)**: después de US2. El filtro se engancha en el pedido que US2 ya responde.
- **US4 (Phase 6)**: después de US2. Puede hacerse en paralelo con US3 si el panel habla con el pedido ya existente.
- **US5 (Phase 7)**: después de US2. No bloquea el panel de la sesión abierta.
- **Polish (Phase 8)**: después de US1, US2, US3 y US4. US5 entra en el mismo cierre si ya está.

### User Story Dependencies

- **US1 (P1)**: lecturas. MVP del dato.
- **US2 (P1)**: el pedido que cita esas lecturas.
- **US3 (P1)**: rechazos sobre ese pedido.
- **US4 (P1)**: panel. Depende del pedido, no de US5.
- **US5 (P2)**: última sesión y nombre. El panel de US4 vale sin ella.

### Within Each User Story

- La prueba se escribe y falla antes de la implementación que la pone verde.
- Las lecturas van antes del pedido. El pedido va antes del panel y del filtro.

### Parallel Opportunities

- T009 y T010 tocan archivos de prueba distintos.
- US3 y US4 pueden avanzar a la vez después de US2.
- US5 puede esperar sin frenar el panel.

### Parallel Example: User Story 4

```text
T009 SessionChatPanel.test.tsx
T010 SessionResultsPage.test.tsx
luego T011 el panel
luego T012 el recorrido
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1.
2. Phase 3 (#68).
3. Parar y correr `backend/tests/unit/test_chat_metrics.py`.

### Incremental Delivery

1. US1 deja las cinco lecturas, sin redactor.
2. US2 deja `POST /chat` con el redactor falso en la suite.
3. US3 deja los rechazos.
4. US4 deja el panel en resultados.
5. US5 deja «la última» y el nombre. Si no entra, US1 a US4 igual se dan por válidas.

---

## Notes

- [P] = archivos distintos, sin depender de una tarea incompleta.
- Las pruebas se escriben primero y tienen que fallar antes de la implementación.
- No commitear desde estas tareas: el cierre lo hace quien pide el commit.
- La herramienta ficticia de specs/003 no responde este chat. El `42` de esa prueba no es una cifra de sesión.
