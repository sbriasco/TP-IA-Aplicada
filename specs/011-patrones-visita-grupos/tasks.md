---

description: "Lista de tareas de la feature 011: patrones de visita y grupos estimados"
---

# Tasks: Patrones de visita y grupos estimados

**Input**: Documentos de diseño de `/specs/011-patrones-visita-grupos/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #8 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

**Tests**: Se incluyen porque el plan los nombra, [quickstart.md](./quickstart.md) los usa para validar y la constitución pide pruebas de cruces, duplicados, tiempos, aislamiento y métricas. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3, US4).
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno. Las pruebas que migran usan `destructive_database_url()` de `backend/tests/conftest.py`.
- No se agregan dependencias. El detector de la suite sigue siendo `fake`. No se modifica `backend/src/flowsight/vision/ultralytics_tracker.py`. El rol de la vidriera en los hechos sigue siendo `window`.

## Phase 1: Setup

**Purpose**: Confirmar que esta feature no cambia el lock ni el detector.

- [X] T001 Verificar que `backend/pyproject.toml` y `frontend/package.json` no ganan paquetes nuevos y que `backend/src/flowsight/vision/ultralytics_tracker.py` no se modifica. Si [plan.md](./plan.md) ya lo dice, dejar ese archivo quieto.

**Checkpoint**: El alcance sigue siendo la regla nueva en `vision/`, el cierre del análisis de archivo, un pedido nuevo y el bloque en resultados.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0015` y modelos que US1 y US2 leen.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T002 Escribir `backend/tests/integration/test_migration_0015.py` con `destructive_database_url()`. Sobre una base en `0014_shop_funnel`, `upgrade head` crea `visit_pattern_reports`, `visit_area_transitions`, `visit_sequences`, `visit_shop_transitions`, `visit_groups` y `visit_group_members` según [data-model.md](./data-model.md). Reutiliza `scene_zone_role` (`front`, `interior`, `window`) y no agrega un valor. `visit_pattern_reports` es único por `job_id` y guarda `0.08`, `45`, `2`, `0.005` y `precision_uncommitted` verdadero. `patterns_unavailable_reason` admite `no_areas` o null. `group_count` es ≥ 0. Transiciones de área únicas por `(job_id, from_shop_id, from_zone_role, to_shop_id, to_zone_role)` con `track_count` ≥ 1. Cambios de local únicos por `(job_id, from_shop_id, to_shop_id)` con locales distintos. Grupos únicos por `(job_id, ordinal)`, con fin de video posterior o igual al inicio. Miembros únicos por `(group_id, track_id)`. `shop_metrics` no gana códigos. `scene_events`, `shop_funnels` y `trajectory` no cambian de forma. El `downgrade` a `0014` solo se usa como fixture de test y no toca esas tablas.
- [X] T003 Crear `backend/alembic/versions/0015_visit_patterns.py` (`down_revision = 0014_shop_funnel`) que cumpla T002. Los enums nuevos se crean en la misma transacción. No hace falta `autocommit_block` porque no se agrega un valor a un enum ya existente. Correr T002 hasta verde.
- [X] T004 Extender `backend/src/flowsight/db/models.py` con los enums y modelos de T003, con los mismos nombres de restricción. `alembic check` no debe reportar diferencias.

**Checkpoint**: `alembic upgrade head` aplica `0015`. Un análisis de specs/006 y el funnel de specs/010 siguen guardando las mismas cifras.

---

## Phase 3: User Story 1 — Ver cómo se recorre la escena (Priority: P1) 🎯 MVP

**Goal**: Al completar un análisis de archivo, cada visita deja transiciones de áreas, secuencias y cambios de local de toda la sesión. El solape no adelanta el paso. Las ocho métricas y el funnel no cambian.

**Independent Test**: Con pies sintéticos, sin pantalla ni video real: A luego B cuenta una transición y una secuencia; el pie en dos áreas a la vez no suma paso; volver a la misma área no la repite; repetir el recorrido no aumenta el conteo de esa visita; más de 1 segundo fuera o sin seguimiento abre otra secuencia; el cambio de local solo aparece si las dos áreas seguidas son de locales distintos.

### Tests for User Story 1

- [X] T005 [P] [US1] Escribir en `backend/tests/unit/test_visit_patterns.py` los casos de áreas de la función pura de `backend/src/flowsight/vision/visit_patterns.py`, sin base de datos y sin leer `trajectory.jsonl`. Cubrir [R1](./research.md#r1--un-área-es-un-polígono-ya-configurado) y [R3](./research.md#r3--qué-se-guarda): salir de un área y quedar en otra dentro de 1 segundo de video anota esa transición y esa secuencia; estar en las dos a la vez no la anota; si la primera observación cae en varias áreas, la secuencia empieza cuando el pie queda en una sola; volver a la misma área no la repite; el mismo identificador repite el par y la cadena y sigue contando uno; una ausencia de más de 1 segundo, o más de 1 segundo fuera de todas las áreas, cierra la secuencia y la siguiente no se pega; una ausencia menor no la cierra y no inventa posiciones; dos áreas de distinto `shop_id` suman un cambio de local y dos del mismo local no; sin ningún polígono, los patrones quedan no disponibles con `no_areas` y no hay filas inventadas; con polígonos y sin pasos, las listas existen vacías. El rol guardado es `front`, `interior` o `window`.
- [X] T006 [P] [US1] Escribir `backend/tests/integration/test_visit_patterns_job.py` con el detector falso. Al completar un `video_analysis` que no es webcam, las transiciones, secuencias y cambios de local quedan en las tablas de esa sesión y de ninguna otra. Un trabajo `failed` o `cancelled` no los presenta como resultado completo. Una webcam no escribe `visit_pattern_reports`. `shop_metrics` conserva sus ocho códigos y el funnel de specs/010 conserva sus etapas. Borrar o cambiar `trajectory.jsonl` después del cierre no cambia esas filas.

### Implementation for User Story 1

- [X] T007 [US1] Crear `backend/src/flowsight/vision/visit_patterns.py`, puro, sin FastAPI ni SQL. Recibe fotograma, fps y los mismos pies que `SceneEventRecorder.observe` ya usa. Implementar solo transiciones, secuencias y cambios de local, con el estado por identificador y sin guardar un pie por fotograma. No modificar `backend/src/flowsight/vision/events.py` ni `backend/src/flowsight/vision/spatial.py`. Hasta T005 en verde.
- [X] T008 [US1] Crear `backend/src/flowsight/services/visit_patterns.py` para persistir `visit_pattern_reports`, `visit_area_transitions`, `visit_sequences` y `visit_shop_transitions`. Llamarlo desde `backend/src/flowsight/worker/video_analysis.py` en la misma transacción que `persist_shop_funnel`, antes de pasar el trabajo a `completed`, y no llamarlo si el origen es webcam. Hasta T006 en verde.

**Checkpoint**: Un análisis falso completado deja los recorridos de esa sesión. Las ocho métricas y el funnel quedan iguales.

---

## Phase 4: User Story 2 — Estimar quiénes iban juntos (Priority: P1)

**Goal**: El mismo cierre deja los grupos estimados. Hacen falta cercanía, dirección y 2 segundos de video. Una visita ocupa un solo grupo por instante. El pedido nuevo los lee junto con los patrones.

**Independent Test**: Con posiciones conocidas, dos visitas que cumplen 0,08 del ancho, 45 grados y 2 segundos forman un grupo estimado. Una quieta, una tercera lejos y un acercamiento de menos de 2 segundos no entran. El rótulo dice que es una estimación. Cero grupos queda disponible.

### Tests for User Story 2

- [X] T009 [P] [US2] Extender `backend/tests/unit/test_visit_patterns.py` con los casos de grupo de [R4](./research.md#r4--dirección-y-visita-quieta) y [R5](./research.md#r5--quiénes-forman-el-grupo). Dos visitas a no más de 0,08 del ancho, con desplazamiento de al menos 0,005 del ancho y ángulo de a lo sumo 45 grados, durante al menos 2 segundos de video, forman un episodio `group_estimate`. Un pie con desplazamiento menor que 0,005 del ancho no entra. Una tercera lejos de alguna no entra. Menos de 2 segundos no confirma. Si el video termina después de los 2 segundos, el fin es el último fotograma observado; antes, no hay episodio. Una visita que cumple dos conjuntos en el mismo instante queda en el que empezó antes y, si empatan, en el de más integrantes. Si también empatan en tamaño, queda en el conjunto de identificador menor. Un conjunto que se desarma y vuelve a cumplir otros 2 segundos es otro episodio. Sin polígonos, los grupos siguen disponibles y cero es un conteo, no `no_areas`.
- [X] T010 [P] [US2] Escribir `backend/tests/contract/test_visit_patterns_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml). `GET /sessions/{session_id}/visit-patterns` devuelve transiciones, secuencias, cambios de local, grupos, `group_count`, umbrales `0.08`, `45` y `2`, y `precision_uncommitted` verdadero. No acepta `shop_id`, `from_seconds` ni `to_seconds`. Otra sesión no devuelve esas filas. Análisis no completado: `409` `result_incomplete`. Webcam: `409` `live_patterns_unavailable` y cero filas. Sin polígonos, `patterns_unavailable_reason` es `no_areas` y los grupos siguen. `GET /sessions/{session_id}/shops/{shop_id}/metrics` y `GET /sessions/{session_id}/shops/{shop_id}/funnel` no cambian de cuerpo. `get_session_figures` en `backend/src/flowsight/services/chat.py` no ofrece estas cifras.

### Implementation for User Story 2

- [X] T011 [US2] Agregar en `backend/src/flowsight/vision/visit_patterns.py` el grafo de pares, los episodios y el desempate de [R5](./research.md#r5--quiénes-forman-el-grupo). La dirección es el desplazamiento en píxeles desde la observación anterior. No leer `backend/src/flowsight/services/position_samples.py` ni `trajectory.jsonl`. Hasta T009 en verde.
- [X] T012 [US2] Persistir `visit_groups` y `visit_group_members` desde `backend/src/flowsight/services/visit_patterns.py`, con `group_count` y `groups_availability=available` cuando la escena del análisis existe. Un episodio guarda inicio, fin e integrantes. Completar la llamada que T008 ya dejó en `backend/src/flowsight/worker/video_analysis.py`.
- [X] T013 [US2] Exponer `GET /sessions/{session_id}/visit-patterns` en `backend/src/flowsight/api/routes.py` y `backend/src/flowsight/api/schemas.py`, con los `409` de T010. No modificar el cuerpo de métricas ni el de funnel. Hasta T010 en verde.

**Checkpoint**: El caso de mano de grupos se lee por el pedido nuevo. El chat mínimo y el funnel quedan iguales.

---

## Phase 5: User Story 3 — Leer patrones y grupos en el resultado (Priority: P2)

**Goal**: El analista ve, en el resultado de un archivo ya terminado, las transiciones, las secuencias, los cambios de local y los grupos de toda la sesión. El tramo y el local elegido no los recalculan.

**Independent Test**: Una sesión de archivo completada muestra esas listas, los tres umbrales, el rótulo de estimación y el aviso de precisión. Sin áreas, los patrones dicen que no hay áreas y los grupos siguen. Cero grupos se lee como cero. Cambiar el tramo o el local no vuelve a pedir el bloque. Una webcam no lo muestra.

### Tests for User Story 3

- [X] T014 [P] [US3] Escribir `frontend/tests/VisitPatternsPanel.test.tsx` según [contracts/visit-patterns-ui.md](./contracts/visit-patterns-ui.md). Cubre transiciones con nombre de local y rol (vidriera para `window`), secuencias, cambios de local, integrantes por identificador, inicio y fin en segundos de video, el texto de estimación que no afirma una relación real, los umbrales de ocho centésimas, 45 grados y 2 segundos, el aviso «La precisión de los patrones y de los grupos estimados no está comprometida.», «No hay áreas.» cuando el motivo es `no_areas` sin reemplazar esas listas por cero, y «0 grupos estimados» cuando el conteo es cero y los grupos están disponibles.
- [X] T015 [P] [US3] Extender `frontend/tests/SessionResultsPage.test.tsx` para que una sesión de archivo completada pida `GET /sessions/{session_id}/visit-patterns` una sola vez. Cambiar el tramo o el local no dispara otro pedido. Una sesión webcam y un análisis incompleto no muestran el bloque.

### Implementation for User Story 3

- [X] T016 [US3] Crear el cliente y los tipos de `GET /sessions/{session_id}/visit-patterns` en `frontend/src/api/visitPatterns.ts`, sin parámetros de tramo ni de local.
- [X] T017 [US3] Crear `frontend/src/components/VisitPatternsPanel.tsx` y `frontend/src/components/VisitPatternsPanel.module.css` con el contenido de T014. Los nombres de local salen de los locales que la pantalla ya cargó.
- [X] T018 [US3] Montar el panel en `frontend/src/pages/SessionResultsPage.tsx` solo para una sesión que no es webcam y cuyo análisis está completado. Pedir el recurso una vez por sesión. El efecto que cambia el tramo o el local no debe volver a pedirlo. Hasta T014 y T015 en verde.

**Checkpoint**: El resultado de archivo muestra los patrones y los grupos de toda la sesión. El tramo sigue filtrando solo hechos y minutos del flujo.

---

## Phase 6: User Story 4 — Contrastar con una observación manual (Priority: P2)

**Goal**: Dejar el lugar donde el equipo anota el contraste de un clip, sin exigir ese clip para la suite.

**Independent Test**: El archivo de contraste existe, clasifica diferencias con el protocolo de specs/001 y no afirma exactitud. La suite de T005, T009, T010 y T014 sigue pudiendo correr sin ese clip. El aviso de precisión permanece en el panel.

### Implementation for User Story 4

- [X] T019 [US4] Crear `specs/011-patrones-visita-grupos/validation/contrast.md` para un clip del material elegido, con transiciones entre áreas, cambios de local y grupos estimados anotados a mano y las diferencias clasificadas como en specs/001 (detección faltante, espuria, pérdida de track, oclusión, duplicado, cruce omitido u otro). Dejar el ensayo en «no ejecutado». No prometer coincidencia. No agregar el clip a pytest, Vitest ni Playwright, y no quitar el aviso de `frontend/src/components/VisitPatternsPanel.tsx`.

**Checkpoint**: Hay dónde escribir el contraste. Las otras historias se validan sin el clip.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Correr la guía de validación sobre lo ya implementado.

- [X] T020 Ejecutar los comandos de [quickstart.md](./quickstart.md) desde `backend/` y `frontend/`. Si un comando no coincide con el nombre real de la prueba, corregir solo `specs/011-patrones-visita-grupos/quickstart.md`. No dar por hecho el contraste manual de T019.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: puede empezar ya.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias.
- **User Stories (Phase 3+)**: dependen de Foundational. US2 agrega grupos sobre el módulo y el cierre de US1. US3 lee el pedido de US2. US4 no bloquea a las demás.
- **Polish (Phase 7)**: después de las historias que se quieran dar por cerradas. T019 puede quedar pendiente sin impedir T020 sobre el resto.

### User Story Dependencies

- **User Story 1 (P1)**: después de Foundational. No depende de otra historia.
- **User Story 2 (P1)**: los casos de T009 pueden escribirse con pies en memoria después de Foundational. La implementación de T011 y T012 toca los mismos archivos que US1, así que sigue a T007 y T008. El contrato HTTP de T013 necesita las filas de ambos.
- **User Story 3 (P2)**: T014 y T015 usan el contrato de pantalla y pueden escribirse en cuanto existen [contracts/visit-patterns-ui.md](./contracts/visit-patterns-ui.md). Montar la pantalla en T018 necesita el cliente y el pedido de US2.
- **User Story 4 (P2)**: después de que el aviso exista en US3. No aporta código de producción.

### Within Each User Story

- La prueba se escribe y falla antes de implementar.
- El modelo de Phase 2 está antes que los servicios.
- La regla pura está antes que la persistencia, y la persistencia antes que el endpoint.
- La historia queda cerrada antes de tratar la siguiente como obligatoria.

### Parallel Opportunities

- T005 y T006 escriben archivos distintos y pueden redactarse juntos después de Phase 2.
- T009 y T010 pueden redactarse juntos. T009 no espera el endpoint.
- T014 y T015 pueden redactarse juntos, y también junto con T009 y T010, porque solo fijan la pantalla contra el contrato.
- T019 no comparte archivos con el backend.

---

## Parallel Example: User Story 1

```text
T005: backend/tests/unit/test_visit_patterns.py
T006: backend/tests/integration/test_visit_patterns_job.py
```

Después, en orden: T007 en `backend/src/flowsight/vision/visit_patterns.py` y T008 en el cierre del worker.

## Parallel Example: User Story 2

```text
T009: backend/tests/unit/test_visit_patterns.py
T010: backend/tests/contract/test_visit_patterns_api.py
```

Después, en orden: T011, T012 y T013.

## Parallel Example: User Story 3

```text
T014: frontend/tests/VisitPatternsPanel.test.tsx
T015: frontend/tests/SessionResultsPage.test.tsx
```

Después, en orden: T016, T017 y T018.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2.
2. Completar Phase 3.
3. Parar y validar US1 con T005 y T006.
4. Recién ahí estimar los grupos de US2.

### Incremental Delivery

1. Setup + Foundational dejan el esquema listo sin cambiar las ocho métricas ni el funnel.
2. US1 entrega recorridos, secuencias y cambios de local.
3. US2 entrega los grupos estimados y el pedido de toda la sesión.
4. US3 los muestra y deja el tramo y el local quietos.
5. US4 deja el contraste manual fuera de la suite.

### Parallel Team Strategy

1. Todos cierran Setup y Foundational.
2. Una persona sigue US1 y después US2 en `visit_patterns.py` y en el worker.
3. Otra puede redactar T014, T015 y el panel contra el contrato mientras US2 cierra el pedido.
4. El contraste de US4 no se reparte como código.

---

## Notes

- [P] marca archivos distintos, sin depender de una tarea incompleta.
- [US1]–[US4] siguen las historias de `spec.md`.
- Cada historia se puede validar con su prueba propia.
- La prueba tiene que fallar antes de implementar.
- No calcular patrones ni grupos desde `trajectory.jsonl`.
- No sumar una transición mientras el pie sigue en las dos áreas.
- No mostrar el bloque en webcam ni mientras el análisis no terminó.
- No agregar estas cifras a `get_session_figures` ni a las ocho métricas.
