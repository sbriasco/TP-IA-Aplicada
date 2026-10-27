---

description: "Lista de tareas de la feature 013: comparaciones e insights"
---

# Tasks: Comparaciones e insights

**Input**: Documentos de diseño de `/specs/013-comparaciones-insights/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #10 (Epic #3).

**Tests**: Se incluyen porque [plan.md](./plan.md) y [quickstart.md](./quickstart.md) los nombran y la constitución pide pruebas de aislamiento y métricas. Dentro de cada historia, la prueba se escribe primero y debe fallar antes de implementar.

**Organization**: Tareas por User Story. Rutas relativas a la raíz del repo. Sin migración. Sin paquetes nuevos. Sin tocar `vision/` ni el worker. MUST NOT alterar cuerpos de métricas, funnel, patrones, possible-purchases ni chat.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` (US1, US2, US3).

## Phase 1: Setup

**Purpose**: Confirmar alcance sin dependencias nuevas.

- [X] T001 Verificar que `backend/pyproject.toml` y `frontend/package.json` no ganan paquetes. Confirmar en [plan.md](./plan.md) que no hay migración Alembic para esta feature.

**Checkpoint**: Alcance = servicio de lectura + `POST /comparisons` + UI aparte del resultado individual.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquemas de API y núcleo compartido de elegibilidad / resolución de zona que bloquean todas las historias.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T002 [P] Añadir modelos Pydantic de petición/respuesta de comparación en `backend/src/flowsight/api/schemas.py` según [contracts/openapi.yaml](./contracts/openapi.yaml) y [data-model.md](./data-model.md) (`ComparisonRequest`, columnas, celdas, cifras, insights).
- [X] T003 Crear `backend/src/flowsight/services/comparison.py` con: (1) filtrar sesiones elegibles (archivo/`synthetic`, `completed` + `result_complete`, no borradas; deduplicar ids); (2) resolver `zone_name` → `shop_id` por escena inmutable de cada sesión; (3) códigos de error `comparison_invalid_request` y `comparison_insufficient_sessions`. Reutilizar loaders existentes (`load_shop_metrics` en `backend/src/flowsight/services/scene_metrics.py`, `load_shop_funnel`, `load_visit_patterns`, lectura de possible-purchases) sin recalcular. Todavía puede devolver solo columnas + cifras base vacías de insights si US3 no está; el ensamblado completo de filas entra en US1.

**Checkpoint**: Se pueden unit-testear elegibilidad y resolución de zona sin UI.

---

## Phase 3: User Story 1 — Comparar cifras ya guardadas entre sesiones (Priority: P1) 🎯 MVP

**Goal**: Elegir ≥2 sesiones de archivo completadas y un `zone_name`; ver lado a lado las ocho métricas, tasa de ingreso y pico, con no disponible ≠ cero y sin recalcular.

**Independent Test**: Dos sesiones sintéticas completadas → `POST /comparisons` con `axis=session` devuelve columnas identificables y cifras; unavailable en un lado sin delta inventado; &lt;2 elegibles → 409; lecturas individuales sin cambio de cuerpo.

### Tests for User Story 1

- [X] T004 [P] [US1] Escribir `backend/tests/unit/test_comparison.py` cubriendo elegibilidad, deduplicación, resolución de zona, celdas available/unavailable, delta solo con ambos lados available, cero real disponible, y familia opcional con un lado ausente (fila visible). Sin video ni GPU.
- [X] T005 [P] [US1] Escribir `backend/tests/contract/test_comparison_api.py` contra [contracts/openapi.yaml](./contracts/openapi.yaml): `POST /comparisons` 200 con `axis=session`; 400 `comparison_invalid_request`; 409 `comparison_insufficient_sessions` (webcam, incompleta, un solo id útil); misma petición → mismo cuerpo; `GET` métricas/funnel/patrones/possible-purchases/chat de esas sesiones no cambian de forma.
- [X] T006 [P] [US1] Escribir `frontend/tests/ComparisonPage.test.tsx` (o `ComparisonPanel.test.tsx`) según [contracts/comparison-ui.md](./contracts/comparison-ui.md): selector ≥2 sesiones + zona; tabla con no disponible; rechazo claro si faltan sesiones elegibles.

### Implementation for User Story 1

- [X] T007 [US1] Completar ensamblado de filas obligatorias (`shop_metrics` + `peak`) y opcionales (funnel, visit_patterns, possible_purchase) en `backend/src/flowsight/services/comparison.py` con `axis=session`, relation/delta según [data-model.md](./data-model.md). Insights pueden ser lista vacía o stub hasta US3. Hasta T004 en verde.
- [X] T008 [US1] Exponer `POST /comparisons` en `backend/src/flowsight/api/routes.py` usando los schemas de T002 y el servicio de T003/T007. Hasta T005 en verde.
- [X] T009 [P] [US1] Crear cliente `frontend/src/api/comparisons.ts` tipado para `POST /comparisons`.
- [X] T010 [US1] Crear `frontend/src/pages/ComparisonPage.tsx` (+ CSS module) con selección desde historial (`listProcessedSessions`), `zone_name` y tabla de cifras. Cablear ruta en `frontend/src/navigation.ts` y `frontend/src/App.tsx`. Entrada desde `frontend/src/pages/ProcessedSessionsSection.tsx` o `SessionsPage` sin mutar `SessionResultsPage` de una sola sesión. Hasta T006 en verde.

**Checkpoint**: MVP usable: comparación sesión vs sesión sin depender de insights ni ejes P2.

---

## Phase 4: User Story 2 — Comparar por día, horario o zona (Priority: P2)

**Goal**: Si el tiempo alcanza, `axis` `day` / `time_of_day` / `zone` agrupa según [research.md](./research.md) R6; si no hay datos suficientes → `comparison_axis_unavailable` sin ranking inventado. **No bloquea el cierre de P1.**

**Independent Test**: Conjunto de sesiones de la misma cámara con fechas/franjas/zonas distintas produce contraste por al menos un eje; eje insuficiente informa no disponible.

### Tests for User Story 2

- [X] T011 [P] [US2] Extender `backend/tests/unit/test_comparison.py` y `backend/tests/contract/test_comparison_api.py` para `day` (fecha UTC de `finished_at`), `time_of_day` (tiempo de video / buckets, no registro), `zone` (misma cámara + nombre); 409 `comparison_axis_unavailable` sin grupos suficientes; mismo nombre de zona en cámaras distintas no se unifica.

### Implementation for User Story 2

- [X] T012 [US2] Implementar ejes P2 en `backend/src/flowsight/services/comparison.py` y aceptar esos `axis` en `POST /comparisons`. Hasta T011 en verde.
- [X] T013 [US2] Añadir controles de eje en `frontend/src/pages/ComparisonPage.tsx` solo si el backend los soporta; mostrar mensaje de eje no disponible sin inventar grupos. Hasta T011 en verde.

**Checkpoint**: P2 entregado o explícitamente diferido en notas de PR sin romper US1.

---

## Phase 5: User Story 3 — Insights derivados (Priority: P2)

**Goal**: Insights cortos deterministas verificables contra las cifras; sin LLM; sin causas/ventas/identidades; chat mínimo intacto.

**Independent Test**: Comparación con diferencia → insight que cita la cifra; empates/unavailable → `no_highlights` (o equivalente); chat no narra comparación.

### Tests for User Story 3

- [X] T014 [P] [US3] Extender `backend/tests/unit/test_comparison.py` con reglas de insight (`higher_traffic_total`, etc., y `no_highlights`); 100 % de afirmaciones numéricas coinciden con celdas; rótulo de estimación cuando aplica.
- [X] T015 [P] [US3] Extender `backend/tests/contract/test_chat_api.py` (o el de comparación) para afirmar que el chat mínimo no incluye herramientas ni texto de comparación/insights (SC-007 / FR-008).
- [X] T016 [P] [US3] Extender `frontend/tests/ComparisonPage.test.tsx` para mostrar insights o el mensaje de sin diferencias / faltan datos.

### Implementation for User Story 3

- [X] T017 [US3] Implementar generación de insights en `backend/src/flowsight/services/comparison.py` (reglas puras, sin Azure). Rellenar `insights` en la respuesta de `POST /comparisons`. Hasta T014 y T015 en verde.
- [X] T018 [US3] Mostrar bloque de insights en `frontend/src/pages/ComparisonPage.tsx`. Hasta T016 en verde.

**Checkpoint**: Insights verificables en la misma respuesta de comparación; chat mínimo sin cambios de alcance.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validar quickstart y regresiones sin ampliar alcance.

- [X] T019 Ejecutar comandas de [quickstart.md](./quickstart.md) (unit+contract comparison, regresión métricas/funnel/patrones/possible-purchase/chat, Vitest Comparison*) y corregir solo fallos de esta feature. No agregar paquetes.

**Checkpoint**: Quickstart en verde.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: inmediato
- **Foundational (Phase 2)**: después de Setup — BLOQUEA historias
- **US1 (Phase 3)**: después de Foundational — MVP
- **US2 (Phase 4)**: después de US1 (reutiliza `POST /comparisons`); omitible si no alcanza el tiempo
- **US3 (Phase 5)**: después de US1 (puede en paralelo con US2 si hay dos personas; mismo `comparison.py` → coordinar)
- **Polish**: después de las historias que se entreguen

### User Story Dependencies

- **US1 (P1)**: sin dependencia de otras historias
- **US2 (P2)**: depende del contrato US1; no bloquea merge de MVP si se documenta diferido
- **US3 (P2)**: depende de cifras de US1; independiente de US2

### Within Each User Story

- Tests primero (deben fallar) → servicio → ruta/UI
- No modificar contratos de lecturas 006–012/008

### Parallel Opportunities

- T002 ∥ preparación de fixtures de test
- T004 ∥ T005 ∥ T006 (tests US1)
- T009 ∥ T007 (cliente vs ensamblado backend, tras T002)
- T011 ∥ trabajo UI US2 tras API
- T014 ∥ T015 ∥ T016
- US2 ∥ US3 con cuidado en `comparison.py` / `ComparisonPage.tsx`

---

## Parallel Example: User Story 1

```bash
# Tests en paralelo:
Task: "T004 unit test_comparison.py"
Task: "T005 contract test_comparison_api.py"
Task: "T006 frontend ComparisonPage.test.tsx"

# Tras T002/T003:
Task: "T007 ensamblado en services/comparison.py"
Task: "T009 cliente frontend/src/api/comparisons.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + 2  
2. Phase 3 (US1)  
3. **STOP y validar** comparación sesión vs sesión  
4. Demo / PR de MVP si hace falta  

### Incremental Delivery

1. US1 → comparación usable  
2. US3 → insights (alto valor, mismo endpoint)  
3. US2 → ejes día/horario/zona si hay tiempo  
4. T019 quickstart  

### Parallel Team Strategy

1. Juntos: Setup + Foundational  
2. Dev A: US1 backend; Dev B: US1 frontend tests/UI tras contrato estable  
3. Luego US3; US2 solo si capacidad  

---

## Notes

- [P] = archivos distintos, sin depender de tareas incompletas  
- Sin `alembic` nuevo; sin LLM; sin webcam como columna completa  
- P2 (US2) no bloquea cierre de P1 (FR-004)  
- Commit por tarea o grupo lógico  
- Siguiente comando típico: `/speckit-implement`

---

## Phase 7: Convergence

**Purpose**: Cerrar huecos detectados vs spec/plan tras `/speckit-implement`.

- [X] T020 Usar fecha de calendario **UTC** de `finished_at` al agrupar el eje `day` en `backend/src/flowsight/services/comparison.py` (p. ej. `finished_at.astimezone(UTC).date()`), no la zona local del host; cubrir con assert en `backend/tests/contract/test_comparison_api.py` o unitario per FR-004 (contradicts)
- [X] T021 Aclarar en `frontend/src/pages/ComparisonPage.tsx` (opción de eje y/o texto de ayuda) que «Día» es la fecha UTC de cierre del análisis, no el día del local ni el tiempo del video; ajustar `frontend/tests/ComparisonPage.test.tsx` si hace falta per FR-004 (partial)
