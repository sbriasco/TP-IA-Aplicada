---

description: "Lista de tareas de la feature 014: chat analítico ampliado"
---

# Tasks: Chat analítico ampliado

**Input**: Documentos de diseño de `/specs/014-chat-analitico-ampliado/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #11 (Epic #3).

**Tests**: Se incluyen porque [plan.md](./plan.md), [quickstart.md](./quickstart.md) y los Independent Test de la spec los exigen (grounding sin modelo de pago). Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Tareas por User Story. Rutas relativas a la raíz del repo. Sin migración. Sin paquetes nuevos. Sin tocar `vision/` ni el worker. US3 (hilo) **diferido**: no hay tareas de implementación. MUST NOT alterar cuerpos de GET métricas/funnel/patrones/possible-purchases ni de `POST /comparisons`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US4).

## Phase 1: Setup

**Purpose**: Confirmar alcance sin dependencias nuevas.

- [X] T001 Verificar que `backend/pyproject.toml` y `frontend/package.json` no ganan paquetes. Confirmar en [plan.md](./plan.md) que no hay migración Alembic ni RAG/vector store; US3 queda fuera del compromiso.

**Checkpoint**: Alcance = ampliar `POST /chat` + panel existente; reutilizar `comparison.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contratos de respuesta/tooling compartidos y ampliación del catálogo de lecturas que bloquean US1–US4.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T002 [P] Ampliar schemas de chat en `backend/src/flowsight/api/schemas.py` según [contracts/openapi.yaml](./contracts/openapi.yaml) y [data-model.md](./data-model.md) (`ChatFigure` con `estimation`, `scope` `whole_session`|`comparison`, `comparison` summary opcional).
- [X] T003 Extender `backend/src/flowsight/services/chat_metrics.py` al catálogo cerrado de [contracts/metric-tools.md](./contracts/metric-tools.md): cinco cifras + `exits` + `store_pass` + `entry_rate` + pico + funnel/patrones/posible compra opcionales; webcam/incomplete → no catálogo como cierre; sin recalcular desde video.

**Checkpoint**: Se puede unit-testear el bundle de cifras ampliadas con redactor falso, sin UI.

---

## Phase 3: User Story 1 — Más familias de cifras ya guardadas (Priority: P1) 🎯 MVP

**Goal**: Desde el panel de resultados, preguntar por el catálogo ampliado de una sesión/zona; cada número citado sale de una lectura; opcionales ausentes = no disponible.

**Independent Test**: Sesión de archivo completada + zona → preguntas de prueba (con redactor falso) citan solo cifras del bundle; funnel/patrones/compra ausentes → unavailable; webcam → unavailable; sin Azure de pago.

### Tests for User Story 1

- [X] T004 [P] [US1] Extender `backend/tests/unit/test_chat_metrics.py` para salidas, pasos, tasa, opcionales presentes/ausentes, rótulos de estimación y alcance whole_session. Sin video ni GPU.
- [X] T005 [P] [US1] Extender `backend/tests/contract/test_chat_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml): `POST /chat` answered con figures del catálogo; unavailable en vivo/incompleto; misma pregunta → mismas figures; GET métricas/funnel/patrones/possible-purchases sin cambio de cuerpo.
- [X] T006 [P] [US1] Extender `frontend/tests/SessionChatPanel.test.tsx` según [contracts/chat-ui.md](./contracts/chat-ui.md): espera/answered con rótulos ampliados; limpieza al cambiar sesión; no segundo modo «solo cinco cifras».

### Implementation for User Story 1

- [X] T007 [US1] Actualizar tool `get_session_figures` (o equivalente) y el ensamblado en `backend/src/flowsight/services/chat.py` para entregar el catálogo de T003 al modelo/redactor falso; tope 2 llamadas; sin memoria entre turnos. Hasta T004 en verde.
- [X] T008 [US1] Cablear respuesta ampliada en `backend/src/flowsight/api/routes.py` (`POST /chat`) con schemas de T002. Hasta T005 en verde.
- [X] T009 [US1] Actualizar `frontend/src/components/SessionChatPanel.tsx` (y tipos del cliente de chat si existen) para mostrar figures/rótulos del catálogo ampliado sin cambiar el layout del tablero. Hasta T006 en verde.

**Checkpoint**: MVP: chat de una sesión con catálogo ampliado y grounding demostrable sin Azure.

---

## Phase 4: User Story 2 — Contraste entre sesiones / ejes (Priority: P1)

**Goal**: Nombrar sesiones y/o «última» + abierta; contrastar por `session` / `day` / `time_of_day` / `zone` reutilizando `comparison.py`; sin inventar columnas.

**Independent Test**: Dos sesiones elegibles → pregunta de contraste con redactor falso; números = contraste 013; eje sin grupos o sin par → clarification/insuficiente; lecturas individuales y `POST /comparisons` intactos.

### Tests for User Story 2

- [X] T010 [P] [US2] Extender `backend/tests/unit/test_chat_drafter.py` o nuevo `backend/tests/unit/test_chat_comparison_tool.py`: resolución abierta+última / nombres; ejes; ambigüedad; &lt;2 elegibles; webcam excluida.
- [X] T011 [P] [US2] Extender `backend/tests/contract/test_chat_api.py`: contraste answered con `scope=comparison` y summary; needs_clarification sin par; axis unavailable sin ranking; `POST /comparisons` regresión misma forma.
- [X] T012 [P] [US2] Extender `frontend/tests/SessionChatPanel.test.tsx`: mensaje de contraste/aclaración; sin inventar columnas en UI.

### Implementation for User Story 2

- [X] T013 [US2] Añadir tool de contraste en `backend/src/flowsight/services/chat.py` que resuelva session_ids/zone_name/axis y delegue en `backend/src/flowsight/services/comparison.py` (sin recalcular). Default axis `session` si el pedido es par sin eje. Hasta T010 en verde.
- [X] T014 [US2] Exponer `scope` / `comparison` summary en la respuesta de `POST /chat` y filtrar números del borrador contra celdas del contraste. Hasta T011 en verde.
- [X] T015 [US2] Mostrar eje y columnas del contraste (o aclaración) en `frontend/src/components/SessionChatPanel.tsx` según [contracts/chat-ui.md](./contracts/chat-ui.md). Hasta T012 en verde.

**Checkpoint**: Chat puede narrar contrastes multi-eje con las mismas reglas que la pantalla de comparación.

---

## Phase 5: User Story 4 — Rechazos y fallo seguro (Priority: P1)

**Goal**: Rechazar compra confirmada, identidad, multi-cámara, SQL/video; no afirmar venta al citar posible compra; error/timeout sin romper tablero ni comparación.

**Independent Test**: Conjunto de preguntas prohibidas → `refused` sin cifras; borrador que afirma venta → no se muestra; modelo ausente/timeout → `error` y UI usable; grounding sigue sin Azure.

### Tests for User Story 4

- [X] T016 [P] [US4] Extender `backend/tests/unit/test_chat_guard.py`: rechazo compra/identidad/SQL/video; permitir tasa/salidas/pasos (ya no veto 008); post-filtro de estimación vs venta.
- [X] T017 [P] [US4] Extender `backend/tests/contract/test_chat_api.py`: `refused` / `error` sin figures; tablero no afectado (smoke de otro GET).

### Implementation for User Story 4

- [X] T018 [US4] Actualizar `backend/src/flowsight/services/chat_guard.py` y el pre/post-filtro en `backend/src/flowsight/services/chat.py` según R6 de [research.md](./research.md). Hasta T016 en verde.
- [X] T019 [US4] Asegurar estados `refused`/`error`/`unavailable` en panel (`frontend/src/components/SessionChatPanel.tsx`) sin bloquear resultados ni navegación a comparación. Hasta T017 en verde.

**Checkpoint**: Ampliar tools no debilita el alcance comprometido de privacidad/estimaciones.

---

## Phase 6: User Story 3 — Hilo de seguimiento (Priority: P2) · DIFERIDO

**No implementar en esta entrega.** Clarificación 2026-10-27: preguntas independientes bastan; US3 no bloquea Feature #11.

- [X] T020 Documentar en el PR / notas de cierre que US3 queda diferido y que cada `POST /chat` sigue autocontenido (sin historial de cifras en el body).

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Validación quickstart y regresión.

- [X] T021 Ejecutar comandas de [quickstart.md](./quickstart.md) (unit+contract chat, regresión comparisons/métricas/funnel/patrones/possible-purchase, Vitest SessionChatPanel) y corregir solo fallos de esta feature. No agregar paquetes.
- [X] T022 [P] Verificar que no quedaron referencias de producto al «chat mínimo de solo cinco cifras» como modo activo en UI (`frontend/src/components/SessionChatPanel.tsx` y textos de ayuda relacionados).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)**: inmediato
- **Foundational (2)**: tras Setup — **bloquea** US1/US2/US4
- **US1 (3)**: tras Foundational — MVP
- **US2 (4)**: tras Foundational; conviene tras US1 (mismo `chat.py` / panel) pero testeable con contraste aislado
- **US4 (5)**: tras Foundational; ideal tras US1 (catálogo) para no reintroducir veto de tasa/salidas
- **US3 (6)**: solo documentación de diferido
- **Polish (7)**: tras US1+US2+US4 deseados

### User Story Dependencies

- **US1**: no depende de US2
- **US2**: reutiliza T003/T007; depende de `comparison.py` ya en main
- **US4**: puede empezar en paralelo a US2 tras US1 parcial, pero comparte `chat_guard.py` / panel
- **US3**: diferido

### Parallel Opportunities

- T002 ∥ preparación de fixtures
- T004 ∥ T005 ∥ T006 (tests US1)
- T010 ∥ T011 ∥ T012 (tests US2)
- T016 ∥ T017 (tests US4)
- T022 ∥ parte de T021

### Within Each Story

1. Tests primero (deben fallar)
2. Servicios / tools
3. API
4. Panel
5. Checkpoint verde

---

## Parallel Example: User Story 1

```text
Task: "T004 unit test_chat_metrics.py"
Task: "T005 contract test_chat_api.py"
Task: "T006 frontend SessionChatPanel.test.tsx"

# Tras T002/T003:
Task: "T007 chat.py get_session_figures ampliado"
Task: "T008 routes POST /chat"
Task: "T009 SessionChatPanel rótulos"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1–2  
2. Phase 3 (US1)  
3. Validar grounding sin Azure  
4. Demo mínima / PR parcial si hace falta  

### Incremental Delivery

1. US1 catálogo ampliado  
2. US2 contraste multi-eje  
3. US4 guards endurecidos  
4. T021 quickstart  
5. No US3  

### Parallel Team Strategy

- Dev A: US1 backend metrics + chat tool  
- Dev B: US1/US2 frontend panel  
- Dev C: US2 comparison tool + US4 guards  
Tras Foundational.

---

## Notes

- Un solo panel supersede 008; actualizar tests que aún esperen veto de tasa/salidas/pasos.
- Contraste = delegación a 013; no duplicar agregación.
- Sin RAG, sin SQL libre, sin paquetes, sin migración.
- Commit por tarea o grupo lógico; PR indica Feature #11 de Boards.
