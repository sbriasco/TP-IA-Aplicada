---

description: "Lista de tareas de la feature 012: evaluación de posible compra"
---

# Tasks: Evaluación de posible compra

**Input**: Documentos de diseño de `/specs/012-posible-compra/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #9 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

**Tests**: Se incluyen porque el plan los nombra, [quickstart.md](./quickstart.md) los usa para validar y la constitución pide pruebas de tiempos, aislamiento y métricas. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3).
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno. Las pruebas que migran usan `destructive_database_url()` de `backend/tests/conftest.py`.
- No se agregan dependencias. El detector de la suite sigue siendo `fake`. Las clases de bolsa son `backpack`, `handbag` y `suitcase` ([R1](./research.md#r1--qué-cuenta-como-bolsa)). No se reescriben `scene_events`, el funnel ni los patrones.

## Phase 1: Setup

**Purpose**: Confirmar que esta feature no cambia el lock ni el alcance.

- [X] T001 Verificar que `backend/pyproject.toml` y `frontend/package.json` no ganan paquetes nuevos. Si [plan.md](./plan.md) ya lo dice, dejar ese archivo quieto.

**Checkpoint**: El alcance sigue siendo la regla nueva en `vision/`, el cierre del análisis de archivo, un pedido nuevo y el bloque en resultados.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0016`, modelos y contrato de recuadros de bolsa que US1 necesita.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T002 Escribir `backend/tests/integration/test_migration_0016.py` con `destructive_database_url()`. Sobre una base en `0015_visit_patterns`, `upgrade head` crea `possible_purchase_reports` y `possible_purchase_members` según [data-model.md](./data-model.md). `possible_purchase_reports` es único por `job_id`, guarda `minimum_seconds = 1`, `visit_count` ≥ 0, `availability = available` y `precision_uncommitted` verdadero. Miembros únicos por `(report_id, track_id)`. `shop_metrics` no gana códigos. `scene_events`, `shop_funnels`, `visit_pattern_reports` y `trajectory` no cambian de forma. El `downgrade` a `0015` solo se usa como fixture de test y no toca esas tablas.
- [X] T003 Crear `backend/alembic/versions/0016_possible_purchase.py` (`down_revision = 0015_visit_patterns`) que cumpla T002. Los enums nuevos, si los hay, se crean en la misma transacción. Correr T002 hasta verde.
- [X] T004 Extender `backend/src/flowsight/db/models.py` con los modelos de T003, con los mismos nombres de restricción. `alembic check` no debe reportar diferencias.
- [X] T005 Ampliar el contrato de detección en `backend/src/flowsight/vision/detector.py` para que, además de las personas (`Detection` con `track_id` y `bbox`), el mismo fotograma pueda aportar recuadros de bolsa sin `track_id` ([R3](./research.md#r3--se-cierra-en-el-mismo-análisis)). Actualizar `backend/src/flowsight/vision/fake.py` para emitir esos recuadros en los casos de prueba. En `backend/src/flowsight/vision/ultralytics_tracker.py`, filtrar `backpack`, `handbag` y `suitcase` como bolsas sin alterar el seguimiento de personas. No modificar `backend/src/flowsight/vision/events.py` ni `backend/src/flowsight/vision/spatial.py`.

**Checkpoint**: `alembic upgrade head` aplica `0016`. Un análisis de specs/006, el funnel de specs/010 y los patrones de specs/011 siguen guardando las mismas cifras.

---

## Phase 3: User Story 1 — Estimar una posible compra por una bolsa observada (Priority: P1) 🎯 MVP

**Goal**: Al completar un análisis de archivo, cada visita cuyo recuadro se solapa en exclusiva con una bolsa al menos 1 segundo de video cuenta una vez. Las ocho métricas, el funnel y los patrones no cambian.

**Independent Test**: Con recuadros sintéticos, sin pantalla ni video real: solape exclusivo ≥ 1 segundo cuenta una vez; menos de 1 segundo no cuenta; hueco ≤ 1 segundo no inventa; más de 1 segundo o pérdida de seguimiento cierra el tramo; dos visitas o ninguna no cuentan; la misma visita no suma dos veces; entrada/atención sin bolsa no cuentan.

### Tests for User Story 1

- [X] T006 [P] [US1] Escribir `backend/tests/unit/test_possible_purchase.py` para la función pura de `backend/src/flowsight/vision/possible_purchase.py`, sin base de datos y sin leer `trajectory.jsonl`. Cubrir [R2](./research.md#r2--solape-exclusivo-con-exactamente-una-visita) y [R4](./research.md#r4--qué-se-guarda): solape exclusivo ≥ 1 segundo de video cuenta esa visita una vez; solape de menos de 1 segundo no cuenta; hueco de hasta 1 segundo no inventa el solape ni parte el indicio; hueco de más de 1 segundo o pérdida del identificador cierra el tramo y una visita nueva no hereda; bolsa que se solapa con dos visitas o con ninguna no cuenta; la misma visita vuelve a solaparse después de un corte y sigue contando uno; el reloj es `(fotograma final − fotograma inicial) / fps`; si el video termina y el tramo ya llevaba 1 segundo, se conserva hasta el último fotograma; cero visitas es un conteo disponible.
- [X] T007 [P] [US1] Escribir `backend/tests/integration/test_possible_purchase_job.py` con el detector falso. Al completar un `video_analysis` que no es webcam, el informe y los integrantes quedan en las tablas de esa sesión y de ninguna otra. Un trabajo `failed` o `cancelled` no los presenta como resultado completo. Una webcam no escribe `possible_purchase_reports`. `shop_metrics` conserva sus ocho códigos, el funnel de specs/010 conserva sus etapas y los patrones de specs/011 conservan sus filas. Borrar o cambiar `trajectory.jsonl` después del cierre no cambia esas filas.

### Implementation for User Story 1

- [X] T008 [US1] Crear `backend/src/flowsight/vision/possible_purchase.py`, puro, sin FastAPI ni SQL. Recibe fotograma, fps, detecciones de persona y recuadros de bolsa. Implementar el solape exclusivo y el conteo de una vez por visita, con estado por identificador y sin guardar un recuadro por fotograma. No modificar `backend/src/flowsight/vision/events.py` ni `backend/src/flowsight/vision/spatial.py`. Hasta T006 en verde.
- [X] T009 [US1] Crear `backend/src/flowsight/services/possible_purchase.py` para persistir `possible_purchase_reports` y `possible_purchase_members`. Llamarlo desde `backend/src/flowsight/worker/video_analysis.py` en la misma transacción que `persist_shop_funnel` y `persist_visit_patterns`, antes de pasar el trabajo a `completed`, y no llamarlo si el origen es webcam. Hasta T007 en verde.

**Checkpoint**: Un análisis falso completado deja la posible compra estimada de esa sesión. Las ocho métricas, el funnel y los patrones quedan iguales.

---

## Phase 4: User Story 2 — Leer la estimación en el resultado (Priority: P2)

**Goal**: El analista ve, en el resultado de un archivo ya terminado, la cantidad de visitas con posible compra estimada, el umbral de 1 segundo y que no es una venta. El tramo y el local elegido no la recalculan.

**Independent Test**: Una sesión de archivo completada muestra la cantidad, el umbral, el rótulo de estimación y el aviso de precisión. Cero se lee como cero. Cambiar el tramo o el local no vuelve a pedir el bloque. Una webcam no lo muestra. El chat mínimo no responde con esta cifra.

### Tests for User Story 2

- [X] T010 [P] [US2] Escribir `backend/tests/contract/test_possible_purchase_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml). `GET /sessions/{session_id}/possible-purchases` devuelve `availability`, `visit_count`, `minimum_seconds` `"1"`, `precision_uncommitted` verdadero y `track_ids` ordenados. No acepta `shop_id`, `from_seconds` ni `to_seconds`. Otra sesión no devuelve esas filas. Análisis no completado: `409` `result_incomplete`. Webcam: `409` `live_purchase_unavailable` y cero filas. Cero visitas: `visit_count` 0 y disponible. `GET /sessions/{session_id}/shops/{shop_id}/metrics`, `GET /sessions/{session_id}/shops/{shop_id}/funnel` y `GET /sessions/{session_id}/visit-patterns` no cambian de cuerpo. `get_session_figures` en `backend/src/flowsight/services/chat.py` no ofrece esta cifra.
- [X] T011 [P] [US2] Escribir `frontend/tests/PossiblePurchasePanel.test.tsx` según [contracts/possible-purchase-ui.md](./contracts/possible-purchase-ui.md). Cubre la cantidad, el umbral de 1 segundo de video, el texto de que es una estimación y no es una venta confirmada, el aviso «La precisión de la posible compra estimada no está comprometida.» y «0 visitas con posible compra estimada» cuando el conteo es cero.
- [X] T012 [P] [US2] Extender `frontend/tests/SessionResultsPage.test.tsx` para que una sesión de archivo completada pida `GET /sessions/{session_id}/possible-purchases` una sola vez. Cambiar el tramo o el local no dispara otro pedido. Una sesión webcam y un análisis incompleto no muestran el bloque.

### Implementation for User Story 2

- [X] T013 [US2] Exponer `GET /sessions/{session_id}/possible-purchases` en `backend/src/flowsight/api/routes.py` y `backend/src/flowsight/api/schemas.py`, leyendo desde `backend/src/flowsight/services/possible_purchase.py`, con los `409` de T010. No modificar el cuerpo de métricas, funnel ni patrones. Hasta T010 en verde.
- [X] T014 [US2] Crear el cliente y los tipos de `GET /sessions/{session_id}/possible-purchases` en `frontend/src/api/possiblePurchases.ts`, sin parámetros de tramo ni de local.
- [X] T015 [US2] Crear `frontend/src/components/PossiblePurchasePanel.tsx` y `frontend/src/components/PossiblePurchasePanel.module.css` con el contenido de T011.
- [X] T016 [US2] Montar el panel en `frontend/src/pages/SessionResultsPage.tsx` solo para una sesión que no es webcam y cuyo análisis está completado. Pedir el recurso una vez por sesión. El efecto que cambia el tramo o el local no debe volver a pedirlo. Hasta T011 y T012 en verde.

**Checkpoint**: El resultado de archivo muestra la posible compra estimada de toda la sesión. El chat mínimo y el tramo siguen sin recalcularla.

---

## Phase 5: User Story 3 — Contrastar con una observación manual (Priority: P2)

**Goal**: Dejar el lugar donde el equipo anota el contraste de un clip, sin exigir ese clip para la suite.

**Independent Test**: El archivo de contraste existe, clasifica diferencias con el protocolo de specs/001 y no afirma exactitud ni una venta. La suite de T006, T007, T010 y T011 sigue pudiendo correr sin ese clip. El aviso de precisión permanece en el panel.

### Implementation for User Story 3

- [X] T017 [US3] Completar o actualizar `specs/012-posible-compra/validation/contrast.md` para un clip del material elegido, con bolsas y visitas anotadas a mano por solape exclusivo y las diferencias clasificadas como en specs/001. Dejar el ensayo en «no ejecutado». Si el material no deja marcar bolsas de forma unívoca, el informe lo dice. No prometer coincidencia ni una venta. No agregar el clip a pytest, Vitest ni Playwright, y no quitar el aviso de `frontend/src/components/PossiblePurchasePanel.tsx`.

**Checkpoint**: El contraste tiene su lugar. La suite no depende del clip real.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validar el recorrido del quickstart sin ampliar el alcance.

- [X] T018 Ejecutar las comandas de [quickstart.md](./quickstart.md) (unit+job, contract de possible-purchase+chat+funnel+visit-patterns, y Vitest de `PossiblePurchasePanel` + `SessionResultsPage`) y corregir solo lo que falle por esta feature. No agregar paquetes ni tocar el funnel ni los patrones más allá de comprobar que no cambiaron.

**Checkpoint**: El quickstart de esta carpeta queda en verde con el detector falso.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias.
- **Foundational (Phase 2)**: Depende del Setup. Bloquea todas las User Stories.
- **US1 (Phase 3)**: Depende de Foundational. MVP.
- **US2 (Phase 4)**: Depende de US1 (hace falta el informe persistido para el pedido y el panel).
- **US3 (Phase 5)**: Puede ir en paralelo con US2 una vez existe el panel (T015), porque solo toca `validation/`.
- **Polish (Phase 6)**: Depende de US1, US2 y US3.

### User Story Dependencies

- **US1 (P1)**: Después de Foundational. No depende de otras historias.
- **US2 (P2)**: Después de US1. Independientemente testeable con un informe ya persistido.
- **US3 (P2)**: Después de que el panel exista (o al menos el aviso de precisión). No bloquea el MVP.

### Within Each User Story

- Pruebas primero y en rojo.
- Regla pura antes de persistir.
- Persistencia antes del pedido.
- Pedido antes del panel.
- Historia completa antes de pasar a la siguiente prioridad, salvo US3 en paralelo con US2.

### Parallel Opportunities

- T006 y T007 en paralelo.
- T010, T011 y T012 en paralelo.
- T014 y T015 en paralelo después de T013.
- T017 puede avanzar mientras se cierra T016.

---

## Parallel Example: User Story 1

```text
Task: "Escribir backend/tests/unit/test_possible_purchase.py …"
Task: "Escribir backend/tests/integration/test_possible_purchase_job.py …"
```

Después, en orden: T008 en `backend/src/flowsight/vision/possible_purchase.py` y T009 en el cierre del worker.

---

## Parallel Example: User Story 2

```text
Task: "Escribir backend/tests/contract/test_possible_purchase_api.py …"
Task: "Escribir frontend/tests/PossiblePurchasePanel.test.tsx …"
Task: "Extender frontend/tests/SessionResultsPage.test.tsx …"
```

Después: T013 (API), luego T014+T015 en paralelo, luego T016 (montaje).

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2.
2. Completar Phase 3 (US1).
3. **STOP and VALIDATE**: unit + job en verde; métricas, funnel y patrones iguales.
4. Demo interna del conteo vía tablas o pedido si ya existe un stub.

### Incremental Delivery

1. Setup + Foundational → esquema y bolsas en el detector.
2. US1 → conteo persistido (MVP).
3. US2 → pedido y bloque en resultados.
4. US3 → contraste «no ejecutado».
5. Polish → quickstart en verde.

### Parallel Team Strategy

1. El equipo cierra Setup + Foundational juntos.
2. Una persona: US1 (visión + worker).
3. Otra persona: US2 (API + panel) cuando US1 deja el informe.
4. US3 puede hacerse en paralelo con el cierre de US2.

---

## Notes

- [P] = archivos distintos, sin depender de tareas incompletas.
- [Story] traza la tarea a la User Story.
- Cada historia debe poder validarse sola.
- Verificar que las pruebas fallen antes de implementar.
- Commit después de cada tarea o grupo lógico.
- Parar en cualquier checkpoint para validar la historia.
- Evitar: tareas vagas, conflictos en el mismo archivo, dependencias cruzadas que rompan la independencia.
- No afirmar precisión. No presentar la cifra como venta. No atribuir la bolsa a un local.
