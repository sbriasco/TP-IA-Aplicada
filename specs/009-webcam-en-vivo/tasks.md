# Tasks: Análisis en vivo con webcam

**Input**: spec.md, plan.md, research.md, data-model.md y contracts/ de esta carpeta.
**Branch**: feature/009-webcam-en-vivo
**Tests**: requeridos por SC-001–011 y AGENTS.md; escribir y comprobar fallo antes de implementar comportamiento.
**Alcance**: todas las historias, sin grabación ni cámara IP operativa. Las pruebas físicas permanecen pendientes hasta disponer de webcam/encuadre y no se sustituyen por evidencia sintética.

## Phase 1: Setup

- [X] T001 Verificar entorno, ignores y dependencias aprobadas en backend/requirements.lock, frontend/package-lock.json y .gitignore; registrar comandos reproducibles en quickstart.md.
- [X] T002 Registrar la exclusión de Azure Boards autorizada por el usuario y crear registro de ejecución/evidencia en specs/009-webcam-en-vivo/validation/implementation.md.

## Phase 2: Foundational

- [X] T003 Escribir pruebas de enums, migraciones aditivas, constraints y aislamiento en backend/tests/integration/test_live_schema.py.
- [X] T004 Agregar webcam/live_analysis, afinidad y entidades live con FKs/checks en backend/src/flowsight/db/models.py y backend/alembic/versions/0009_live_capture.py, 0010_live_capture_schema.py.
- [X] T005 Escribir pruebas de reserva, exclusión y recuperación por equipo en backend/tests/integration/test_live_machine.py.
- [X] T006 Implementar WorkerMachine, advisory lock, heartbeat y reservas en backend/src/flowsight/worker/live_control.py y services/live_jobs.py; integrar afinidad de archivos en services/jobs.py y worker/lifecycle.py.
- [X] T007 [P] Escribir pruebas del slot de último frame, stop bloqueado y fuente fake en backend/tests/unit/test_live_capture.py.
- [X] T008 Implementar contratos, proceso spawn, webcam DSHOW/MSMF y fuente fake en backend/src/flowsight/capture/contracts.py, process.py, webcam.py y fake.py sin dependencias nuevas.
- [X] T009 [P] Escribir pruebas temporales de cruces, oscilación, continuidad, atribución tardía y segmentos en backend/tests/unit/test_live_spatial.py.
- [X] T010 Implementar contador temporal y reset del tracker en backend/src/flowsight/vision/live_spatial.py y ultralytics_tracker.py preservando contador de archivos.
- [X] T011 [P] Escribir pruebas de reservoir, TTL y límites en backend/tests/unit/test_live_sampling.py.
- [X] T012 Implementar muestreo acotado y reemplazo de slots en backend/src/flowsight/vision/live_sampling.py.

## Phase 3: US1 · Configurar e iniciar webcam (P1)

**Goal**: preparar frame, usar escena existente, iniciar y detener normalmente.
**Independent test**: fuente fake permite preparación/editor/check/start/stop con duración0 previa a captura; dispositivo fallido no deja job ficticio.

- [X] T013 [US1] Escribir contratos de preparación/check/start/stop y retiro concurrente en backend/tests/contract/test_live_sessions.py.
- [X] T014 [US1] Implementar sesión/frame, nonce TTL, confirmación y admisión en backend/src/flowsight/services/live_sessions.py y live_jobs.py.
- [X] T015 [US1] Escribir integración de claim, captura, checkpoint y stop en backend/tests/integration/test_live_analysis_job.py.
- [X] T016 [US1] Implementar runner live y cierre completo con flush idempotente en backend/src/flowsight/worker/live_analysis.py, worker/main.py y worker/lifecycle.py; no crear archivos derivados.
- [X] T017 [US1] Exponer esquemas/rutas REST y errores en backend/src/flowsight/api/live_schemas.py, live_routes.py y main.py.
- [X] T018 [P] [US1] Escribir pruebas de formulario, navegación y discriminación de origen en frontend/tests/LivePreparationPage.test.tsx y frontend/e2e/live.spec.ts.
- [X] T019 [US1] Implementar API/tipos, formulario y preparación reutilizando editor en frontend/src/api/live.ts, types/live.ts, pages/LivePreparationPage.tsx, components/WebcamPreparationForm.tsx, navigation.ts y App.tsx.

## Phase 4: US2 · Imagen y estadísticas en vivo (P1)

**Goal**: mostrar frames recientes con conteos por sentido, total y cruces/minuto sincronizados.
**Independent test**: trayectorias anotadas actualizan sin refresh; sobrecarga y observador lento no acumulan frames; reconectar pantalla conserva acumulados.

- [X] T020 [US2] Escribir pruebas de WS, autenticación interna, límites, revisiones y backpressure en backend/tests/contract/test_live_preview.py.
- [X] T021 [US2] Implementar canal productor/control loopback, broker acotado y schemas en backend/src/flowsight/preview/live_channel.py y live_messages.py; integrar worker/API sin snapshots en disco.
- [X] T022 [US2] Implementar persistencia transaccional de cruces/buckets por timestamp original y publicación atómica en backend/src/flowsight/services/live_results.py y worker/live_analysis.py.
- [X] T023 [US2] Escribir pruebas de mensajes fuera de orden, reloj y pares imagen/métricas en frontend/tests/LiveAnalysisPage.test.tsx y liveMessages.test.ts.
- [X] T024 [US2] Implementar pantalla live, selector de local/sentidos, gráfico, clock calibration y stop asíncrono en frontend/src/pages/LiveAnalysisPage.tsx, components/CrossingChart.tsx y api/live.ts.
- [X] T025 [US2] Verificar recorrido de vivo y reload con API/worker fake reales en frontend/e2e/live.spec.ts y frontend/e2e/run-e2e.mjs.

## Phase 5: US3 · Interrupciones e historial (P2)

**Goal**: preservar acumulados, confirmar reanudación y consultar resultados/muestra sin video ni métricas comerciales.
**Independent test**: desconectar fuente, confirmar encuadre, detener y reiniciar muestra cruces, huecos y heatmap aislados.

- [X] T026 [US3] Escribir integración de desconexión/retry/confirmación, cambio de dimensiones, caída de worker y DB en backend/tests/integration/test_live_recovery.py.
- [X] T027 [US3] Implementar discontinuidad, tres retries y confirmación antes de nuevo segmento en backend/src/flowsight/worker/live_analysis.py, live_control.py y services/live_jobs.py.
- [X] T028 [US3] Implementar recuperación scoped, fallo con checkpoint y buffers limitados ante caída DB en backend/src/flowsight/worker/lifecycle.py y live_analysis.py.
- [X] T029 [US3] Escribir contratos de historial, eventos paginados, muestra y guard chat en backend/tests/contract/test_live_results.py.
- [X] T030 [US3] Implementar resultados/eventos/coverage y lecturas source-aware en backend/src/flowsight/services/live_results.py, position_samples.py, processed_sessions.py, sessions.py y guard de chat existente.
- [X] T031 [US3] Escribir pruebas de estados históricos, huecos y no reproducción/chat en frontend/tests/LiveResultsPage.test.tsx y frontend/e2e/live.spec.ts.
- [X] T032 [US3] Implementar historial live, mapa máximo2000 muestras y controles de recuperación en frontend/src/pages/LiveResultsPage.tsx, LiveAnalysisPage.tsx, SessionsPage.tsx y SessionDetailPage.tsx.

## Phase 6: Polish & validation

- [X] T033 Crear ensayo reproducible de sobrecarga600s y estabilidad7200s con medidas de memoria/almacenamiento en scripts/validate-live.ps1 y backend/tests/live_validation.py.
- [X] T034 Ejecutar pruebas de regresión, Ruff, build/Vitest y Playwright; registrar evidencia y limitaciones en specs/009-webcam-en-vivo/validation/implementation.md.
- [ ] T035 Ejecutar webcam real10min, ≥40 cruces anotados y medir p95 captura-pantalla/error por sentido; registrar hardware/encuadre y estado en specs/009-webcam-en-vivo/validation/hardware.md.
- [X] T036 Actualizar entorno/demo, quickstart y decisiones alineadas en .env.example, docs/decisiones-tecnicas.md y specs/009-webcam-en-vivo/quickstart.md; revisar toda la feature contra FR-001–021/SC-001–011 en validation/implementation.md.

## Dependencies & execution order

Setup → foundation → US1 → US2 → US3 → validation. T007/T009/T011 son independientes como pruebas; sus implementaciones siguen cada RED correspondiente. US2 requiere captura/job de US1 y US3 requiere checkpoint/transporte de US2. Los tests de cada historia se ejecutan también de forma aislada con fixtures propios.

## Parallel examples

US1: pruebas REST T013 y formulario T018 pueden redactarse separadamente tras foundation. US2: contrato WS T020 y pruebas de mensajes T023 afectan archivos distintos. US3: contratos históricos T029 y UI T031 se pueden preparar separadamente. Estas oportunidades no autorizan delegación automática; implementación en esta sesión, salvo revisión final exigida por la skill de ejecución.

## Implementation strategy

Entregar incrementos verificables con tests primero, actualizar casillas únicamente con evidencia y conservar registro duradero. US1 es el primer incremento funcional; continuar US2/US3 y validación conforme al objetivo autorizado, sin detenerse en un MVP parcial. No marcar pruebas físicas como aprobadas por resultados fake. Hooks Git opcionales disponibles mediante /speckit-git-commit; no necesarios para ejecutar las tareas.
