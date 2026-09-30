---

description: "Lista de tareas de la feature 006: eventos espaciales, métricas y persistencia"
---

# Tasks: Eventos espaciales, métricas y persistencia

**Input**: Documentos de diseño de `/specs/006-eventos-metricas/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #14 (Epic #1). US1 = #61, US2 = #62, US3 = #63, US4 = #64. Tareas #99–#105 bajo #61, #94–#96 bajo #62, #97–#98 bajo #63, #92–#93 bajo #64.

**Tests**: Se incluyen porque el plan los exige y la constitución pide pruebas de cruces, duplicados, tiempos, aislamiento y métricas. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3, US4).
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno. Las pruebas que migran usan `destructive_database_url()` de `backend/tests/conftest.py`.
- No se agregan dependencias. El detector de la suite sigue siendo `fake`.

---

## Phase 1: Setup

**Purpose**: Confirmar que esta feature no cambia el lock ni el detector.

- [x] T001 Verificar que `backend/pyproject.toml` no gana paquetes nuevos y que `backend/src/flowsight/vision/ultralytics_tracker.py` no se modifica en esta feature. Anotarlo en `specs/006-eventos-metricas/plan.md` solo si hiciera falta; si ya lo dice, dejar el archivo quieto.

**Checkpoint**: El alcance sigue siendo backend, sin peso YOLO y sin pantalla nueva.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0005` y modelos que todas las historias leen.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [x] T002 Escribir `backend/tests/integration/test_migration_0005.py` con `destructive_database_url()`. Sobre una base en `0004_video_analysis`, `upgrade head` crea `scene_events`, `shop_metrics` y `traffic_buckets` según [data-model.md](./data-model.md): enums de `kind`, `zone_role`, `code`, `availability` y `label`; UNIQUE de métricas `(job_id, shop_id, code)`; índice `(session_id, shop_id, video_timestamp_seconds)` en hechos; `value` nulo si y solo si `availability=unavailable`. No altera columnas de `analysis_measures`. El `downgrade` a `0004` solo se usa como fixture de test.
- [x] T003 Crear `backend/alembic/versions/0005_scene_metrics.py` (`down_revision = 0004_video_analysis`) que cumpla T002. Los enums nuevos usan `op.get_context().autocommit_block()` cuando PostgreSQL lo exija. El `downgrade` borra las tres tablas y no toca `analysis_measures` ni `line_crossings`. Correr T002 hasta verde.
- [x] T004 Extender `backend/src/flowsight/db/models.py` con los modelos y enums de T003, mismos nombres de restricción. `alembic check` no debe reportar diferencias.

**Checkpoint**: `alembic upgrade head` aplica `0005`. Un análisis de specs/005 sigue guardando las tres medidas oficiales.

---

## Phase 3: User Story 1 — Hechos de zona y línea (Priority: P1) · #61 🎯 MVP

**Goal**: Al completar un análisis, existen hechos de zona, paso, entrada, salida y permanencia frontal, sin una fila por fotograma.

**Independent Test**: Con el detector falso, oscilación no confirma entrada; un identificador que desaparece no genera salida ni permanencia; el interior no genera permanencia; un cruce del tramo dibujado sí genera `store_enter` ligado al cruce confirmado.

### Tests for User Story 1

- [x] T005 [P] [US1] Escribir `backend/tests/unit/test_scene_events.py`. Cubre, sin base de datos: cruce del segmento en el sentido de entrada → `store_enter`; el opuesto → `store_exit`; prolongación de la línea sin intersección de segmentos → nada; ida y vuelta dentro de 10 fotogramas → ningún hecho confirmado; pie que entra y sale de la zona frontal sin perderse → `dwell` con `duration_seconds` = diferencia de instantes de video; desaparición del identificador dentro de la zona frontal → ni `dwell` ni `store_exit`; pie solo en interior → `zone_enter`/`zone_exit` posibles y ningún `dwell`; paso = pie en frontal sin `store_enter`.

### Implementation for User Story 1

- [x] T006 [US1] Crear `backend/src/flowsight/vision/events.py`, puro, sin FastAPI ni SQL. Reutiliza `flowsight.scene.geometry` y la ventana `OSCILLATION_MAX_FRAMES` de `backend/src/flowsight/vision/spatial.py`. No vuelve a contar entradas oficiales. Hasta T005 en verde.
- [x] T007 [US1] En `backend/src/flowsight/worker/video_analysis.py`, alimentar T006 con el pie de cada fotograma. Al pasar a `completed`, persistir los hechos en `scene_events` en la misma transacción del cierre. `store_enter` y `store_exit` apuntan al `line_crossings` confirmado. Si el trabajo queda `failed` o `cancelled`, no quedan hechos consultables como resultado completo. No leer `trajectory.jsonl`.

**Checkpoint**: Un `video_analysis` falso completado deja hechos de esa sesión y de ninguna otra. El JSONL sigue siendo la muestra cada 5 fotogramas y no es la fuente de los hechos.

---

## Phase 4: User Story 2 — Ocho métricas (Priority: P1) · #62

**Goal**: Cada local de un análisis completado tiene las ocho métricas, el flujo de 60 s y el horario pico, alineados con los números oficiales.

**Independent Test**: El caso de mano de [quickstart.md](./quickstart.md) coincide. Una segunda pasada no cambia números. Sin pasos, la tasa es no disponible. Sin estadías cerradas, media y mediana son no disponibles.

### Tests for User Story 2

- [x] T008 [P] [US2] Escribir `backend/tests/unit/test_shop_metrics.py` según [R3](./research.md#r3--las-ocho-métricas-y-el-horario-pico). Tráfico = identificadores distintos con pie en la zona frontal. Cada uno cuenta en un solo intervalo de 60 s, el de su primer pie. La suma de intervalos es el tráfico. Empate de pico → menor `bucket_index`. Video de menos de 60 s → un intervalo. Tasa = entradas oficiales / pasos. Esas entradas, salidas y ocupación visible son los enteros recibidos, no un recálculo. Permanencia = media y mediana en segundos de video de los `dwell` frontales.

### Implementation for User Story 2

- [x] T009 [US2] Crear `backend/src/flowsight/vision/metrics.py`, puro. Hasta T008 en verde.
- [x] T010 [US2] Crear `backend/src/flowsight/services/scene_metrics.py`. Al completar, copia `entries`, `exits` y `visible_occupancy` desde `analysis_measures` (`partial=false`) hacia `shop_metrics` y escribe el resto con T009. No hace `UPDATE` del valor oficial. Un trabajo ya completado antes de esta feature no se rellena solo.

**Checkpoint**: Las tres medidas oficiales no cambian de valor. `shop_metrics` las repite y agrega las otras cinco más el flujo.

---

## Phase 5: User Story 3 — Consulta (Priority: P1) · #63

**Goal**: Tablero y chat futuro leen las mismas cifras por sesión, local e intervalo. Un análisis incompleto no se presenta como final.

**Independent Test**: El GET de métricas coincide con `/jobs/{id}/measures` en las tres oficiales. Otra sesión no ve los hechos. Cancelado o fallido responde `409` `result_incomplete`. El intervalo es semiabierto.

### Tests for User Story 3

- [x] T011 [P] [US3] Escribir `backend/tests/contract/test_scene_metrics_api.py` y extender `backend/tests/integration/test_scene_metrics_job.py` según [contracts/openapi.yaml](./contracts/openapi.yaml) y [quickstart.md](./quickstart.md). `GET /sessions` no embebe métricas. `GET /sessions/{session_id}/shops/{shop_id}/metrics` trae ocho medidas, `flow` y `peak`. `GET /sessions/{session_id}/events` filtra `shop_id` y `from_seconds <= t < to_seconds`. Local de otra sesión → `404`. Análisis no completado → `409` con `result_incomplete`.

### Implementation for User Story 3

- [x] T012 [US3] Agregar los esquemas de [contracts/openapi.yaml](./contracts/openapi.yaml) en `backend/src/flowsight/api/schemas.py` y los dos GET en `backend/src/flowsight/api/routes.py`, leyendo solo por `backend/src/flowsight/services/scene_metrics.py`. Sin SQL generado ni llamada al modelo. Hasta T011 en verde.

**Checkpoint**: La consulta de dos sesiones no mezcla filas. El listado de sesiones sigue siendo el de specs/002.

---

## Phase 6: User Story 4 — Contraste manual (Priority: P2) · #64

**Goal**: Queda escrito cómo contrastar un clip real, sin bloquear la suite.

**Independent Test**: La suite de T005, T008 y T011 pasa sin el clip. `validation/README.md` pide entradas, salidas y pasos contados a mano y no promete igualdad.

- [x] T013 [US4] Crear `specs/006-eventos-metricas/validation/README.md` con el protocolo de diferencias del experimento 001 (entradas, salidas y pasos). No inventar un conteo ni un `reference-run`. No agregar el clip al repositorio.

**Checkpoint**: El recorrido de prueba no exige el contraste manual.

---

## Phase 7: Polish

- [x] T014 Correr desde `backend/` los tres comandos de [quickstart.md](./quickstart.md) (`test_scene_events.py`, `test_shop_metrics.py`, `test_migration_0005.py`, `test_scene_metrics_job.py`, `test_scene_metrics_api.py`) y dejar la suite de esta feature en verde. No afirmar el clip real.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: arranca ya.
- **Foundational (Phase 2)**: bloquea todas las historias.
- **US1 (Phase 3)**: después de Phase 2. No depende de US2 ni US3.
- **US2 (Phase 4)**: después de US1, porque las métricas leen hechos y oficiales.
- **US3 (Phase 5)**: después de US2, porque la consulta lee `shop_metrics`.
- **US4 (Phase 6)**: después de US2, en paralelo con US3 (otro archivo).
- **Polish (Phase 7)**: al final.

### Parallel Opportunities

- T005 puede escribirse mientras T004 termina, pero no pasa hasta existir `events.py`.
- T008 puede escribirse en paralelo con T007 (archivo distinto) y no pasa hasta T009.
- T013 puede hacerse en paralelo con T012.

### Parallel Example: User Story 1

```text
T005 test_scene_events.py
luego T006 events.py
luego T007 video_analysis.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 y Phase 2.
2. Phase 3 (US1, #61).
3. Parar y correr `backend/tests/unit/test_scene_events.py`.

### Incremental Delivery

1. US1 deja hechos.
2. US2 deja las ocho métricas.
3. US3 las publica.
4. US4 solo documenta el contraste manual.

---

## Notes

- [P] = archivos distintos, sin depender de una tarea incompleta.
- Las pruebas se escriben primero y tienen que fallar antes de la implementación.
- No commitear desde estas tareas: el cierre lo hace quien pide el commit.
