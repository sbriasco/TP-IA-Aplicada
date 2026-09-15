---

description: "Tareas del experimento local de validación de videos y tracking"
---

# Tasks: Validación técnica de videos y tracking

**Input**: Design documents from `specs/001-validacion-videos-tracking/`

**Azure Boards**: Feature #4; US1 → #17, US2 → #18, US3 → #19, US4 → #20

**Scope**: Experimento local pequeño con script Python, YOLO, ByteTrack, archivos locales y
escenas preconfiguradas. No incluye frontend, API, chat, editor visual ni PostgreSQL.

**Tests**: Se incluyen verificaciones automatizadas acotadas porque la especificación exige
comprobar geometría, timestamps, duplicados, aislamiento y formatos. No se ejecutarán durante
la generación de este archivo.

## Phase 1: Setup

**Purpose**: Preparar estructura, protección de datos y entorno reproducible sin instalar
nada sin aprobación explícita.

- [X] T001 Crear la estructura del experimento en `experiments/video-tracking-validation/` con `config/`, `inputs/`, `references/`, `outputs/`, `outputs/overlays/` y `tests/`.
- [X] T002 [P] Crear `experiments/video-tracking-validation/.gitignore` para excluir videos, pesos de modelos, resultados, overlays, archivos de rendimiento, referencias con datos sensibles y entornos virtuales.
- [X] T003 [P] Crear `experiments/video-tracking-validation/README.md` con alcance, límites, relación con Feature #4, User Stories #17-#20, rutas de entrada/salida y advertencia de que videos y pesos no se versionan.
- [X] T004 [P] Crear `experiments/video-tracking-validation/requirements.txt` con las versiones candidatas documentadas en `specs/001-validacion-videos-tracking/plan.md`, indicando que quedan pendientes de validación.
- [X] T005 Confirmar en `experiments/video-tracking-validation/README.md` la aprobación del equipo para instalar dependencias antes de ejecutar cualquier instalación; si no hay aprobación, dejar el entorno sin instalar.
- [X] T006 Instalar las dependencias candidatas en el entorno Python aislado de `experiments/video-tracking-validation/` solo después de la aprobación registrada en `README.md`, documentando la matriz Python/PyTorch/CUDA/GPU y licencias; no ejecutar esta tarea sin esa aprobación.

## Phase 2: Foundational

**Purpose**: Implementar los contratos y validaciones compartidas que bloquean la ejecución
segura de las historias.

- [X] T007 Crear `experiments/video-tracking-validation/config/scene.example.json` usando un ejemplo sintético válido, con dimensiones positivas, polígono no degenerado, línea de dos puntos y mapeo `A_to_B`/`B_to_A` a entrada/salida; marcarlo como ajeno a los videos reales.
- [X] T008 [P] Crear `experiments/video-tracking-validation/references/fragments.example.csv` con `video_id`, `fragment_id`, `start_video_seconds`, `end_video_seconds`, unidad en segundos, motivo, casos cubiertos y limitaciones.
- [X] T010 [P] Crear `experiments/video-tracking-validation/tests/test_scene_config.py` para validar dimensiones positivas, puntos dentro del frame, polígono de al menos tres puntos con área no nula, línea de dos puntos distintos y ambos sentidos de cruce.
- [X] T012 [P] Crear `experiments/video-tracking-validation/tests/test_review_and_results_formats.py` para validar campos mínimos de `outputs/review.csv`, IDs estables de observación automática, bbox, `reference_point` y la distinción entre ausencia fuera de la muestra y espurio revisado.
- [X] T013 Crear `experiments/video-tracking-validation/tests/test_session_isolation.py` para comprobar que los resultados de dos sesiones o cámaras no comparten `session_id`, tracks ni referencias de fragmento.
- [X] T014 Crear `experiments/video-tracking-validation/tests/test_event_deduplication.py` para cubrir oscilaciones sobre la línea, duplicados de una ocurrencia observable y cambios de `track_id` que no deben clasificarse automáticamente como duplicados.

## Phase 3: User Story 1 - Seleccionar fragmentos representativos (Azure #17)

**Goal**: Identificar fragmentos reales y documentar cobertura sin inventar características del
material.

**Independent Test**: Cada video disponible tiene un fragmento documentado o una justificación
explícita de imposibilidad, con intervalo, motivo, casos cubiertos y limitaciones.

- [X] T015 [US1] Implementar en `experiments/video-tracking-validation/run_validation.py` la lectura del manifest local `references/fragments.csv` con límites en segundos del video original y validación de intervalo semiabierto; `references/fragments.example.csv` permanece como plantilla sintética versionada y `fragments.csv` queda excluido de Git.
- [X] T016 [US1] Crear `experiments/video-tracking-validation/inputs/video-inventory.csv` local y no versionado para registrar rutas, resolución, fps, duración, condiciones de uso y observaciones reales de cada video seleccionado.
- [X] T017 [US1] Generar `experiments/video-tracking-validation/outputs/fragment-selection.csv` con cada fragmento, intervalo, motivo, circulación/entradas/frentes/oclusiones observables y limitaciones; ampliar la muestra si faltan cruces u oclusiones antes de concluir.
- [X] T018 [US1] Verificar manualmente la cobertura de `experiments/video-tracking-validation/outputs/fragment-selection.csv` contra `specs/001-validacion-videos-tracking/contracts/fragments-manifest.md` y registrar cualquier video no evaluable.

## Phase 4: User Story 3 - Evaluar tracking y eventos espaciales (Azure #19)

**Goal**: Ejecutar detección y tracking sobre los fragmentos seleccionados y una escena
preconfigurada, antes de comparar contra la referencia manual.

**Independent Test**: La ejecución produce detecciones, tracks temporales, bbox/punto de
referencia, eventos de zona y cruces en ambos sentidos, con IDs estables por observación y
métricas de rendimiento por fragmento.

**Dependency**: Requiere completar US1 y tener aprobada la instalación del entorno si aplica.

- [X] T019 [US3] Precisar en `experiments/video-tracking-validation/config/scene.example.json` qué lado de la línea es A y cuál B, cómo se identifica el cruce del segmento y cómo `A_to_B`/`B_to_A` corresponden a `entry`/`exit` o `unknown`.
- [X] T020 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` la lectura del video por `[start_video_seconds, end_video_seconds)`, conservando `video_timestamp` absoluto y `relative_seconds` sin usar tiempo de procesamiento para métricas de comportamiento.
- [X] T021 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` la detección YOLO y tracking ByteTrack con IDs temporales, bbox `[x_min, y_min, x_max, y_max]`, `reference_point`, frame, timestamp y un ID estable por observación automática para referenciar desde `review.csv`.
- [X] T011 [US3] Verificar en `experiments/video-tracking-validation/tests/test_fragment_times.py` los límites `[start_video_seconds, end_video_seconds)`, las unidades en segundos y la conversión `relative_seconds = video_timestamp_seconds - start_video_seconds` sin redondear timestamps de comportamiento.
- [X] T022 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` las reglas de zona frontal y cruce de segmento en ambos sentidos, registrando dirección, estado de visibilidad, oclusión, pérdida de continuidad y eventos sin asumir identidad real.
- [X] T023 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` la visualización local anotada con detecciones, tracks, bbox/punto, zona, línea y eventos, guardando overlays en `experiments/video-tracking-validation/outputs/overlays/`; no crear interfaz web ni algoritmo de asociación.
- [X] T024 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` el registro `outputs/detections.jsonl`, conservando la relación entre `automatic_observation_id`, sesión, fragmento, frame, timestamp original y tiempo relativo. La cobertura de `events.csv` queda en la tarea de zonas y cruces.
- [X] T025 [US3] Implementar en `experiments/video-tracking-validation/run_validation.py` el registro `outputs/performance.csv` por fragmento con duración del video, frames procesados, tiempo de procesamiento y equipo/dispositivo, separado de los timestamps de comportamiento.
- [X] T026 [US3] Ejecutar las verificaciones de geometría, timestamps, aislamiento, eventos y formatos de `experiments/video-tracking-validation/tests/` sobre datos sintéticos antes de usar videos reales, documentando resultados en `experiments/video-tracking-validation/README.md`.

## Phase 5: User Story 2 - Comparar con una referencia manual (Azure #18)

**Goal**: Revisar visualmente los resultados automáticos contra una muestra manual y registrar
correspondencias y errores sin asociación automática.

**Independent Test**: `outputs/review.csv` permite revisar cada observación manual de la muestra,
identificar coincidencias/omisiones/duplicados y evaluar continuidad de tracks por separado.

**Dependency**: Requiere completar US1 y US3; la ejecución automática debe estar disponible
antes de iniciar esta comparación.

- [X] T009 [US2] Crear `experiments/video-tracking-validation/references/manual.example.csv` como ejemplo de referencia manual sintética, con observaciones, timestamps absolutos, tiempos relativos, zona/línea, dirección, casos cubiertos y notas. Esta preparación puede comenzar después de seleccionar fragmentos y antes de consultar resultados automáticos.
- [X] T027 [US2] Preparar `experiments/video-tracking-validation/references/manual.csv` mirando el video original y sin consultar detecciones, tracks, eventos u overlays automáticos antes de anotar; la comparación posterior depende de que US3 haya producido resultados.
- [X] T028 [US2] Revisar los overlays locales de `experiments/video-tracking-validation/outputs/overlays/` junto con `outputs/detections.jsonl` y `outputs/events.csv`, identificando cada ocurrencia observable por intervalo, zona/línea y dirección.
- [X] T029 [US2] Registrar en `experiments/video-tracking-validation/outputs/review.csv` las correspondencias, omisiones, duplicados y errores observados, usando `automatic_observation_id`; no clasificar como espurio un resultado fuera de la muestra manual revisada.
- [X] T030 [US2] Registrar en `experiments/video-tracking-validation/outputs/review.csv` la continuidad de tracks por separado (`continua`, `posible pérdida`, `cambio de ID`, `no evaluable`) y no convertir automáticamente un cambio de ID en duplicado.
- [X] T031 [US2] Ampliar `experiments/video-tracking-validation/references/manual.csv` y repetir la revisión si la muestra inicial no cubre cruces u oclusiones necesarios para una conclusión.
- [X] T032 [US2] Verificar que `experiments/video-tracking-validation/outputs/review.csv` distingue coincidencia, omisión, duplicado, no comparable y espurio dentro de la muestra, y conserva notas de evidencia humana.

## Phase 6: User Story 4 - Medir tiempos y decidir viabilidad (Azure #20)

**Goal**: Consolidar rendimiento, cobertura directa y estado de viabilidad por medición.

**Independent Test**: El informe final distingue timestamps de comportamiento y rendimiento por
fragmento, separa mediciones comprobadas de no evaluables y asigna un estado de viabilidad válido.

**Dependency**: Requiere completar US1, US3 y US2.

- [X] T033 [US4] Consolidar en `experiments/video-tracking-validation/outputs/performance.csv` los registros por fragmento y, opcionalmente, un resumen global trazable a cada registro.
- [X] T034 [US4] Calcular en `experiments/video-tracking-validation/run_validation.py` solo las duraciones de permanencia e intervalos de comportamiento a partir de timestamps del video, manteniendo separados duración del fragmento, frames y tiempo de procesamiento.
- [X] T035 [US4] Evaluar en `experiments/video-tracking-validation/outputs/viability-report.md` cuáles mediciones se comprobaron directamente con la zona frontal, la línea y los videos disponibles, sin exigir implementar todas las métricas del MVP.
- [X] T036 [US4] Asignar en `experiments/video-tracking-validation/outputs/viability-report.md` a cada medición uno de `viable`, `viable con ajustes`, `no viable con el material o configuración evaluados` o `no evaluable por falta de evidencia`.
- [X] T037 [US4] Documentar en `experiments/video-tracking-validation/outputs/viability-report.md` evidencia, limitaciones, datos incompletos, ajustes requeridos, cobertura manual y conclusiones negativas respaldadas por evidencia.
- [X] T038 [US4] Verificar `experiments/video-tracking-validation/outputs/viability-report.md` contra `specs/001-validacion-videos-tracking/contracts/results-and-report.md` y las condiciones de cierre de US4.

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T039 [P] Actualizar `experiments/video-tracking-validation/README.md` con comandos ejecutados, matriz de entorno, versiones efectivamente usadas, limitaciones y resultados; no afirmar validaciones no ejecutadas.
- [X] T040 [P] Revisar `experiments/video-tracking-validation/.gitignore` para confirmar que no se incluyen videos, pesos, outputs, overlays, referencias locales ni bases de datos.
- [X] T041 [P] Registrar en `experiments/video-tracking-validation/README.md` la evidencia de asistencia de IA, decisiones tomadas y fuentes oficiales consultadas.
- [X] T042 Ejecutar una revisión final de `specs/001-validacion-videos-tracking/`, `experiments/video-tracking-validation/` y `experiments/video-tracking-validation/outputs/` para confirmar trazabilidad a Feature #4, US #17-#20, aislamiento de sesiones y ausencia de secretos o archivos grandes.

## Dependencies & Execution Order

### Story completion order

```text
Setup
  -> Foundational
  -> US1 (#17): selección y manifest de fragmentos
  -> US3 (#19): ejecución automática, geometría, detecciones, eventos y overlays
  -> US2 (#18): comparación manual sobre resultados confirmados
  -> US4 (#20): rendimiento, viabilidad e informe final
  -> Polish
```

US3 se ejecuta antes que US2 aunque US2 tenga un número de historia menor, porque la
comparación manual depende de detecciones, tracks y eventos producidos por la ejecución.

### Parallel opportunities

- Después de T001: T002, T003 y T004 pueden ejecutarse en paralelo.
- Después de T007-T008: T010, T012, T013 y T014 pueden desarrollarse en paralelo; T009 se prepara en US2 después de seleccionar fragmentos y antes de consultar resultados automáticos.
- Después de completar US1: T019 puede prepararse en paralelo con el inventario/configuración,
  mientras la implementación de lectura temporal mantiene la dependencia de T020.
- Dentro de US3, T021 y T022 requieren la lectura temporal y la geometría; T023, T024 y T025
  pueden separarse por archivo o responsabilidad una vez definido el formato de resultados.
- Dentro de US4, T033, T035 y T036 pueden trabajarse en paralelo cuando US2 haya terminado;
  T037 y T038 consolidan el informe.
- T039, T040 y T041 son paralelizables; T042 es el cierre.

## Implementation Strategy

1. **MVP del experimento**: completar Setup, Foundational, US1 y US3 para obtener una ejecución
   automática reproducible con datos sintéticos y videos seleccionados.
2. **Evidencia revisada**: completar US2 solo sobre resultados automáticos confirmados y la
   muestra manual cubierta; ampliar la muestra cuando falten cruces u oclusiones.
3. **Decisión**: completar US4 con rendimiento por fragmento, cobertura directa y estados de
   viabilidad, aceptando conclusiones negativas respaldadas por evidencia.
4. **Cierre**: ejecutar Polish y documentar qué se verificó, qué quedó pendiente y qué no fue
   evaluable.

## Traceability Summary

| User Story | Azure | Spec section | Main outputs |
|---|---:|---|---|
| US1 | #17 | User Story 1 | `fragment-selection.csv`, fragment manifest |
| US2 | #18 | User Story 2 | `review.csv`, manual reference |
| US3 | #19 | User Story 3 | `detections.jsonl`, `events.csv`, overlays, `performance.csv` |
| US4 | #20 | User Story 4 | `viability-report.md`, performance summary |

## Azure Boards Task Mapping

| Tarea | Azure Task | Padre |
|---|---:|---|
| T001-T006 | #21 | US3 #19 |
| T008, T015-T018 | #26 | US1 #17 |
| T009, T027 | #27 | US2 #18 |
| T020-T021, T011, T023-T025 (solo `detections.jsonl` en T024) | #22 | US3 #19 |
| T007, T010, T012-T014, T019, T022, T024 (`events.csv`), T026 | #23 | US3 #19 |
| T028-T032 | #28 | US2 #18 |
| T033-T037 | #24 | US4 #20 |
| T038-T042 | #25 | US4 #20 |

## Phase 8: Convergence

Hallazgos de `/speckit-converge` (2026-09-15). T001–T042 siguen como están; estas tareas
no reescriben requisitos. Un `[X]` previo no se toma como evidencia suficiente.

- [X] T043 Ampliar la muestra manual y `review.csv` a un fragmento ya seleccionado en `fragments.csv` con oclusión o solapamiento (`frag-onestop-group-002` o `frag-walkby-inside-002`), con escena, ejecución automática y revisión humana, o no extraer conclusiones sobre oclusión; no tratar T031 como cobertura de US2/AC2 per US2/AC2, FR-004, SC-002 (partial)
- [X] T044 Reejecutar la medición de `detection_tracking_time_seconds` y `postprocess_time_seconds` en el mismo fragmento, peso `yolov8n.pt` y CPU, contrastarla con T025, y dejar explícito en el informe que los 46 tests unittest no validan ese rendimiento ni la repetición de YOLO per FR-015, SC-009, plan: rendimiento por fragmento (partial)
