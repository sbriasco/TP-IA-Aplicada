# Implementation Plan: Procesamiento y seguimiento con vista en vivo

**Branch**: `feature/005-procesamiento-tracking` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-procesamiento-tracking/spec.md`

**Azure Boards**: Feature #13 (Epic #1). User Stories #56, #57, #58, #59 y #60.

## Summary

El worker deja de ignorar `video_analysis`. Toma un trabajo por vez, recorre el video ya registrado con la versión de escena elegida y cierra el seguimiento anónimo:

- Detección y tracking detrás de una interfaz. En CI y en el recorrido reproducible se usa un detector falso. En un video real, Ultralytics YOLOv8n + ByteTrack, las versiones del experimento 001 ([R1](./research.md#r1--detector-y-tracker)).
- No se guarda una fila por persona y por fotograma. Los cruces y las tres medidas oficiales van a PostgreSQL; la trayectoria es un JSONL cada 5 fotogramas, en disco ([R2](./research.md#r2--qué-se-guarda-y-qué-no), [R3](./research.md#r3--entradas-salidas-y-ocupación-visible)).
- La vista reutiliza el WebSocket de specs/002. El video real publica `schema_version` `2`, con el fotograma y su instante. El tope de 320×180 queda solo para el flujo sintético ([R5](./research.md#r5--vista-en-vivo)).
- El avance es fotogramas del video. Cancelar agrega el estado `cancelled`, distinto de `failed` ([R4](./research.md#r4--estados-incluido-cancelado), [R7](./research.md#r7--avance)).
- La evidencia de la PC de referencia no entra en CI ([R6](./research.md#r6--pruebas-sin-el-equipo-de-referencia)).

## Technical Context

**Language/Version**: Python 3.11.16; Node.js 22.20.0; TypeScript 5.9 con `strict`.

**Primary Dependencies**:
- Existentes: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3, OpenCV headless 4.10.0.84, React 19.1, Vite 7.
- Nuevas en el lock del backend, ya acordadas en el stack y fijadas por el experimento 001: `ultralytics==8.4.153`, `torch==2.7.1+cpu`, `torchvision==0.22.1+cpu`. El proceso de la API no las importa. El wheel de GPU no entra al lock de CI.

**Storage**:
- PostgreSQL, local o Azure Flexible Server vía `FLOWSIGHT_DATABASE_URL`: estado del trabajo, cruces confirmados y medidas oficiales.
- Disco local, bajo `FLOWSIGHT_VIDEOS_DIR`: el video ya registrado y el JSONL de trayectoria. La API no devuelve rutas absolutas.

**Testing**:
- pytest, con `pytest.mark.gpu` excluido de la suite y de CI.
- El detector falso cubre estados, conteos, aislamiento, cancelación y vista.
- Playwright: vista en vivo y cancelación contra ese detector.
- La medición de la PC de referencia queda en `validation/` y no bloquea CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest` para backend y E2E, `windows-latest` para el build del frontend. CPU en la suite. GPU solo en la medición manual.

**Project Type**: aplicación web monorepo (`backend/` + `frontend/`) con API y worker separados.

**Performance Goals**:
- No hay meta de tiempo real. La velocidad se mide y se registra.
- SC-003: al 50 % de los fotogramas, el avance informado es el 50 %, con tolerancia de un fotograma.
- SC-002: el instante declarado de la imagen y el del fotograma coinciden.
- SC-006: un video real de menos de dos minutos termina en el equipo de referencia y el resumen trae dispositivo, versiones y fotogramas por segundo de procesamiento.

**Constraints**:
- Un solo trabajo `processing` por equipo. El claim sigue siendo `FOR UPDATE SKIP LOCKED`.
- Tiempos de negocio con el instante del video.
- `track_id` temporal, por sesión y cámara. Sin identidad ni seguimiento entre cámaras.
- La compuerta de escena de specs/004 no se redefine.
- Al completar, entradas, salidas y ocupación visible son los números oficiales. No hay un segundo cálculo.
- `cancelled` no reemplaza a `failed` ni a `worker_interrupted`.

**Scale/Scope**: seis integrantes; un video a la vez; clips de pocos minutos; pocos locales por cámara. Fuera de alcance: el resto de métricas, el tablero, el chat y el mapa de calor.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R7).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | El video se procesa en el equipo. CI usa el detector falso, sin GPU ni peso. El lock de CPU no exige el wheel gráfico. La migración es la 0004 | Aprobado |
| II. Responsabilidades separadas | `vision/` no importa FastAPI ni la base. El worker orquesta. `services/` persiste medidas y cruces. La API no importa Ultralytics. La geometría de `scene/` se reutiliza | Aprobado |
| III. Trazabilidad y aislamiento | Cada cruce y cada medida llevan sesión, local e instante de video. El avance no usa el reloj de pared. Dos sesiones con el mismo `track_id` quedan separadas | Aprobado |
| IV. Privacidad | El identificador no es una persona. No hay reconocimiento facial ni seguimiento entre cámaras. La ocupación es la visible en la zona frontal. Perder el seguimiento no inventa permanencia | Aprobado |
| V. Eventos confiables | Oscilación de 10 fotogramas, igual que el experimento. Un cambio de identificador no suma un cruce. Las tres medidas oficiales no se recalculan después | Aprobado |
| VI. Analytics acotado | Esta feature no llama al modelo de chat ni expone SQL | No aplica |
| VII. Evidencia e incrementos | Historias #56 a #60. La prueba de GPU queda fuera de CI y el resumen versionable no lleva nombre de máquina ni rutas | Aprobado |

**Revisión post-diseño**: se mantiene. El JSONL de trayectoria y el JPEG de la vista quedan fuera de PostgreSQL, como ya dice `docs/decisiones-tecnicas.md`. Agregar `cancelled` no renombra los estados de specs/002.

## Project Structure

### Documentation (this feature)

```text
specs/005-procesamiento-tracking/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── preview-websocket.md
│   └── trajectory-sample.md
├── checklists/
│   └── requirements.md
├── cross-feature-analysis.md
├── validation/                  # resumen de la PC de referencia (al medir)
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml / requirements.lock       # + ultralytics y torch CPU
├── alembic/versions/0004_video_analysis.py  # cancelled, medidas, cruces, avance
├── src/flowsight/
│   ├── vision/                              # puro: sin FastAPI ni DB
│   │   ├── detector.py                      # interfaz
│   │   ├── fake.py                          # secuencia fija para tests
│   │   ├── ultralytics_tracker.py           # yolov8n + ByteTrack
│   │   ├── spatial.py                       # pie, cruce, oscilación de 10 fotogramas
│   │   └── trajectory.py                    # JSONL cada 5 fotogramas
│   ├── services/measures.py                 # medidas oficiales y parciales
│   ├── services/jobs.py                     # + cancelled, result_complete
│   ├── worker/lifecycle.py                  # claim de video_analysis
│   ├── worker/video_analysis.py             # bucle por fotograma, corte al cancelar
│   └── api/routes.py, api/schemas.py        # cancel, measures, trajectory
└── tests/
    ├── unit/test_spatial_counts.py, test_trajectory_sample.py
    ├── integration/test_video_analysis_job.py
    └── contract/test_video_analysis_api.py

frontend/
├── src/pages/JobPreviewPage.tsx             # schema 2, avance, medidas, cancelar
├── src/api/jobs.ts
└── e2e/video-analysis.spec.ts               # detector falso
```

**Structure Decision**: se mantiene el monorepo de specs/002. La API no carga el modelo. El worker es el único que elige `fake` o Ultralytics según `FLOWSIGHT_DETECTOR`. Las reglas de cruce viven en `vision/spatial.py` para que la feature de métricas lea los números ya cerrados en vez de volver a interpretar la línea.

## Implementation Phases

1. **Estados y persistencia**: migración `0004` (`cancelled`, columnas de avance y versiones, `analysis_measures`, `line_crossings`). Transiciones `pending|processing → cancelled`. `result_complete` solo en `completed`. Prueba de que un `processing` interrumpido sigue yendo a `failed`.
2. **US1 (#56)**: interfaz del detector, falso y Ultralytics; bucle del worker sobre `video_analysis`; muestra JSONL; pie en el centro inferior; versiones del método en el trabajo. El claim incluye este tipo y sigue siendo uno por vez.
3. **US3 (#58)**: avance por fotogramas; medidas parciales por local; al completar, las mismas filas pasan a oficiales (`partial=false`). Oscilación y cambio de identificador no suman.
4. **US2 (#57)**: `schema_version` `2` en el WebSocket, con el fotograma dibujado y el mismo instante. El flujo sintético no cambia. La página de vista muestra avance y medidas.
5. **US5 (#59)**: `POST /jobs/{id}/cancel`. El worker se detiene en el límite del fotograma y no pisa un `cancelled` con `completed`.
6. **US4 (#60)**: marca `gpu` fuera de CI; script de evidencia en `validation/`. Si no hay dispositivo gráfico, el mismo video corre en CPU y el resumen lo dice.

#56 bloquea al resto. La interfaz falsa de #56 permite probar #58, #57 y #59 sin el peso.

## Verification Strategy

- **#56**: el detector falso completa un trabajo; no existe una fila por fotograma; el JSONL tiene una muestra cada 5 fotogramas; el pie es el centro inferior; dos sesiones no mezclan `track_id`.
- **#58**: a la mitad de los fotogramas el avance es 50 % ± 1 fotograma; las medidas se ven `partial=true` y, al completar, `partial=false` sin una segunda fila; la oscilación de 10 fotogramas y un cambio de identificador no aumentan entradas ni salidas.
- **#57**: el mensaje `2` trae el mismo `frame_index` que la imagen; un cliente lento conserva un solo mensaje pendiente; el sintético sigue en `schema_version` `1`.
- **#59**: cancelar deja `cancelled` y `result_complete=false`; no hay fotogramas posteriores; reiniciar el worker no lo retoma. Una caída sigue en `failed` / `worker_interrupted`.
- **#60**: la suite por defecto no recolecta `gpu`. El resumen manual de la PC de referencia no contiene rutas ni nombre de equipo.
- **Regresión**: suites de specs/002 y specs/004 en verde, incluida la compuerta de escena.

## Complexity Tracking

No hay violaciones que justificar.
