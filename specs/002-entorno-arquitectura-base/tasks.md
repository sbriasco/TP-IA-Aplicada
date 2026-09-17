# Tasks: Entorno local reproducible y arquitectura base

**Input**: Design documents from `/specs/002-entorno-arquitectura-base/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Cada tarea funcional incluye las pruebas necesarias dentro del mismo entregable para mantener una lista compacta.

**Organization**: Las tareas se agrupan por User Story y representan resultados verificables, no archivos individuales.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede realizarse en paralelo sin editar los mismos archivos ni depender de una tarea incompleta.
- **[Story]**: User Story de `spec.md` a la que aporta.
- Antes de instalar cualquier dependencia, presentar versiones y comandos y esperar aprobación.

## Phase 1: Setup

**Purpose**: Crear la estructura mínima y fijar herramientas reproducibles.

- [X] T001 Crear la estructura `backend/`, `frontend/`, `scripts/` y `fixtures/synthetic/`; preparar `.node-version`, `.env.example`, exclusiones en `.gitignore` y manifiestos de dependencias en `backend/pyproject.toml` y `frontend/package.json`, solicitando aprobación antes de instalar o generar lockfiles.
- [X] T002 Configurar calidad y ejecución base en `backend/pyproject.toml`, `frontend/tsconfig.json`, `frontend/vite.config.ts` y `.github/workflows/ci.yml`, dejando CI en CPU y sin videos, pesos, GPU ni credenciales de Azure.

**Checkpoint**: Estructura y configuración preparadas; dependencias instaladas únicamente si fueron aprobadas.

---

## Phase 2: Foundational

**Purpose**: Proveer configuración, persistencia y contratos compartidos por todas las historias.

**⚠️ CRITICAL**: Las User Stories dependen de esta fase.

- [X] T003 Implementar configuración validada y arranque seguro en `backend/src/flowsight/core/config.py`, `backend/src/flowsight/api/main.py` y `backend/src/flowsight/worker/main.py`, con errores accionables sin secretos y pruebas en `backend/tests/unit/test_config.py`.
- [X] T004 Implementar modelos SQLAlchemy, estados y relaciones de `data-model.md` en `backend/src/flowsight/db/`, crear la migración inicial en `backend/alembic/versions/` y comprobar aplicación repetible, fallo seguro e integridad con pruebas PostgreSQL en `backend/tests/integration/test_migrations.py`.

**Checkpoint**: Configuración y esquema base disponibles para implementar historias.

---

## Phase 3: User Story 1 - Reproducir el entorno local (Priority: P1) 🎯 MVP

**Goal**: Preparar y diagnosticar FlowSight desde un clon limpio sin datos privados.

**Independent Test**: Seguir la guía con `.env.example`, ejecutar la comprobación y obtener componentes disponibles o un mensaje accionable ante cada requisito faltante.

- [X] T005 [US1] Implementar `scripts/check-environment.ps1` y documentar preparación, instalación local de PostgreSQL 17, orden de inicio y detención en `README.md`; validar escenarios correctos y faltantes en `backend/tests/integration/test_environment_check.py` y registrar el tiempo desde un clon limpio hasta la verificación satisfactoria, excluyendo descargas externas.

**Checkpoint**: US1 puede verificarse sin crear trabajos ni usar videos.

---

## Phase 4: User Story 2 - Persistir sesiones y trabajos sintéticos (Priority: P1)

**Goal**: Crear sesiones y trabajos persistidos con transiciones, fallos y recuperación.

**Independent Test**: Crear trabajos exitoso, fallido e interrumpido; reiniciar componentes y consultar estados, momentos y explicaciones persistidas.

- [X] T006 [US2] Implementar creación y consulta de sesiones y trabajos según `contracts/openapi.yaml` en `backend/src/flowsight/api/`, exponiendo el historial de transiciones y sus momentos junto al estado actual; implementar transiciones controladas en `backend/src/flowsight/services/jobs.py` y pruebas de contrato en `backend/tests/contract/test_sessions_jobs_api.py`.
- [X] T007 [US2] Implementar reclamo atómico de a un trabajo, carga idempotente y procesamiento del fixture determinista y recuperación `worker_interrupted` sin reintento en `backend/src/flowsight/worker/` y `fixtures/synthetic/base-flow.json`; probar concurrencia, reinicio y dos cargas consecutivas sin duplicados en `backend/tests/integration/test_worker_lifecycle.py`.

**Checkpoint**: US2 persiste y recupera sesiones y trabajos independientemente del frontend.

---

## Phase 5: User Story 3 - Mantener trazabilidad y aislamiento por sesión (Priority: P1)

**Goal**: Relacionar cada dato sintético con sesión, cámara, frame y timestamp sin mezclar contextos.

**Independent Test**: Procesar dos sesiones que reutilizan cámara, frame y `track_id`; toda observación y evento conserva su árbol correcto y timestamps válidos.

- [X] T008 [US3] Implementar generación y persistencia de frames, observaciones y eventos sintéticos en `backend/src/flowsight/synthetic/` y `backend/src/flowsight/services/trace.py`, rechazando timestamps y referencias inválidas mediante pruebas en `backend/tests/unit/test_synthetic_trace.py`.
- [X] T009 [US3] Implementar `GET /jobs/{job_id}/trace` en `backend/src/flowsight/api/` y pruebas PostgreSQL de aislamiento, claves repetidas y separación entre tiempo del video y tiempo operativo en `backend/tests/integration/test_session_isolation.py`.

**Checkpoint**: US3 demuestra trazabilidad completa y cero asociaciones cruzadas.

---

## Phase 6: User Story 4 - Previsualizar sin bloquear el trabajo (Priority: P2)

**Goal**: Entregar previews sintéticos a clientes normales, lentos o desconectados sin frenar el worker.

**Independent Test**: Conectar tres clases de cliente y comprobar un único pendiente, entrega del último frame previo al terminal y finalización independiente.

- [X] T010 [US4] Implementar el broker de último frame y el WebSocket de `contracts/preview-websocket.md` en `backend/src/flowsight/preview/` y `backend/src/flowsight/api/`, con JPEG sintético acotado y pruebas de cliente lento, tardío, reconectado y desconectado en `backend/tests/integration/test_preview_websocket.py`.
- [X] T011 [P] [US4] Implementar una pantalla mínima de supervisión accesible en `frontend/src/pages/JobPreviewPage.tsx` y su cliente REST/WebSocket en `frontend/src/api/`, con estados de API indisponible, conexión y terminal cubiertos en `frontend/tests/JobPreviewPage.test.tsx`.

**Checkpoint**: US4 funciona sin convertir la preview en fuente persistida ni bloquear trabajos.

---

## Phase 7: User Story 5 - Validar equipos de referencia (Priority: P2)

**Goal**: Registrar evidencia comparable del flujo base en CPU y GPU sin extrapolar rendimiento.

**Independent Test**: Ejecutar el mismo flujo en CPU y registrar GPU como aprobada, fallida o no evaluada con resultados y limitaciones anonimizados.

- [X] T012 [US5] Implementar recolección y anonimización de evidencia, tres ejecuciones del fixture y tres consultas de salud con medianas en `scripts/verify-base.ps1` y `backend/src/flowsight/core/environment_evidence.py`, con pruebas en `backend/tests/unit/test_environment_evidence.py`.
- [X] T013 [US5] Ejecutar y documentar la validación CPU y preparar el procedimiento reutilizable para la PC RTX 5080 en `specs/002-entorno-arquitectura-base/validation/README.md`, versionando solo el resumen anonimizado y permitiendo `not_evaluated` para GPU.

**Checkpoint**: US5 conserva evidencia medida sin volver obligatoria la GPU.

---

## Phase 8: Cierre transversal

**Purpose**: Comprobar el recorrido integral y dejarlo mantenible para el equipo.

- [X] T014 Ejecutar el recorrido completo de `quickstart.md`, todas las pruebas backend/frontend y CI, y registrar comandos, resultados y hallazgos en `specs/002-entorno-arquitectura-base/validation/base-verification.md`; cualquier defecto debe volver a la tarea responsable o proponerse como Bug de Azure antes de modificar alcance.
- [X] T015 Revisar exclusiones de Git, ausencia de secretos y datos privados, contratos y decisiones en `.gitignore`, `README.md`, `docs/decisiones-tecnicas.md` y `specs/002-entorno-arquitectura-base/`; verificar antes del PR los IDs de Azure creados mediante el flujo separado y previamente aprobado.

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Setup (T001–T002)
  └─ Foundational (T003–T004)
       └─ US1 (T005)
       └─ US2 (T006–T007)
            └─ US3 (T008–T009)
            └─ US4 (T010–T011)
       └─ US5 (T012–T013, después del flujo base)
            └─ Cierre (T014–T015)
```

- T001 precede instalaciones, lockfiles y configuración de herramientas en T002.
- T003 y T004 requieren la estructura y bloquean el trabajo funcional.
- US1 puede cerrarse después de la base fundacional.
- US2 produce los trabajos que consumen US3 y US4.
- US3 y US4 pueden avanzar en paralelo después de US2.
- US5 requiere el flujo base completo que medirá.
- T014 y T015 se ejecutan al finalizar las historias incluidas.

### Parallel Opportunities

- Después de T007, una persona puede trabajar en T008–T009 y otra en T010–T011.
- T011 puede avanzar en paralelo con T010 una vez acordado el contrato WebSocket, usando dobles de prueba.
- La documentación del procedimiento GPU de T013 puede prepararse mientras se termina T012; la evidencia se completa después.
- T015 puede comenzar como revisión documental mientras T014 ejecuta verificaciones, evitando editar simultáneamente los mismos archivos.

## Implementation Strategy

### Primer incremento

1. Completar T001–T004.
2. Completar T005 y validar US1.
3. Continuar con T006–T007 para obtener el primer flujo funcional persistido.

### Entrega incremental

1. **Entorno**: T001–T005.
2. **Sesiones y trabajos**: T006–T007.
3. **Trazabilidad y preview**: T008–T011, en paralelo si hay dos personas.
4. **Evidencia y cierre**: T012–T015.

## Notes

- Son 15 tareas deliberadamente agrupadas; no dividirlas por archivo salvo que aparezca un bloqueo real.
- Cada tarea funcional incluye sus pruebas para evitar una lista duplicada de implementación y testing.
- Las instalaciones requieren aprobación previa según `AGENTS.md`.
- Videos, pesos, bases, `.env`, outputs e informes privados no se suben a Git.
- Los cambios de Azure se proponen y aprueban por separado.

## Phase 9: Convergence

- [X] T016 [US4] Conectar el worker y la API para publicar previews sintéticos descartables entre procesos, generar JPEG válido de 320×180 y hasta 100 KiB, aplicar la frecuencia máxima configurada y verificar el WebSocket real con clientes normal, lento, tardío, reconectado y desconectado per US4, FR-013, FR-014, FR-020 y SC-007 (missing/partial).
- [X] T017 [US1] Comprobar la conexión con PostgreSQL antes de exponer la API y evitar que `/health` informe disponibilidad cuando el almacenamiento obligatorio no responde per FR-022 y US1/AC2 (contradicts).
- [X] T018 [US4] Obtener el `job_id` de una entrada navegable, manejar trabajos inexistentes y verificar en navegador el recorrido conexión, preview y estado terminal per Constitución VII, US4 y T011 (partial).

## Phase 10: Convergence

- [X] T019 [US4] Verificar contra la API, el worker y el WebSocket reales los clientes lento, tardío, reconectado y desconectado, comprobando último frame, estado REST y finalización independiente per SC-007 y T016 (partial).
- [X] T020 [US4] Resolver el ejecutable del worker E2E según la plataforma y validar que el recorrido configurado en GitHub Actions funcione en Ubuntu además de Windows per FR-017, SC-008 y CI E2E (contradicts).
