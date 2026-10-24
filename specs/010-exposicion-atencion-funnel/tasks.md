---

description: "Lista de tareas de la feature 010: exposición, detención, atención estimada y funnel comercial"
---

# Tasks: Exposición, detención, atención estimada y funnel comercial

**Input**: Documentos de diseño de `/specs/010-exposicion-atencion-funnel/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #7 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

**Tests**: Se incluyen porque el plan los nombra, [quickstart.md](./quickstart.md) los usa para validar y la constitución pide pruebas de cruces, duplicados, tiempos, aislamiento y métricas. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3, US4).
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno. Las pruebas que migran usan `destructive_database_url()` de `backend/tests/conftest.py`.
- No se agregan dependencias. El detector de la suite sigue siendo `fake`. La vidriera persistida sigue siendo `zone_role=window`.

## Phase 1: Setup

**Purpose**: Confirmar que esta feature no cambia el lock ni el detector.

- [X] T001 Verificar que `backend/pyproject.toml` y `frontend/package.json` no ganan paquetes nuevos y que `backend/src/flowsight/vision/ultralytics_tracker.py` no se modifica. Si [plan.md](./plan.md) ya lo dice, dejar ese archivo quieto.

**Checkpoint**: El alcance sigue siendo la regla de zona, el cierre del análisis de archivo, un pedido nuevo y el bloque en resultados.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0014` y modelos que todas las historias leen.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T002 Escribir `backend/tests/integration/test_migration_0014.py` con `destructive_database_url()`. Sobre una base en `0013_scene_display_name`, `upgrade head` agrega `showcase_stop` a `scene_event_kind` y crea `shop_funnels`, `shop_funnel_stages` y `shop_funnel_rates` según [data-model.md](./data-model.md). `duration_seconds` es obligatorio solo en `dwell` y `showcase_stop`. `showcase_stop` exige `zone_role=window` y duración ≥ 3. `dwell` sigue exigiendo `front`. UNIQUE de `(job_id, shop_id)` en `shop_funnels`, de `(job_id, shop_id, stage)` en etapas y de `(job_id, shop_id, code)` en tasas. `count` y `value` son nulos si y solo si `availability=unavailable`. `shop_metrics` no gana códigos. El `downgrade` a `0013` solo se usa como fixture de test y no toca `shop_metrics`, `analysis_measures` ni `line_crossings`.
- [X] T003 Crear `backend/alembic/versions/0014_shop_funnel.py` (`down_revision = 0013_scene_display_name`) que cumpla T002. `ALTER TYPE ... ADD VALUE` usa `op.get_context().autocommit_block()` antes de usar el valor nuevo. Correr T002 hasta verde.
- [X] T004 Extender `backend/src/flowsight/db/models.py` con `showcase_stop`, los enums de etapa, tasa y rótulo, y los modelos de T003, con los mismos nombres de restricción. `alembic check` no debe reportar diferencias.

**Checkpoint**: `alembic upgrade head` aplica `0014`. Un análisis de specs/006 sigue guardando las ocho métricas y los `zone_enter` de vidriera.

---

## Phase 3: User Story 1 — Distinguir exposición y detención (Priority: P1) 🎯 MVP

**Goal**: Al completar un análisis, una estadía de vidriera de al menos 3 segundos de video deja una detención, y la exposición sigue siendo la entrada de zona ya existente.

**Independent Test**: Con hechos sintéticos, sin pantalla ni video real: menos de 3 segundos no detiene; 3 segundos o más sí; perder el identificador o terminar el video adentro no detiene; varias entradas de zona por oscilación no se borran y no aparece un segundo hecho de exposición.

### Tests for User Story 1

- [X] T005 [P] [US1] Escribir `backend/tests/unit/test_showcase_stop.py` sobre `SceneEventRecorder` en `backend/src/flowsight/vision/events.py`, sin base de datos. Pie que entra y sale de `window` en menos de 3 segundos de video: `zone_enter` y `zone_exit`, ningún `showcase_stop` y ningún kind nuevo de exposición. Estadía de al menos 3 segundos cerrada al salir: un `showcase_stop` con `zone_role=window`, `duration_seconds` igual a la diferencia de fotogramas dividida por los fps, e instante de la salida. Desaparición del identificador adentro, o fin del recorrido con el pie adentro: ningún `showcase_stop`. Dos entradas y salidas de `window` no borran los `zone_enter`. Un `dwell` frontal sigue existiendo solo para `front`.
- [X] T006 [P] [US1] Escribir `backend/tests/integration/test_showcase_stop_job.py` con el detector falso. Al completar un `video_analysis` que no es webcam, la detención que califica queda en `scene_events` de esa sesión y de ninguna otra. Los `zone_enter` de `window` previos siguen. Un trabajo `failed` o `cancelled` no deja esa detención consultable como resultado completo. `shop_metrics` conserva sus ocho códigos.

### Implementation for User Story 1

- [X] T007 [US1] Cerrar la detención en `backend/src/flowsight/vision/events.py` al salir de `window`, con la misma cuenta `(fotograma de salida − fotograma de entrada) / fps` que el `dwell` frontal. No emitir atención, no tocar la ventana de oscilación de `backend/src/flowsight/vision/spatial.py` y no dejar de emitir `zone_enter`/`zone_exit`. Hasta T005 en verde.
- [X] T008 [US1] Persistir `showcase_stop` por el cierre ya existente en `backend/src/flowsight/services/scene_metrics.py` y `backend/src/flowsight/worker/video_analysis.py`, en la misma transacción que pasa el trabajo a `completed`. No agregar un kind de exposición. Hasta T006 en verde.

**Checkpoint**: Un análisis falso completado deja la detención de esa sesión. La entrada de zona de vidriera sigue siendo la exposición.

---

## Phase 4: User Story 2 — Armar el funnel con visitas vinculadas (Priority: P1)

**Goal**: Cada local de un análisis de archivo completado tiene las cinco etapas y las cuatro tasas de toda la sesión, sin cambiar las ocho métricas ni el chat.

**Independent Test**: El caso de mano de [quickstart.md](./quickstart.md) coincide. Una segunda lectura no cambia números. Sin etapa anterior, la tasa es no disponible. Sin vidriera, las cuatro etapas que dependen de ella son no disponibles y el paso observado sigue. Una webcam no guarda ni devuelve el funnel.

### Tests for User Story 2

- [X] T009 [P] [US2] Escribir `backend/tests/unit/test_funnel.py` para la función pura de `backend/src/flowsight/vision/funnel.py`, sin SQL. Cubrir [R4](./research.md#r4--conteos-del-funnel-aparte-de-las-ocho-métricas): paso observado incluye a quien luego tiene `store_enter`; exposición exige además `zone_enter` de `window`; detención y atención salen de `showcase_stop` con cortes de 3 y 8 segundos; varias estadías del mismo `track_id` cuentan una vez por etapa; el ingreso vinculado exige un `store_enter` posterior al inicio de la atención más temprana de 8 segundos o más; quien solo pisa `window` suma `excluded_window_only` y no la exposición; sin polígono de vidriera, exposición, detención, atención e ingreso vinculado quedan `no_showcase`; las cuatro tasas usan los códigos de [data-model.md](./data-model.md) y nunca `entry_rate`; etapa anterior en cero deja la tasa no disponible. Las entradas oficiales recibidas no se recalculan. Se cumple atención ≤ detención ≤ exposición ≤ paso observado y ingreso vinculado ≤ atención.
- [X] T010 [P] [US2] Escribir `backend/tests/contract/test_funnel_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml). `GET /sessions/{session_id}/shops/{shop_id}/funnel` devuelve cinco etapas, cuatro tasas, umbrales 3 y 8, `excluded_window_only` y `precision_uncommitted=true`. No acepta `from_seconds` ni `to_seconds`. Otra sesión no devuelve esas filas. Análisis no completado: `409` `result_incomplete`. Webcam: `409` `live_funnel_unavailable` y cero filas de funnel. `GET /sessions/{session_id}/shops/{shop_id}/metrics` sigue sin etapas ni tasas del funnel. `get_session_figures` en `backend/src/flowsight/services/chat.py` no ofrece estas cifras.

### Implementation for User Story 2

- [X] T011 [US2] Crear `backend/src/flowsight/vision/funnel.py`, puro, sin FastAPI ni SQL. Recibe los hechos ya armados y las entradas oficiales ya cerradas. No lee el video ni `trajectory.jsonl`. Hasta T009 en verde.
- [X] T012 [US2] Crear `backend/src/flowsight/services/funnel.py` para persistir y leer `shop_funnels`, `shop_funnel_stages` y `shop_funnel_rates`. Llamarlo desde `backend/src/flowsight/worker/video_analysis.py` en la misma transacción de cierre que `persist_completed_scene`, solo si el origen no es webcam. Guardar umbrales 3 y 8 y `precision_uncommitted=true`.
- [X] T013 [US2] Exponer `GET /sessions/{session_id}/shops/{shop_id}/funnel` en `backend/src/flowsight/api/routes.py` y `backend/src/flowsight/api/schemas.py`, con los `409` de T010. No modificar el cuerpo de `GET /sessions/{session_id}/shops/{shop_id}/metrics`. Hasta T010 en verde.

**Checkpoint**: El caso de mano se lee por el pedido nuevo. Las ocho métricas y el chat mínimo quedan iguales. El funnel es de toda la sesión.

---

## Phase 5: User Story 3 — Leer el funnel en el resultado (Priority: P2)

**Goal**: El analista ve el funnel del local en el resultado de un archivo ya terminado, con los nombres, los umbrales y el aviso de precisión. El tramo no lo recalcula.

**Independent Test**: Una sesión de archivo completada muestra las cinco etapas, las cuatro tasas por par de etapas, los umbrales y el aviso. Cambiar el tramo no vuelve a pedir el funnel. Una webcam no muestra el bloque. La tasa de ingreso existente conserva su nombre.

### Tests for User Story 3

- [X] T014 [P] [US3] Escribir `frontend/tests/FunnelPanel.test.tsx` según [contracts/funnel-ui.md](./contracts/funnel-ui.md). Cubre los cinco nombres visibles, «De paso observado a exposición», «De exposición a detención», «De detención a atención estimada» y «De atención estimada a ingreso vinculado», los umbrales de 3 y 8 segundos, el rótulo de estimación, el aviso «La precisión de estas etapas no está comprometida.», el texto de visitas excluidas cuando `excluded_window_only` es mayor que cero, una tasa no disponible que no se muestra como cero, y la ausencia del nombre «tasa de ingreso» en esas cuatro tasas.

### Implementation for User Story 3

- [X] T015 [US3] Crear el cliente y los tipos de `GET /sessions/{session_id}/shops/{shop_id}/funnel` en `frontend/src/api/funnel.ts`, sin parámetros de tramo.
- [X] T016 [US3] Crear `frontend/src/components/FunnelPanel.tsx` y `frontend/src/components/FunnelPanel.module.css` con el contenido de T014. Las entradas ya cerradas se muestran desde las métricas que la pantalla ya cargó, no desde un segundo cálculo.
- [X] T017 [US3] Montar el panel en `frontend/src/pages/SessionResultsPage.tsx` solo para una sesión que no es webcam y cuyo análisis está completado. Pedir el funnel una vez por local. El efecto que cambia el tramo no debe volver a pedirlo. Una sesión webcam y un análisis incompleto no renderizan el bloque.

**Checkpoint**: El resultado de archivo muestra el funnel de toda la sesión. El tramo sigue filtrando solo hechos y minutos del flujo.

---

## Phase 6: User Story 4 — Contrastar con una observación manual (Priority: P2)

**Goal**: Dejar el lugar donde el equipo anota el contraste de un clip, sin exigir ese clip para la suite.

**Independent Test**: El archivo de contraste existe, clasifica diferencias con el protocolo de specs/001 y no afirma exactitud. La suite de T005, T009, T010 y T014 sigue pudiendo correr sin ese clip. El aviso de precisión permanece en el panel.

### Implementation for User Story 4

- [X] T018 [US4] Crear `specs/010-exposicion-atencion-funnel/validation/contrast.md` para un clip del material elegido, con paso observado, exposición, detención, atención estimada e ingreso vinculado anotados a mano y las diferencias clasificadas como en specs/001 (detección faltante, espuria, pérdida de track, oclusión, duplicado, cruce omitido u otro). Dejar el ensayo en «no ejecutado». No prometer coincidencia. No agregar el clip a pytest, Vitest ni Playwright, y no quitar el aviso de `frontend/src/components/FunnelPanel.tsx`.

**Checkpoint**: Hay dónde escribir el contraste. Las otras historias se validan sin el clip.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Correr la guía de validación sobre lo ya implementado.

- [X] T019 Ejecutar los comandos de [quickstart.md](./quickstart.md) desde `backend/` y `frontend/`. Si un comando no coincide con el nombre real de la prueba, corregir solo `specs/010-exposicion-atencion-funnel/quickstart.md`. No dar por hecho el contraste manual de T018.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: puede empezar ya.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias.
- **User Stories (Phase 3+)**: dependen de Foundational. US2 persiste encima de los hechos de US1. US3 lee el pedido de US2. US4 no bloquea a las demás.
- **Polish (Phase 7)**: después de las historias que se quieran dar por cerradas. T018 puede quedar pendiente sin impedir T019 sobre el resto.

### User Story Dependencies

- **User Story 1 (P1)**: después de Foundational. No depende de otra historia.
- **User Story 2 (P1)**: la función pura de T009 y T011 puede probarse con hechos en memoria después de Foundational. Guardar el funnel en el trabajo y el contrato HTTP dependen de US1.
- **User Story 3 (P2)**: el test de T014 usa una respuesta fija del contrato y puede escribirse en cuanto existe [contracts/funnel-ui.md](./contracts/funnel-ui.md). Montar la pantalla en T017 necesita el cliente y el pedido de US2.
- **User Story 4 (P2)**: después de que el aviso exista en US3. No aporta código de producción.

### Within Each User Story

- La prueba se escribe y falla antes de implementar.
- El modelo de Phase 2 está antes que los servicios.
- La regla pura está antes que la persistencia, y la persistencia antes que el endpoint.
- La historia queda cerrada antes de tratar la siguiente como obligatoria.

### Parallel Opportunities

- T005 y T006 escriben archivos distintos y pueden redactarse juntos después de Phase 2.
- T009 y T010 pueden redactarse juntos. T009 no espera el endpoint.
- T014 puede redactarse junto con T009 y T010 porque solo fija el componente contra el contrato.
- T018 no comparte archivos con el backend.

---

## Parallel Example: User Story 1

```text
T005: backend/tests/unit/test_showcase_stop.py
T006: backend/tests/integration/test_showcase_stop_job.py
```

Después, en orden: T007 en `backend/src/flowsight/vision/events.py` y T008 en el cierre del worker.

## Parallel Example: User Story 2

```text
T009: backend/tests/unit/test_funnel.py
T010: backend/tests/contract/test_funnel_api.py
```

Después, en orden: T011, T012 y T013.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2.
2. Completar Phase 3.
3. Parar y validar US1 con T005 y T006.
4. Recién ahí armar los conteos de US2.

### Incremental Delivery

1. Setup + Foundational dejan el esquema listo sin cambiar las ocho métricas.
2. US1 entrega la detención y conserva la entrada de zona como exposición.
3. US2 entrega el funnel de toda la sesión por el pedido nuevo.
4. US3 lo muestra y deja el tramo quieto.
5. US4 deja el contraste manual fuera de la suite.

### Parallel Team Strategy

1. Todos cierran Setup y Foundational.
2. Una persona sigue US1 y después US2 en el worker.
3. Otra puede redactar T014 y el panel contra el contrato mientras US2 cierra el pedido.
4. El contraste de US4 no se reparte como código.

---

## Notes

- [P] marca archivos distintos, sin depender de una tarea incompleta.
- [US1]–[US4] siguen las historias de `spec.md`.
- Cada historia se puede validar con su prueba propia.
- La prueba tiene que fallar antes de implementar.
- No recalcular el funnel al elegir un tramo.
- No llamar «tasa de ingreso» a ninguna tasa del funnel.
- No mostrar el bloque en webcam ni mientras el análisis no terminó.

## Phase 8: Convergence

- [X] T020 Mostrar junto a «Ingreso vinculado», en `frontend/src/components/FunnelPanel.tsx`, la aclaración de que no es el total de entradas ni una compra, y cubrirla en `frontend/tests/FunnelPanel.test.tsx`. Las entradas oficiales siguen saliendo de las métricas ya cargadas. per FR-014, US3/AC1 (partial)
- [X] T021 Revisar en `backend/src/flowsight/services/funnel.py` la respuesta `metrics_not_generated` para un análisis completado sin filas de funnel: el contrato de `contracts/openapi.yaml` solo admite `no_showcase` como motivo de etapa. Justificar ese caso o dejar de devolver un motivo fuera del contrato. per plan: contracts/openapi.yaml (unrequested)
