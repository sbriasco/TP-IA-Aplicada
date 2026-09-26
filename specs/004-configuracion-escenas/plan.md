# Implementation Plan: Carga, configuración y editor visual de escenas

**Branch**: `feature/004-configuracion-escenas` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-configuracion-escenas/spec.md`

**Azure Boards**: Feature #12 (Epic #1). User Stories #53, #54 y #55.

## Summary

La feature agrega:

- **Registro de videos locales**: sesiones `video_file` sobre videos locales. El navegador envía el archivo crudo, la API lo copia a `FLOWSIGHT_VIDEOS_DIR` calculando el SHA-256 en la misma pasada, lo sondea con OpenCV (frames contados, fps medido o estimado) y guarda en PostgreSQL los metadatos y el frame de referencia como JPEG, para que se vea desde cualquier equipo.
- **Cámaras registradas**: con nombre único, más la migración de las sesiones sintéticas existentes.
- **Configuración espacial versionada e inmutable por cámara**: locales con identidad estable, zonas y línea de entrada con la convención A/B del experimento 001. La validación geométrica se hace en píxeles del frame, y las versiones son inmutables (trigger en la base).
- **Compuerta de análisis**: `POST /sessions/{id}/jobs` con `video_analysis` exige una versión de la misma cámara con igual relación de aspecto. El trabajo queda asociado a esa versión y en `pending` hasta #56.
- **Editor SVG**: sobre el frame, con `viewBox` en píxeles del frame y controles nativos accesibles.

## Technical Context

**Language/Version**: Python 3.11.16; Node.js 22.20.0; TypeScript 5.9 con `strict`.

**Primary Dependencies**:
- Existentes: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3; React 19.1 y Vite 7.
- **Nueva en el backend**: `opencv-python-headless==4.10.0.84` (OpenCV ya está en el stack acordado; misma versión que el experimento 001, [R4](./research.md#r4-dependencia-nueva-del-backend)).
- Sin dependencias nuevas en el frontend.

**Storage**:
- PostgreSQL, local o Azure Flexible Server vía `FLOWSIGHT_DATABASE_URL`: cámaras, sesiones, metadatos del video, frame de referencia (`bytea`), versiones de escena y trabajos.
- Disco local: videos en `FLOWSIGHT_VIDEOS_DIR`.

**Testing**:
- pytest: unidades de geometría y sondeo, migración, contrato API e integración con PostgreSQL.
- Vitest: conversiones de coordenadas y estado del editor.
- Playwright: registro, editor, redimensionado y guardado.
- Los videos de prueba se generan en runtime ([R14](./research.md#r14-video-de-prueba-sin-subir-videos-a-git)).

**Target Platform**: Windows 10/11 en los equipos de desarrollo; CI en `ubuntu-latest` (backend y E2E) y `windows-latest` (build del frontend). Solo CPU.

**Project Type**: aplicación web monorepo (`backend/` + `frontend/`) con API y worker separados.

**Performance Goals**:
- SC-001: registrar un video de 5 min en < 30 s en la PC de desarrollo.
- SC-004: < 0,5 % de desvío de coordenadas al redimensionar.
- El detalle de sesión no rehashea si el archivo no cambió (caché por `(ruta, tamaño, mtime)`).

**Constraints**:
- El video nunca se guarda en la base (FR-007).
- No se exponen rutas absolutas ni credenciales en los errores (FR-013).
- Las variables nuevas son opcionales, para no romper los `.env` existentes.
- Las versiones son inmutables.
- No se hace refactor de las FK compuestas de specs/002.

**Scale/Scope**: seis integrantes; decenas de sesiones y cámaras; pocos locales por cámara; polígonos de ≤ 64 vértices; videos de minutos (hasta pocos GB).

No quedan `NEEDS CLARIFICATION`: todas las incógnitas se resolvieron en [research.md](./research.md) (R1 a R14).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | El video y su sondeo quedan en el equipo; la base se elige solo por URL; las migraciones son reversibles para tests; los videos de prueba se generan en runtime; las variables nuevas son opcionales | Aprobado |
| II. Responsabilidades separadas | Módulos nuevos `video/` (sondeo y almacenamiento), `scene/` (geometría y validación puras) y `services/scenes.py` (persistencia); la API solo orquesta; el worker no cambia salvo el filtro de claim | Aprobado |
| III. Trazabilidad y aislamiento | Frame de referencia con `frame_index` y `video_timestamp_seconds`; duración con base de tiempo del video; FK compuestas por cámara en versiones, locales y trabajos (FR-029); prueba con dos cámaras y dos sesiones (SC-008) | Aprobado |
| IV. Privacidad | `FLOWSIGHT_MACHINE_ID` con formato restringido y sin usuario del sistema; sin rutas absolutas en respuestas; la zona interior es opcional, y sin ella la permanencia interior queda "no disponible" | Aprobado |
| V. Eventos confiables | La convención A/B es idéntica a la del experimento 001 y está verificada con `scene.example.json`; el cruce se evalúa en #63; no se generan eventos en esta feature | Aprobado |
| VI. Analytics acotado | Sin chat ni LLM en esta feature | No aplica |
| VII. Evidencia e incrementos | Tres historias independientes (#53, #54, #55); pruebas de tolerancias, aislamiento, inmutabilidad y migración; mediciones de SC-001, SC-003 y SC-004 en `validation/` | Aprobado |

**Revisión post-diseño**: se mantiene. Hay una decisión que corrige documentación existente: el frame de referencia (una imagen, no un video) se guarda en PostgreSQL ([R5](./research.md#r5-frame-de-referencia-accesible-desde-cualquier-equipo-fr-006)). `docs/decisiones-tecnicas.md` decía "previews… no van en PostgreSQL salvo decisión posterior"; esta es esa decisión posterior y se registra en ese documento durante la implementación. No es una violación constitucional.

## Project Structure

### Documentation (this feature)

```text
specs/004-configuracion-escenas/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml             # endpoints nuevos/modificados
│   └── video-registration.md    # secuencia, errores y configuración de video
├── checklists/
│   ├── requirements.md
│   └── data-geometry.md
├── validation/                  # mediciones SC-001/003/004 (se crea al implementar)
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml / requirements.lock      # + opencv-python-headless
├── alembic/versions/0002_scene_configuration.py
├── src/flowsight/
│   ├── core/config.py                       # + videos_dir, machine_id opcionales
│   ├── db/models.py                         # + Camera, VideoSource, ReferenceFrame, Shop,
│   │                                        #   SceneVersion, SceneVersionShop, SceneZone,
│   │                                        #   SceneEntryLine; Session/ProcessingJob extendidos
│   ├── video/                               # nuevo
│   │   ├── probe.py                         # OpenCV: frames, fps, frame de referencia JPEG
│   │   ├── storage.py                       # copia por stream + SHA-256, .incoming, disponibilidad
│   │   └── fixtures.py                      # clips sintéticos para tests/E2E
│   ├── scene/                               # nuevo, puro (sin DB)
│   │   ├── geometry.py                      # px, área, intersección, lado A/B, aspecto
│   │   └── validation.py                    # reglas → SceneIssue (errores/advertencias)
│   ├── services/
│   │   ├── cameras.py                       # registro y get-or-create por name_key
│   │   ├── video_sessions.py                # registro y recarga transaccional
│   │   ├── scenes.py                        # crear versión (FOR UPDATE), consultar
│   │   └── jobs.py                          # + compuerta video_analysis
│   ├── api/routes.py, api/schemas.py        # endpoints de contracts/openapi.yaml
│   └── worker/lifecycle.py                  # claim filtrado por tipos soportados
└── tests/
    ├── unit/test_scene_geometry.py, test_scene_validation.py, test_video_probe.py, test_video_storage.py
    ├── integration/test_migration_0002.py, test_scene_isolation.py, test_scene_immutability.py
    └── contract/test_cameras_api.py, test_video_sessions_api.py, test_scene_api.py, test_jobs_gate_api.py

frontend/
├── src/
│   ├── App.tsx                              # router mínimo por pathname (+ ?job= existente)
│   ├── api/{cameras,sessions,scenes}.ts
│   ├── types/scene.ts
│   ├── pages/{SessionsPage,SessionDetailPage,SceneEditorPage}.tsx
│   ├── components/{VideoUploadForm,CameraPicker,SceneCanvas,ShopPanel,EntryLineControls,SceneIssues}.tsx
│   └── editor/{coordinates.ts,editorState.ts}  # + *.test.ts (Vitest)
└── e2e/scene-editor.spec.ts                 # + run-e2e.mjs genera un clip vía el venv del backend

.env.example                                 # + FLOWSIGHT_VIDEOS_DIR, FLOWSIGHT_MACHINE_ID
docs/decisiones-tecnicas.md                  # registrar R5 (frame de referencia en PostgreSQL)
README.md                                    # estado del proyecto y configuración de video
```

**Structure Decision**: se mantiene el monorepo de specs/002. La lógica geométrica queda pura en `scene/`, sin DB ni FastAPI, para que #63 (eventos) la reutilice desde el worker. El acceso a video queda en `video/` y lo reutiliza #56. Los servicios concentran transacciones y reglas de persistencia; la API solo traduce HTTP.

## Implementation Phases

1. **Fundaciones**: dependencia OpenCV (confirmar con el usuario), `Settings` opcionales, migración `0002` con datos de cámaras, modelos y trigger de inmutabilidad. Pruebas de migración, incluido el conflicto de nombres.
2. **US1 (#53)**:
   - Backend: `video/probe.py`, `video/storage.py`, servicio y endpoints de cámaras, registro, recarga, detalle y frame de referencia, con pruebas de errores y atomicidad.
   - Frontend: listado, alta de cámara, subida con progreso y detalle con disponibilidad.
3. **US2 (#54)**: `scene/geometry.py` y `scene/validation.py` con pruebas de tolerancias y A/B; servicio de versiones con numeración concurrente; endpoints de versiones; compuerta de trabajos y filtro de claim del worker; pruebas de aislamiento con dos cámaras y dos sesiones.
4. **US3 (#55)**: editor SVG (coordenadas, estado, vértices, líneas, sentido, errores mapeados, advertencia de salida); pruebas Vitest y E2E de Playwright.
5. **Cierre**: `.env.example`, README, `docs/decisiones-tecnicas.md`, CI (el lock nuevo), mediciones de SC-001, SC-003 y SC-004 en `validation/`.

US1 bloquea US2, porque una versión necesita una sesión con frame de referencia, y US2 bloquea el guardado de US3. La geometría pura de US2 se puede desarrollar en paralelo con US1.

## Verification Strategy

- **US1**: clips generados MJPG/AVI y mp4v/MP4; casos vacío, extensión inválida, texto renombrado y truncado; desconexión a mitad de la subida (sin sesión ni `.partial`); duplicado por hash; `missing` y `mismatch` al mover o reemplazar el archivo; recarga con el hash correcto e incorrecto; ninguna respuesta de error contiene la ruta absoluta de `FLOWSIGHT_VIDEOS_DIR`.
- **US2**: tabla de casos de geometría en el límite (9,99 y 10 px; 99 y 100 px²; 2 y 2,01 px; vértice que toca otra arista); A/B contra `scene.example.json`; dos guardados concurrentes con números distintos; `UPDATE`/`DELETE` rechazados por el trigger; compuerta en su orden (`scene_not_configured` → `other_camera` → `aspect_ratio_mismatch`) y 16:9 con otra resolución permitido; el trabajo `video_analysis` no lo reclama el worker actual.
- **US3**: Vitest para pantalla ↔ frame ↔ normalizado; Playwright registra un clip, dibuja un local, redimensiona tres veces, guarda y compara con la API (< 0,5 %); un error de autointersección se marca sin perder el dibujo; la advertencia de salida funciona; los controles se usan por rol y nombre accesible.
- **Regresión**: toda la suite y el E2E de specs/002 sin cambios.

## Complexity Tracking

No hay violaciones que justificar.
