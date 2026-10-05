# Análisis en vivo con webcam — Implementation Plan

> **For agentic workers:** ejecutar por incrementos mediante `superpowers:executing-plans` o `superpowers:subagent-driven-development`, según el método elegido por el usuario. Este comando entrega diseño; la lista ejecutable de tareas se genera con `/speckit-tasks`.

**Branch**: `feature/009-webcam-en-vivo` | **Date**: 2026-10-03
**Spec**: [spec.md](./spec.md)
**Estado de ejecución 2026-10-05**: software implementado; progreso/evidencia en tasks.md y validation/implementation.md. Validación física y larga duración pendientes. Las listas de esta planificación conservan sus requisitos compuestos de validación/Git y no sustituyen el estado de tareas.
**Goal**: Preparar una webcam, analizar cruces y mostrarlos junto a la imagen, conservar resultados y mapa de calor sin grabar video.
**Architecture**: Worker local con fuente intercambiable y captura aislada, contador temporal separado de archivos y persistencia incremental. La API recibe actualizaciones transitorias por WebSocket y entrega a cada observador el último resultado completo. El frontend diferencia preparación, vista de vivo e historial webcam del recorrido de archivos.
**Tech Stack**: Python/FastAPI/Pydantic, OpenCV, YOLO11m/ByteTrack, PostgreSQL/SQLAlchemy/Alembic; React/TypeScript strict/Vite, CSS Modules, SVG, Recharts. Sin dependencias nuevas.
**Azure Boards**: No vincular ni publicar esta feature por instrucción del usuario; es un agregado para la expo del profesor, fuera del TP.

## Summary

Las aclaraciones y CF-01–07 se implementan con origen `webcam`, trabajo `live_analysis` y tablas específicas de cruces/muestreo. `video_file` y `synthetic` conservan contratos. El tiempo analítico parte del primer frame de captura válido después de iniciar; preparación y carga del modelo quedan fuera. «Detener» solicita cierre normal, nunca invoca cancelar. Las métricas comerciales y el chat de webcam siguen fuera.

Diseño y motivos: [research.md](./research.md). Esquema: [data-model.md](./data-model.md). Contratos: [API y WS](./contracts/live-api.md), [fuente](./contracts/capture-source.md) y [UI](./contracts/live-ui.md). Validación: [quickstart.md](./quickstart.md).

## Global Constraints

- Una webcam conectada al equipo del worker; no usar captura del navegador ni servicios cloud para visión.
- No grabar video ni snapshots/overlays del vivo; únicamente frame de referencia persistente, datos de eventos y muestra acotada.
- Conservar escenas inmutables, relación de aspecto con tolerancia existente del 1 %, bajas lógicas y números retirados.
- Todos los tiempos de negocio del vivo provienen de captura; secuencia y segmento evitan continuidad artificial.
- Los cruces por minuto son distintos del flujo de visitas; no producir visitas únicas, ocupación, permanencia ni indicadores comerciales de webcam.
- Modelo/locks vigentes; cualquier nueva dependencia requeriría consulta. No instalar paquetes en planificación.
- Pytest y Playwright con cámara/detector fake y PostgreSQL local; hardware/GPU se evalúan aparte.

## Review Focus

- Cambio de dispositivo índice USB después de desconectar: no reanudar conteo sin confirmación de encuadre.
- Lectura nativa OpenCV bloqueada: liberar captura por terminación del proceso auxiliar sin bloquear la API.
- Cruce al final de un minuto confirmado después: atribuir al timestamp original y actualizar ese minuto.
- Fallo de PostgreSQL durante el vivo: no crecer en memoria ni presentar datos no persistidos como historial final.
- Reinicio de API o pantalla: reconectar con acumulados autoritativos, sin reenviar incrementos ni reiniciar el análisis.

## Technical Context

**Language/Version**: Python 3.11.x (CI 3.11.16), TypeScript 5.9.2 strict, Node 22.20.0.
**Primary Dependencies**: FastAPI 0.141.1, SQLAlchemy 2.0.54, Alembic 1.20.0, OpenCV headless 4.10.0.84, NumPy 2.4.6, Ultralytics 8.4.153, torch 2.7.1+cpu, torchvision 0.22.1+cpu, websockets 17.1; React 19.1.1, Vite 7.3.6, Recharts 3.10.1. Pydantic sigue el lock existente. CUDA se rige por el entorno ya documentado.
**Storage**: PostgreSQL 17 local/test; Azure opcional por `FLOWSIGHT_DATABASE_URL`. Frame de referencia bytea existente; sin archivos derivados del vivo. Muestreo máximo 20.000 filas por análisis.
**Testing**: pytest 9.1.1, Ruff 0.13.2, Vitest 5.0.1 y Playwright del lock. Pruebas unitarias temporales, contratos, migración desde 0008, integración worker/API y E2E con fuente reproducible.
**Target Platform**: Windows en demo; Linux en CI con fuente fake. Webcam física no es requisito CI.
**Project Type**: aplicación web monorepo; API y worker separados, un worker por PC.
**Performance Goals**: SC-002 p95 captura-pantalla ≤2 s en PC demo, ensayo 10 min; SC-003 sobrecarga 3× por 10 min sin cola creciente; SC-007 2 horas tranquilas con memoria final ≤1,2× mediana posterior al calentamiento. Objetivos no demostrados.
**Constraints**: preview hasta 5 Hz, 1 MiB por mensaje, un frame pendiente, 1 resultado pendiente por productor/observador, continuidad máxima 1 s y oscilación 1/3 s iniciales; límites y manejo de fallos en research.
**Scale/Scope**: sesiones de 2–3 horas, >200 asistentes acumulados con concurrencia visible desconocida; hasta 20 locales por escena, una cámara activa, hasta 8 observadores de vivo por API.

## Constitution Check

GATE previo a investigación: la spec usa tiempo observado de captura; la redacción III de constitución 1.0.1 solo mencionaba archivos. Se aclaró como 1.0.2 sin cambiar el principio, y se alinearon AGENTS.md y decisiones técnicas; no se usa tiempo de inferencia. Gate de diseño aprobado.

| Principio | Evidencia del diseño | Resultado |
|---|---|---|
| I · Local/reproducible | OpenCV/YOLO locales; fuente fake sin webcam, GPU ni Azure | Cumple |
| II · Separación | Fuente, reglas temporales, persistencia, transporte y UI diferenciados | Cumple |
| III · Tiempo/aislamiento | Captura monótona; FK compuestas y segmentos; archivos conservan tiempo de video | Cumple |
| IV · Privacidad | IDs temporales; sin video ni identidad; muestra de pies limitada | Cumple |
| V · Eventos | Oscilación temporal, límite de continuidad y cruces confirmados por vencimiento | Cumple |
| VI · Analytics | APIs acotadas; webcam explícitamente no disponible para chat | Cumple |
| VII · Evidencia | Ensayos medibles, pruebas fake y regresiones; registro local, sin Boards por instrucción del usuario | Cumple en diseño |

Post-diseño: no nuevas dependencias, servicios cloud ni cambios de modelo. La afinidad de equipo impide que otro worker reclame una webcam compartida por DB. Hardware, precisión, latencia y límites de memoria requieren pruebas de implementación; no se presentan como verificados.

## Project Structure

### Documentation (this feature)

```text
specs/009-webcam-en-vivo/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── cross-feature-analysis.md
├── contracts/
│   ├── live-api.md
│   ├── capture-source.md
│   └── live-ui.md
└── tasks.md                 # siguiente comando, no creado aquí
```

### Source Code (paths propuestos; sin implementación en esta fase)

```text
backend/alembic/versions/0009_live_capture.py
backend/alembic/versions/0010_live_capture_schema.py
backend/src/flowsight/
├── capture/                # contracts.py, webcam.py, process.py, fake.py
├── vision/                 # live_spatial.py, live_sampling.py; detector reset
├── worker/                 # live_analysis.py, live_control.py; lifecycle/main
├── preview/                # live_messages.py, live_channel.py; broker existente separado
├── services/               # live_sessions.py, live_jobs.py, live_results.py
├── api/                    # live_routes.py, live_schemas.py; extensiones source-aware
└── db/models.py            # modelos aditivos
backend/tests/{unit,contract,integration}/test_live_*.py
frontend/src/
├── pages/                  # LivePreparationPage.tsx, LiveAnalysisPage.tsx, LiveResultsPage.tsx
├── components/             # WebcamPreparationForm.tsx, CrossingChart.tsx
├── api/                    # live.ts
├── types/                  # live.ts; session.ts/processedSessions.ts extendidos
└── navigation.ts           # router existente
frontend/tests/Live*.test.tsx
frontend/e2e/live-webcam.spec.ts
scripts/validate-live.ps1
```

Extender `frontend/src/navigation.ts`, sin crear una segunda capa de router. `api/routes.py` solo conecta rutas existentes a servicios; rutas de vivo se agregan en módulo propio. `SceneCanvas`, `Split`, `MetricCard` y `PositionHeatmap` se reutilizan; no refactor ajeno de archivos.

## Phase 0 · Investigación cerrada

R1–R10 resuelven preparación, lectura bloqueante, modelo, temporalidad, control, transporte, muestreo, historia, latencia y gobierno. Se consultaron contratos locales y documentación primaria; no se ejecutó hardware ni se instaló software. Todas las incógnitas de diseño tienen una decisión y alternativa descartada en research. Valores iniciales son configurables y deben validarse sin cambiar resultados de archivos.

## Phase 1 · Diseño e incrementos para tareas

### Incremento 1 · Origen y preparación (FR-001/002/017)

**Files**: migraciones 0009/0010, `db/models.py`, `capture/contracts.py`, `capture/process.py`, `capture/webcam.py`, `worker/live_control.py`, `services/live_sessions.py`, `api/live_routes.py`, `api/live_schemas.py`, `core/config.py`.
**Interfaces**: `FrameSource.start()`, `read_latest(after_sequence: int, timeout_s: float) -> CapturedFrame | None`, `stop(timeout_s: float) -> None`; `prepare_live_session(database, request: LivePrepareRequest, capture: CaptureProbeResult) -> Session`.
- [ ] Escribir y ejecutar pruebas de origen webcam, preparación sin job, dispositivo ausente, abandono y frame compartido; deben fallar antes de implementación.
- [ ] Implementar protocolo fake/real, proceso auxiliar y preparación por canal local; respetar contrato y locks de máquina/cámara.
- [ ] Verificar migración desde 0008 sin pérdida de sesiones/escenas y cierres acotados con proveedor que nunca retorna; revisar y guardar incremento en Git.

### Incremento 2 · Tracking y reglas temporales (FR-004–007/009/020)

**Files**: `vision/live_spatial.py`, `vision/live_sampling.py`, `vision/detector.py`, `vision/ultralytics_tracker.py`, `tests/unit/test_live_spatial.py`, `test_live_sampling.py`.
**Interfaces**: `LiveSpatialCounter.observe(frame: CapturedFrame, detections: Sequence[Detection]) -> list[LiveCrossingFact]`, `advance(timestamp_s: Decimal) -> list[LiveCrossingFact]`, `discontinue(timestamp_s: Decimal) -> None`; `LivePositionSampler.observe(...) -> list[PositionSlotChange]`.
- [ ] Escribir/ejecutar casos calculados a mano: ida/vuelta dentro y fuera de 1/3 s, cruce fuera del segmento, hueco >1 s, ID reutilizado y confirmación de minuto 59,9 en 60,3; contar exactamente lo esperado.
- [ ] Implementar política temporal solo para vivo, reset de tracker por segmento y reservoir de 20.000 muestras.
- [ ] Verificar regresiones de `test_spatial_counts.py` y muestreo uniforme reproducible con RNG inyectado; revisar y guardar incremento.

### Incremento 3 · Trabajo, persistencia y cierre (FR-003/012–015/017/021)

**Files**: `worker/live_analysis.py`, `worker/lifecycle.py`, `worker/main.py`, `services/live_jobs.py`, `services/live_results.py`, `tests/integration/test_live_analysis_job.py`.
**Interfaces**: `process_live_analysis_job(factory, job_id: UUID, *, settings: Settings, now: Callable[[], datetime], source_factory: SourceFactory) -> None`; `request_live_stop(database, job_id: UUID, occurred_at: datetime) -> ProcessingJob`.
- [ ] Escribir/ejecutar integración fake: timestamps, flush 1 s, idempotencia, stop completado con huecos, fallos y dos PCs con mismo DB sin robo de webcam.
- [ ] Implementar afinidad/exclusión, heartbeat/control, cruces y buckets transaccionales, cierre y recuperación scoped; nunca llamar `persist_completed_scene` para vivo.
- [ ] Probar pérdida DB >5 s con memoria acotada y fallo seguro, y cancelación de archivos sin cambios; revisar y guardar incremento.

### Incremento 4 · Canal transitorio y lecturas (FR-010/011/013/014/019)

**Files**: `preview/live_messages.py`, `preview/live_channel.py`, `api/live_routes.py`, `api/main.py`, `services/position_samples.py`, `services/processed_sessions.py`, guard de chat por origen.
**Interfaces**: `LiveBroker.publish(update: LiveUpdate) -> None`, `latest(job_id: UUID) -> LiveUpdate | None`; rutas y errores exactos en contracts/live-api.md.
- [ ] Escribir/ejecutar contratos con productor/observador lento, payload fuera de sesión, reconexión de API y mensaje >1 MiB; verificar que inferencia continúa y no hay archivos JPEG/preview.
- [ ] Implementar WS loopback validado, último resultado, heartbeat y control duplex; lectura histórica de cruces/muestra sin archivo y guard de chat antes de LLM.
- [ ] Verificar que productor no bloquea inferencia, TTL de imagen y rechazo de ID de otro equipo; revisar y guardar incremento.

### Incremento 5 · Recorrido web (FR-001–003/008/010–013/019)

**Files**: tipos/API/navigation/App, páginas LivePreparation/LiveAnalysis/LiveResults, CrossingChart, SessionsPage/SessionDetailPage, tests/frontend y E2E fake.
**Interfaces**: `prepareLiveSession`, `startLiveAnalysis`, `stopLiveAnalysis`, `getLiveResults`, `subscribeLivePreview` consumen contratos; tipos discriminados con validación runtime sin `any`.
- [ ] Escribir/ejecutar tests por rol/nombre: preparar/editor/start, pares imagen+cifras, rechazo fuera de orden, stop y consulta histórica sin video.
- [ ] Implementar selector de sentidos y local, etiquetas parciales/cobertura, reconexión, gráfico «Cruces por minuto» y mapa con máximo 2.000 puntos renderizados.
- [ ] Verificar Playwright reload/pantalla desconectada, reanudación confirmada por operador y chat no disponible; revisar y guardar incremento.

### Incremento 6 · Evidencia y regresiones (FR-015/018 y SC-001–011)

**Files**: `scripts/validate-live.ps1`, fixture fake, `frontend/e2e/run-e2e.mjs`, CI existente, evidencia anonimizada en `validation/` y documentación de demo.
- [ ] Probar sobrecarga fake 3× y ensayo 2 horas con medidas de memoria de todos los procesos de captura/worker/API; no basta contar frames pendientes.
- [ ] Ejecutar suite y build aprobados; realizar webcam real 10 min/40 cruces manuales sin grabación y dejar estado medido o no evaluado.
- [ ] Registrar p95 captura-pantalla, error por ocurrencia y sentido, hardware/modelo y límites; si falla un objetivo, ajustar encuadre/configuración o declarar limitación. No prometer 200 detecciones simultáneas.

## Verification and Handoff

Los comandos y datos de prueba están en quickstart. La planificación se validó por coherencia documental, contratos y límites. Posteriormente se generó tasks.md y se implementó en incrementos con pruebas; consultar validation/implementation.md para evidencia actual y hardware.md para aceptación pendiente.

## Complexity Tracking

No excepciones constitucionales. Un auxiliar de captura y canal local son necesarios para lectura bloqueada y API/worker separados; se reutilizan librerías estándar y dependencias fijadas, sin servidor de streaming ni infraestructura adicional.
