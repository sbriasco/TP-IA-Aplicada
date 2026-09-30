---

description: "Lista de tareas de la feature 007: dashboard e historial"
---

# Tasks: Dashboard e historial

**Input**: Documentos de diseño de `/specs/007-dashboard-historial/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [contracts/dashboard-ui.md](./contracts/dashboard-ui.md), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #15 (Epic #1). US1 = #65, US2 = #66, US3 = #67. Bajo #65: #106–#112 (T002–T008). Bajo #66: #113 (T001), #114–#118 (T009–T013) y #119 (T017). Bajo #67: #120–#122 (T014–T016).

**Tests**: Se incluyen porque el plan y [quickstart.md](./quickstart.md) los nombran, y la constitución pide pruebas del recorrido. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3).
- No hay migración. No se toca `GET /sessions` ni el pedido de métricas de specs/006.
- No se agregan paquetes salvo Recharts `3.10.1`. El detector de la suite sigue siendo `fake`.

---

## Phase 1: Setup

**Purpose**: Dejar instalada la única dependencia nueva, ya elegida en las decisiones técnicas.

- [x] T001 Instalar `recharts@3.10.1` y dejarlo fijado en `frontend/package.json` y `frontend/package-lock.json`. No agregar otro paquete.

**Checkpoint**: `frontend/package.json` depende de Recharts 3.10.1 y de ninguna librería de gráficos más.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: La ruta de resultados existe antes de que el historial enlace y antes de que el tablero la llene.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [x] T002 Extender `frontend/tests/navigation.test.ts` para que `/sessions/s1/results` resuelva `{ name: "results", sessionId: "s1" }`, con barra final igual, y para que `/sessions/s1/results/extra` siga en `not_found`. El detalle y el editor no cambian. La prueba debe fallar antes de T003.
- [x] T003 Hacer pasar T002 en `frontend/src/navigation.ts` y en `frontend/src/App.tsx`. Crear `frontend/src/pages/SessionResultsPage.tsx` que muestre el título Resultados y el id de la sesión, sin indicadores ni gráfico.

**Checkpoint**: `/sessions/{id}/results` abre una pantalla vacía de resultados. `/sessions/{id}` sigue siendo la carga y la escena.

---

## Phase 3: User Story 1 — Historial de sesiones procesadas (Priority: P1) · #65 🎯 MVP

**Goal**: Ver las sesiones ya analizadas y abrir la de resultados, aunque el video no esté en este equipo.

**Independent Test**: Una sesión sin análisis no aparece. Una completada muestra nombre, archivo, estado, `finished_at` y el número de la versión guardada en ese análisis. Una fallida muestra el motivo y no se presenta como resultado final. Sin el archivo, el frame de referencia sigue visible.

### Tests for User Story 1

- [x] T004 [P] [US1] Escribir `backend/tests/contract/test_processed_sessions_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml). Usa `destructive_database_url()` como `backend/tests/contract/test_scene_metrics_api.py`. Cubre: sesión sin análisis ausente; completada con nombre, `video_filename`, estado, `finished_at` y `version_number` de la versión del análisis, no de una versión posterior de la cámara; fallida con `failure_message` y `result_complete` false; otra sesión no entra en esa fila; `GET /sessions` no gana campos. La prueba debe fallar antes de T005.
- [x] T005 [P] [US1] Escribir `frontend/tests/ProcessedSessionsSection.test.tsx`. Con datos de prueba, la tabla muestra nombre, video, estado, fecha de procesamiento y versión; una fallida muestra el motivo y no el texto de resultado final; la lista vacía dice que no hay sesiones procesadas; el enlace de la fila apunta a `/sessions/{id}/results`. No se quita el alta de video. La prueba debe fallar antes de T007.

### Implementation for User Story 1

- [x] T006 [US1] Crear `backend/src/flowsight/services/processed_sessions.py` y el `GET /processed-sessions` en `backend/src/flowsight/api/routes.py` y `backend/src/flowsight/api/schemas.py`, según [data-model.md](./data-model.md). El análisis es el más reciente por `created_at`. La disponibilidad del video es la que ya calcula el detalle de sesión. Hasta T004 en verde.
- [x] T007 [US1] Crear `frontend/src/api/processedSessions.ts`, `frontend/src/pages/ProcessedSessionsSection.tsx` y `frontend/src/pages/ProcessedSessionsSection.module.css`. Montar la sección desde `frontend/src/pages/SessionsPage.tsx` sin reemplazar el alta. Hasta T005 en verde.
- [x] T008 [US1] En `frontend/src/pages/SessionResultsPage.tsx` y `frontend/tests/SessionResultsPage.test.tsx`, si la disponibilidad es `missing` o `mismatch`, mostrar el frame de referencia ya servido por la sesión y el texto de que el archivo no está en este equipo. Los resultados no se ocultan. No dibujar el mapa ni los ocho indicadores.

**Checkpoint**: El historial lista solo sesiones analizadas y abrir una fila llega a `/sessions/{id}/results`.

---

## Phase 4: User Story 2 — Indicadores y gráficos (Priority: P1) · #66

**Goal**: En una sesión completada, los ocho indicadores son los de toda la sesión. El tramo solo filtra minutos y hechos. En curso se ven solo tres cifras parciales.

**Independent Test**: Los ocho indicadores coinciden con el pedido de métricas. Mover el tramo no los cambia y no parte un minuto de 60 s. En curso hay entradas, salidas y ocupación visible con el texto «parcial», y no las otras cinco. Una tasa no disponible no se muestra como cero.

### Tests for User Story 2

- [x] T009 [P] [US2] Escribir `frontend/tests/visibleBuckets.test.ts`. Un minuto `[0, 60)` se muestra entero si el tramo es `[50, 70)`. Un minuto que no se solapa no se muestra. La función no parte el minuto ni modifica los ocho indicadores. La prueba debe fallar antes de T010.
- [x] T010 [P] [US2] Extender `frontend/tests/SessionResultsPage.test.tsx`. Completado: los ocho rótulos, «estimación de visitas», «visible», «observable» y «no disponible» en texto, no solo color. El gráfico usa los minutos de T009. Cambiar el tramo no vuelve a pedir las métricas y sí filtra los hechos. En curso: solo entradas, salidas y ocupación visible, con «parcial». Fallido: el motivo y ningún indicador de los ocho. La prueba debe fallar antes de T012.

### Implementation for User Story 2

- [x] T011 [US2] Crear `frontend/src/flow/visibleBuckets.ts` con la regla de [data-model.md](./data-model.md). Hasta T009 en verde.
- [x] T012 [US2] Crear `frontend/src/api/metrics.ts` para el pedido de métricas, los hechos (`from_seconds`, `to_seconds`) y `GET /jobs/{id}/measures`. Completar `frontend/src/pages/SessionResultsPage.tsx` y `frontend/src/pages/SessionResultsPage.module.css` según [contracts/dashboard-ui.md](./contracts/dashboard-ui.md). El gráfico de barras usa Recharts. El local inicial es el primero por `position`. El horario pico es el de la respuesta, no el máximo de los minutos filtrados. Hasta T010 en verde.
- [x] T013 [US2] Escribir `frontend/e2e/session-results.spec.ts` y engancharlo al recorrido que ya corre `frontend/e2e/run-e2e.mjs`. Abre el historial, entra a una sesión completada y comprueba que los indicadores visibles coinciden con el pedido de métricas. Una segunda sesión no se mezcla. Con el video ausente, el frame sigue. El mapa puede no estar.

**Checkpoint**: El tablero de una sesión completada no recalcula. El de una en curso no inventa las cinco métricas que todavía no existen.

---

## Phase 5: User Story 3 — Mapa de calor (Priority: P2) · #67

**Goal**: Dibujar la muestra de posiciones sobre el frame. Si no hay muestra, explicarlo sin tapar los indicadores.

**Independent Test**: Con muestra, los pies se ven sobre el frame de referencia. Sin el archivo en este equipo, el estado vacío lo dice y los indicadores siguen. El recorrido de T013 pasa igual sin esta historia.

### Tests for User Story 3

- [x] T014 [P] [US3] Escribir `backend/tests/contract/test_position_samples_api.py`. `GET /jobs/{id}/position-samples` devuelve pies normalizados del JSONL de specs/005, sin métricas. Si el archivo no está, `availability` es `unavailable` y el estado HTTP es 200. Si el análisis no existe, 404. La prueba debe fallar antes de T015.

### Implementation for User Story 3

- [x] T015 [US3] Crear `backend/src/flowsight/services/position_samples.py` y el GET en `backend/src/flowsight/api/routes.py` y `backend/src/flowsight/api/schemas.py`. Lee el JSONL ya escrito. No calcula métricas. Hasta T014 en verde.
- [x] T016 [US3] Crear `frontend/src/components/PositionHeatmap.tsx`, `frontend/src/components/PositionHeatmap.module.css` y `frontend/tests/PositionHeatmap.test.tsx`. Montarlo desde `frontend/src/pages/SessionResultsPage.tsx` sobre el frame de referencia. Sin muestra, el texto explica el vacío y no oculta los indicadores.

**Checkpoint**: #65 y #66 siguen verdes si esta historia no se entrega.

---

## Phase 6: Polish

**Purpose**: Correr la validación del quickstart sobre lo que quedó implementado.

- [x] T017 Correr los comandos de [quickstart.md](./quickstart.md). Si el mapa no está, el recorrido de historial e indicadores igual tiene que pasar. No anotar una medición nueva del detector.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: puede empezar ya. La necesita US2.
- **Foundational (Phase 2)**: bloquea a las tres historias.
- **US1 (Phase 3)**: después de Phase 2. No depende de US2 ni de US3.
- **US2 (Phase 4)**: después de Phase 1, Phase 2 y US1, porque completa la misma pantalla de resultados.
- **US3 (Phase 5)**: después de Phase 2. Puede esperar a US2 para montar el mapa en la pantalla ya armada. No bloquea el cierre de US1 ni de US2.
- **Polish (Phase 6)**: después de US1 y US2. US3 es opcional para este cierre.

### User Story Dependencies

- **US1 (P1)**: historial y apertura. MVP.
- **US2 (P1)**: indicadores sobre la pantalla que US1 abre.
- **US3 (P2)**: mapa. El quickstart declara que el recorrido vale sin él.

### Within Each User Story

- La prueba se escribe y falla antes de la implementación que la pone verde.
- El cliente HTTP y la pantalla van después del contrato que consumen.

### Parallel Opportunities

- T004 y T005 pueden escribirse a la vez.
- T009 puede escribirse en paralelo con T004 y T005, porque es otro archivo, pero no se implementa hasta Phase 4.
- T014 puede escribirse en paralelo con las pruebas de US2. Su implementación espera a que exista la pantalla de US2 si se monta ahí.

### Parallel Example: User Story 1

```text
T004 test_processed_sessions_api.py
T005 ProcessedSessionsSection.test.tsx
luego T006 el GET
luego T007 la sección
luego T008 el frame cuando falta el video
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 y Phase 2.
2. Phase 3 (#65).
3. Parar y correr `backend/tests/contract/test_processed_sessions_api.py` y `frontend/tests/ProcessedSessionsSection.test.tsx`.

### Incremental Delivery

1. US1 deja el historial y la apertura.
2. US2 deja los indicadores y el gráfico, sin recalcular el tramo.
3. US3 deja el mapa si entra en el plazo. Si no entra, US1 y US2 igual se dan por válidas.

---

## Notes

- [P] = archivos distintos, sin depender de una tarea incompleta.
- Las pruebas se escriben primero y tienen que fallar antes de la implementación.
- No commitear desde estas tareas: el cierre lo hace quien pide el commit.
