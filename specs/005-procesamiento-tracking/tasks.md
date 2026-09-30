---

description: "Lista de tareas de la feature 005: procesamiento y seguimiento con vista en vivo"
---

# Tasks: Procesamiento y seguimiento con vista en vivo

**Input**: Documentos de diseño de `/specs/005-procesamiento-tracking/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/openapi.yaml](./contracts/openapi.yaml), [contracts/preview-websocket.md](./contracts/preview-websocket.md), [contracts/trajectory-sample.md](./contracts/trajectory-sample.md), [quickstart.md](./quickstart.md)

**Azure Boards**: Feature #13 (Epic #1). US1 = #56, US2 = #57, US3 = #58, US4 = #60, US5 = #59. Esta lista no crea tareas en Boards.

**Tests**: Se incluyen porque el plan los exige ("Testing" y "Verification Strategy") y la constitución pide pruebas de cruces, timestamps, aislamiento por sesión y recorridos de interfaz. Dentro de cada historia, las pruebas se escriben primero y deben fallar antes de implementar.

**Organization**: Las tareas se agrupan por User Story. Cada tarea nombra los archivos que toca. Rutas relativas a la raíz del repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Se puede hacer en paralelo (archivos distintos, sin depender de tareas incompletas).
- **[Story]**: User Story de `spec.md` a la que aporta (US1, US2, US3, US4, US5).
- `ultralytics==8.4.153`, `torch==2.7.1+cpu` y `torchvision==0.22.1+cpu` son el stack ya acordado, fijado en [R1](./research.md#r1--detector-y-tracker). Mostrar los comandos de instalación antes de ejecutarlos. No agregar el wheel de GPU al lock de CI.
- Nunca `alembic downgrade` ni borrar la base para recuperar un entorno: se corrige la causa y se vuelve a correr `alembic upgrade head`. Las pruebas que migran usan `destructive_database_url()` de `backend/tests/conftest.py`.

---

## Phase 1: Setup

**Purpose**: Dependencias de visión en el lock de CPU y la configuración del detector.

- [X] T001 Agregar `ultralytics==8.4.153`, `torch==2.7.1+cpu` y `torchvision==0.22.1+cpu` a `backend/pyproject.toml` y regenerar `backend/requirements.lock` con el índice CPU de PyTorch (`https://download.pytorch.org/whl/cpu`), el mismo criterio que `experiments/video-tracking-validation/requirements.txt`. Registrar en `backend/pyproject.toml` el marker `gpu` y dejar `addopts` con `-m "not gpu"` además de las opciones actuales. Mostrar los comandos al usuario, reinstalar el venv desde el lock y confirmar que `import torch` ve la variante CPU. El paquete de la API no debe importar `ultralytics` ni `torch` en `backend/src/flowsight/api/`. · [R1](./research.md#r1--detector-y-tracker), [R6](./research.md#r6--pruebas-sin-el-equipo-de-referencia)
- [X] T002 [P] Extender `Settings` en `backend/src/flowsight/core/config.py` con `detector` (`FLOWSIGHT_DETECTOR`, `fake` o `ultralytics`, default `fake`) y `yolo_weights` (`FLOWSIGHT_YOLO_WEIGHTS`, ruta opcional, `None` si falta). Un valor distinto de esos dos no impide el arranque: queda como `fake`. Documentar ambas en `.env.example`. Casos en `backend/tests/unit/test_config.py`: ausente, `fake`, `ultralytics`, valor inválido. Ningún mensaje de error repite una ruta absoluta.

**Checkpoint**: La suite actual sigue corriendo sin GPU y sin el peso. `FLOWSIGHT_DETECTOR` ausente equivale a `fake`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Esquema `0004`, modelos y transiciones de estado que todas las historias usan.

**⚠️ CRITICAL**: Ninguna User Story empieza hasta completar esta fase.

- [X] T003 Escribir `backend/tests/integration/test_migration_0004.py` con `destructive_database_url()`. Sobre una base en `0003`, `upgrade head` debe: agregar `cancelled` a `job_status`; agregar en `processing_jobs` `frames_analyzed`, `frames_total`, `analyzed_video_timestamp_seconds`, `result_complete` (false por defecto), `detector_name`, `detector_version`, `tracker_name`, `tracker_version` y `trajectory_relative_path`; crear `analysis_measures` y `line_crossings` según [data-model.md](./data-model.md), con UNIQUE `(job_id, shop_id, code)` y el índice `(session_id, shop_id, track_id)`. Un `video_analysis` de specs/004 sigue exigiendo `scene_version_id`. `result_complete=true` con un estado distinto de `completed` se rechaza si el CHECK del data-model está definido. El `downgrade` de `0004` a `0003` solo se usa como fixture de test.
- [X] T004 Crear `backend/alembic/versions/0004_video_analysis.py` que cumpla T003. `ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled'` va dentro de `op.get_context().autocommit_block()`, como en `0002`. El `downgrade` quita tablas y columnas nuevas y no borra el valor `cancelled` del enum (PostgreSQL no lo permite de forma segura). Correr T003 hasta verde.
- [X] T005 Extender `backend/src/flowsight/db/models.py` con `JobStatus.CANCELLED`, los campos nuevos de `ProcessingJob`, y los modelos `AnalysisMeasure` y `LineCrossing` (`code`, `availability`, `disposition`, `direction`) con los mismos nombres de restricción que `0004`. `alembic check` no debe reportar diferencias.
- [X] T006 Extender `backend/src/flowsight/services/jobs.py`: `pending → cancelled` y `processing → cancelled`; `finished_at` también en `cancelled`; `result_complete=true` solo al pasar a `completed`, y `false` en `failed` o `cancelled`. `failed` sigue exigiendo `reason_code` y `failure_message`. `cancelled` no los exige. No hay salida desde `completed`, `failed` ni `cancelled`. Actualizar `backend/src/flowsight/worker/lifecycle.py` `recover_interrupted_jobs` para que un `processing` encontrado al arrancar siga yendo a `failed` con `failure_code=worker_interrupted` y `result_complete=false`, nunca a `cancelled`.

**Checkpoint**: `alembic upgrade head` aplica `0004`. Un trabajo sintético de specs/002 sigue el ciclo `pending → processing → completed` o `failed`.

---

## Phase 3: User Story 1 — Procesar un video y conservar el seguimiento (Priority: P1) · #56 🎯 MVP

**Goal**: El worker reclama un `video_analysis`, lo recorre con el detector configurado y deja el seguimiento anónimo atado al instante del video, sin una fila por persona y por fotograma.

**Independent Test**: Con `FLOWSIGHT_DETECTOR=fake`, una sesión con video y escena válida termina en `completed`, con versiones del método, muestra JSONL cada 5 fotogramas y cero filas nuevas en `observations`. Otra sesión con el mismo `track_id` no ve esa muestra.

### Tests for User Story 1 ⚠️

- [X] T007 [P] [US1] Escribir `backend/tests/unit/test_trajectory_sample.py`. El escritor de [contracts/trajectory-sample.md](./contracts/trajectory-sample.md) crea un JSONL cuyo primer registro es `header` (`sample_every_frames=5`, nombres y versiones) y luego solo fotogramas 0, 5, 10… con `bbox` y `foot` normalizados. El centro inferior de `[10, 20, 40, 80]` es `[25, 80]` en píxeles y el normalizado usa el ancho y alto del frame. No escribe una línea por cada fotograma.
- [X] T008 [P] [US1] Escribir `backend/tests/integration/test_video_analysis_job.py` (PostgreSQL, `FLOWSIGHT_DETECTOR=fake`, video generado con `flowsight.video.fixtures`). Cubre: el worker reclama `video_analysis` y lo deja `completed` con `result_complete=true`, `frames_analyzed == frames_total` y `frames_total` igual a `video_sources.frame_count` (no `declared_frame_count`); `detector_name=fake` y `tracker_name=fake`; el JSONL existe bajo `FLOWSIGHT_VIDEOS_DIR` y la API no devuelve esa ruta absoluta; no se insertan filas en `observations` ni `synthetic_frames` para ese trabajo; dos sesiones con el mismo `track_id` no comparten muestras. El peso YOLO no se carga.

### Implementation for User Story 1

- [X] T009 [P] [US1] Crear `backend/src/flowsight/vision/detector.py` y `backend/src/flowsight/vision/fake.py`. La interfaz devuelve, por fotograma, detecciones con `track_id`, `bbox` en píxeles y el pie en el centro inferior. `fake` reproduce una secuencia fija y determinista, sin OpenCV de red ni `ultralytics`. Incluir `build_detector(settings)` que con `fake` no abre el peso.
- [X] T010 [P] [US1] Implementar `backend/src/flowsight/vision/trajectory.py` según [contracts/trajectory-sample.md](./contracts/trajectory-sample.md) y [R2](./research.md#r2--qué-se-guarda-y-qué-no): ruta relativa `derived/<session_id>/<job_id>/trajectory.jsonl` bajo `FLOWSIGHT_VIDEOS_DIR`, muestra cada 5 fotogramas, encabezado con versiones. Sin DB ni FastAPI. Hasta T007 en verde.
- [X] T011 [P] [US1] Implementar `backend/src/flowsight/vision/ultralytics_tracker.py` con Ultralytics `8.4.153`, peso `yolov8n.pt` desde `FLOWSIGHT_YOLO_WEIGHTS` y ByteTrack. Si el peso no está o el detector no es `ultralytics`, no se importa en el arranque de la API. `model_unavailable` es el código de fallo cuando el worker real no encuentra el peso. El dispositivo gráfico se usa solo si está disponible; si no, CPU ([R1](./research.md#r1--detector-y-tracker)).
- [X] T012 [US1] Crear `backend/src/flowsight/worker/video_analysis.py`. Para un trabajo ya en `processing`: lee el video de la sesión, copia `frames_total` desde `video_sources.frame_count`, recorre los fotogramas, calcula `analyzed_video_timestamp_seconds = frame_index / fps`, escribe la muestra con T010 y al terminar llama a `transition_job(..., completed)`. Si el archivo no está, `failed` con `video_unavailable`. Si el detector real no tiene peso, `failed` con `model_unavailable`. Un error del método queda `failed` con `analysis_failed` y un mensaje sin rutas ni secretos. Depende de T009 y T010.
- [X] T013 [US1] En `backend/src/flowsight/worker/lifecycle.py`, agregar `JobKind.VIDEO_ANALYSIS` a `SUPPORTED_JOB_KINDS` y despachar ese tipo a T012. El claim sigue siendo uno por vez, `FOR UPDATE SKIP LOCKED`, ordenado por `created_at`. El flujo `synthetic_base_flow` no cambia. Hasta T008 en verde.
- [X] T014 [US1] Extender `JobResponse` en `backend/src/flowsight/api/schemas.py` y el `GET /jobs/{job_id}` existente con `status` incluido `cancelled`, `result_complete`, `frames_analyzed`, `frames_total`, `analyzed_video_timestamp_seconds`, `detector_name`, `detector_version`, `tracker_name`, `tracker_version` y `scene_version_id`, según [contracts/openapi.yaml](./contracts/openapi.yaml). No agregar la ruta absoluta de la trayectoria.

**Checkpoint**: Un `video_analysis` con detector falso termina solo, queda aislado por sesión y no llena `observations`. El trabajo sintético sigue igual.

---

## Phase 4: User Story 2 — Ver el seguimiento mientras se analiza (Priority: P1) · #57

**Goal**: Durante el análisis, la vista muestra el fotograma de ese instante con recuadros, identificadores, zonas y línea. Un observador lento no frena el trabajo.

**Independent Test**: El mensaje `schema_version` `2` trae el mismo `frame_index` que la imagen. Un cliente que publica dos actualizaciones seguidas conserva solo la última. El trabajo sintético sigue en `schema_version` `1`.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Escribir `backend/tests/integration/test_video_preview.py`. Publicar dos `PreviewUpdate` de un `video_analysis` deja un solo pendiente, el del `frame_index` mayor, con `schema_version` `2`, JPEG que empieza con `FF D8` y el mismo instante que el fotograma. El mensaje sintético armado por `PreviewUpdate.as_message()` sigue en `schema_version` `1` sin campo `measures`. Un cliente desconectado no cambia el estado del trabajo.

### Implementation for User Story 2

- [X] T016 [US2] Crear `backend/src/flowsight/vision/overlay.py` con una función pura que reciba el frame BGR, las detecciones, las zonas y la línea de la versión, y devuelva un JPEG. Dibuja recuadro, `track_id`, polígonos y la línea. Calidad inicial 80. Si el JPEG supera 200 KiB, baja la calidad sin cambiar el instante ni forzar 320×180 ([R5](./research.md#r5--vista-en-vivo)).
- [X] T017 [US2] Extender `backend/src/flowsight/preview/broker.py` para que `PreviewUpdate` acepte `schema_version` (default `"1"`) y `measures` (default vacío). `as_message()` incluye `measures` solo cuando `schema_version` es `"2"`. El reemplazo del pendiente único no cambia. Hasta T015 en verde para el caso de un solo pendiente.
- [X] T018 [US2] En `backend/src/flowsight/worker/video_analysis.py`, publicar por `PreviewBroker` un update `schema_version` `2` con el JPEG de T016, `progress_percent = frames_analyzed / frames_total` y el instante del fotograma. En `backend/src/flowsight/api/routes.py`, el WebSocket de un `video_analysis` se suscribe al broker; el de `synthetic_base_flow` sigue leyendo `SyntheticFrame` y publicando `schema_version` `1`. El productor no espera al cliente. Depende de T016 y T017.
- [X] T019 [P] [US2] En `frontend/src/api/jobs.ts`, aceptar `schema_version` `1` o `2` y el estado `cancelled` en el mensaje terminal, sin romper `frontend/e2e/job-preview.spec.ts`. En `frontend/src/pages/JobPreviewPage.tsx`, mostrar la imagen, el instante, el avance por fotogramas y el texto de que la vista no promete la velocidad del video.
- [X] T020 [US2] Agregar `frontend/e2e/video-analysis.spec.ts` que, con el detector falso, abre la vista de un `video_analysis`, espera una imagen y comprueba que el instante mostrado coincide con el del mensaje. Depende de T018 y T019.

**Checkpoint**: La vista del video real coincide con su instante. La vista sintética de specs/002 no cambia de formato.

---

## Phase 5: User Story 3 — Avance y conteos parciales (Priority: P1) · #58

**Goal**: El avance sigue los fotogramas del video. Entradas, salidas y ocupación visible se ven parciales y, al completar, pasan a ser los números oficiales de la sesión.

**Independent Test**: A la mitad de los fotogramas el avance es 50 % ± 1 fotograma. Al completar hay una sola fila por medida, con `partial=false`. Una oscilación dentro de 10 fotogramas y un cambio de identificador no aumentan entradas ni salidas.

### Tests for User Story 3 ⚠️

- [X] T021 [P] [US3] Escribir `backend/tests/unit/test_spatial_counts.py` según [R3](./research.md#r3--entradas-salidas-y-ocupación-visible). El sentido de entrada configurado suma `entries`; el opuesto, `exits`. Dos cruces de sentidos opuestos del mismo `track_id` a ≤ 10 fotogramas quedan `oscillation` y no suman. A 11 fotogramas, ambos confirman. Un `track_id` nuevo no hereda un cruce ni genera una salida. La ocupación visible es la cantidad de pies distintos dentro de la zona frontal en el último fotograma, no un acumulado y no usa la zona interior. Extender `backend/tests/integration/test_video_analysis_job.py`: con el detector falso, al 50 % de los fotogramas `frames_analyzed` es la mitad ± 1; al completar, `GET /jobs/{id}/measures` devuelve las tres medidas con `partial=false` y no existe una segunda fila para el mismo `(job_id, shop_id, code)`.

### Implementation for User Story 3

- [X] T022 [US3] Implementar `backend/src/flowsight/vision/spatial.py` sin DB ni FastAPI: pie normalizado, cruce de la línea con la convención A/B de `backend/src/flowsight/scene/geometry.py`, debounce de 10 fotogramas, y ocupación visible de la zona frontal. Reutilizar la geometría existente; no copiar una segunda definición de A/B. Hasta la parte unitaria de T021 en verde.
- [X] T023 [US3] Crear `backend/src/flowsight/services/measures.py`. Upsert de `analysis_measures` por `(job_id, shop_id, code)` e inserción de `line_crossings` solo para el hecho (`confirmed` u `oscillation`), no por fotograma. Al completar, las mismas filas pasan a `partial=false`. En `failed` o `cancelled` permanecen `partial=true`. Cada fila guarda `video_timestamp_seconds` del fotograma que la produjo.
- [X] T024 [US3] En `backend/src/flowsight/worker/video_analysis.py`, actualizar `frames_analyzed` y el instante en cada fotograma, y llamar a T022 y T023. `progress_percent` sale de esos fotogramas, no del reloj de pared. Al pasar a `completed`, cerrar las medidas como oficiales. Depende de T022 y T023.
- [X] T025 [US3] Agregar `AnalysisMeasureResponse` en `backend/src/flowsight/api/schemas.py` y `GET /jobs/{job_id}/measures` en `backend/src/flowsight/api/routes.py`, según [contracts/openapi.yaml](./contracts/openapi.yaml). Incluir `shop_name` de la versión usada. 404 si el trabajo no existe. Hasta la parte de integración de T021 en verde.
- [X] T026 [US3] Incluir en el `preview.update` de `schema_version` `2` el arreglo `measures` del contrato [preview-websocket.md](./contracts/preview-websocket.md), con `partial=true` mientras el trabajo no esté `completed`. El mensaje `schema_version` `1` no lleva ese arreglo. Depende de T017 y T024.

**Checkpoint**: Las tres medidas oficiales son las filas con `partial=false`. No hay otro cálculo paralelo.

---

## Phase 6: User Story 4 — Evidencia en el equipo de referencia (Priority: P1) · #60

**Goal**: Dejar registrado cómo corrió un video real en el equipo de referencia, sin exigir ese equipo para el resto de la feature.

**Independent Test**: `pytest` por defecto no recolecta la prueba `gpu`. El resumen versionable trae dispositivo, versiones y fotogramas por segundo de procesamiento, y no trae nombre de máquina, usuario ni rutas. Si no hay dispositivo gráfico, el mismo flujo termina en CPU y el resumen lo dice.

### Tests for User Story 4 ⚠️

- [X] T027 [US4] Crear `backend/tests/gpu/test_reference_device.py` marcado `pytest.mark.gpu`. Comprueba que, con `FLOWSIGHT_DETECTOR=ultralytics` y el peso presente, un clip corto termina y el resumen incluye `execution_mode`, versiones y `frames_per_processing_second`. Si no hay CUDA, el test se salta con motivo explícito y no falla la suite. Confirmar que `backend/.venv/Scripts/pytest` (o `bin/pytest`) sin argumentos no lo recolecta.

### Implementation for User Story 4

- [X] T028 [P] [US4] Crear `backend/src/flowsight/vision/evidence.py` y `specs/005-procesamiento-tracking/validation/README.md`. El escritor arma el JSON de [R6](./research.md#r6--pruebas-sin-el-equipo-de-referencia): dispositivo, versiones del método, fotogramas procesados por segundo de procesamiento (`frames_total / processing_duration_s`) y limitaciones. El texto versionable no incluye hostname, usuario, rutas absolutas ni secretos. El README dice que CI no exige este archivo.
- [X] T029 [P] [US4] En `backend/src/flowsight/vision/ultralytics_tracker.py`, si el dispositivo gráfico no está o falla al usarse, continuar en CPU y devolver esa limitación a T028 en vez de dejar el trabajo `failed` solo por la GPU. Depende de T011.

**Checkpoint**: La suite ordinaria sigue en verde sin la PC de referencia. La medición manual queda descrita en `validation/README.md`.

---

## Phase 7: User Story 5 — Cancelar un análisis (Priority: P2) · #59

**Goal**: El operador puede cancelar un análisis en curso. El trabajo queda `cancelled`, no `failed`, y lo ya guardado queda incompleto.

**Independent Test**: Cancelar durante el recorrido no procesa fotogramas posteriores, deja `result_complete=false` y las medidas en `partial=true`. Volver a arrancar el worker no lo retoma. Una caída del proceso sigue en `failed` con `worker_interrupted`.

### Tests for User Story 5 ⚠️

- [X] T030 [P] [US5] Extender `backend/tests/integration/test_video_analysis_job.py` y agregar `backend/tests/contract/test_video_analysis_api.py`. `POST /jobs/{id}/cancel` sobre `pending` o `processing` responde 200 con `status=cancelled` y `result_complete=false`. Sobre `completed`, `failed` o `cancelled` responde 409. Tras cancelar a mitad del video falso, `frames_analyzed` no llega a `frames_total` y las medidas siguen `partial=true`. `recover_interrupted_jobs` no convierte ese trabajo en `failed` ni lo vuelve a reclamar. Un `processing` huérfano, sin cancelación, sí pasa a `failed` / `worker_interrupted`.

### Implementation for User Story 5

- [X] T031 [US5] Implementar `POST /jobs/{job_id}/cancel` en `backend/src/flowsight/api/routes.py` usando `transition_job` de T006. Motivo de la transición: `operator_cancelled`, sin `failure_code`. 404 si no existe. 409 si el estado no admite la transición, con `{"detail": {"code", "message"}}`. Depende de T030 escrito y de T006.
- [X] T032 [US5] En `backend/src/flowsight/worker/video_analysis.py`, al terminar cada fotograma volver a leer el estado. Si es `cancelled`, persistir la muestra y las medidas ya calculadas, no llamar a `completed` y salir. No procesar el fotograma siguiente. Depende de T012 y T031.
- [X] T033 [P] [US5] En `frontend/src/api/jobs.ts` agregar `cancelJob`. En `frontend/src/pages/JobPreviewPage.tsx` mostrar un botón "Cancelar análisis" mientras el estado es `pending` o `processing`, y el estado `cancelled` como incompleto, distinto de `failed`.
- [X] T034 [US5] Extender `frontend/e2e/video-analysis.spec.ts` para pulsar "Cancelar análisis" y ver el estado cancelado. Depende de T020, T032 y T033.

**Checkpoint**: Cancelar y una caída del proceso dejan estados distintos. Ninguno se reintenta solo.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Cerrar documentación y la regresión de las features anteriores.

- [X] T035 [P] Actualizar `README.md` y `docs/decisiones-tecnicas.md`: `video_analysis` ya no queda pendiente hasta #56; el detector por defecto de tests es `fake`; el lock de CPU no incluye el wheel de GPU; las tres medidas oficiales viven en `analysis_measures`.
- [ ] T036 Seguir [quickstart.md](./quickstart.md): correr la suite de `backend/` (sin marker `gpu`) y `npm run lint`, `npm test`, `npm run build` y `npm run test:e2e` en `frontend/`. La suite de specs/002 y specs/004, incluido `frontend/e2e/job-preview.spec.ts`, queda en verde.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup. Bloquea todas las historias.
- **US1 (Phase 3)**: depende de Phase 2. Bloquea US2, US3, US4 y US5.
- **US2 (Phase 4)**: depende de US1.
- **US3 (Phase 5)**: depende de US1. T026 depende además de T017.
- **US4 (Phase 6)**: depende de T011. No depende de la vista ni de los conteos.
- **US5 (Phase 7)**: depende de US1. T034 depende también de la vista (T020).
- **Polish (Phase 8)**: depende de las historias que se quieran cerrar. Para dar la feature por completa, de todas.

### User Story Dependencies

- **US1 (P1)**: primera historia entregable. No depende de las otras.
- **US2 (P1)**: necesita el bucle de US1 para publicar fotogramas. El formato sintético no depende de US1.
- **US3 (P1)**: necesita el bucle de US1. El cálculo puro de T022 no necesita la vista.
- **US4 (P1)**: necesita el detector real de T011. La suite ordinaria no lo ejecuta.
- **US5 (P2)**: necesita el bucle de US1 y las transiciones de Phase 2. Es la única historia de prioridad menor.

### Within Each User Story

- Las pruebas de la historia se escriben y fallan antes de la implementación que las pone verdes.
- Modelos y funciones puras antes del worker.
- El worker antes de los endpoints que exponen su resultado.
- La historia queda verificable antes de pasar a la siguiente.

### Parallel Opportunities

- T002 puede hacerse junto con T001 (archivos distintos).
- T007 y T008 pueden escribirse juntas.
- T009, T010 y T011 pueden hacerse juntas después de esas pruebas.
- T019 puede avanzar junto con T016–T018.
- T021 puede escribirse mientras se cierra US2, si no toca los mismos archivos.
- T028 y T029 pueden hacerse juntas después de T027.
- T031 y T033 pueden hacerse juntas después de T030.

---

## Parallel Example: User Story 1

```text
T007  tests/unit/test_trajectory_sample.py
T008  tests/integration/test_video_analysis_job.py

T009  vision/detector.py + vision/fake.py
T010  vision/trajectory.py
T011  vision/ultralytics_tracker.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 y Phase 2.
2. Completar Phase 3 (US1, #56).
3. Parar y validar el detector falso: trabajo `completed`, muestra cada 5 fotogramas, sesiones aisladas.
4. Recién ahí tiene sentido la vista, los conteos, la GPU o la cancelación.

### Incremental Delivery

1. Setup + Foundational.
2. US1: el video se analiza y se puede consultar el seguimiento.
3. US2: se ve el fotograma con el seguimiento.
4. US3: el avance y las tres medidas oficiales.
5. US4: evidencia manual en el equipo de referencia, sin bloquear CI.
6. US5: cancelar, como incremento P2.
7. Polish: regresión de specs/002 y specs/004.

### Parallel Team Strategy

Con más de una persona, después de US1:

- Una persona puede tomar US2 (vista) y otra US3 (conteos), coordinando T026 porque toca el mensaje de la vista.
- US4 puede avanzar desde T011 sin esperar la interfaz.
- US5 conviene después de que el bucle de US1 esté estable.

---

## Notes

- [P] significa archivos distintos, sin depender de una tarea incompleta.
- El detector de pruebas es `fake`. No hace falta el peso ni la GPU para US1, US2, US3 ni US5.
- `frames_total` sale de `video_sources.frame_count`, no del encabezado MPEG.
- Al completar, no se inserta una segunda fila de medidas: las mismas pasan a `partial=false`.
- Cancelar no es un fallo. Una caída del proceso sigue siendo `worker_interrupted`.
