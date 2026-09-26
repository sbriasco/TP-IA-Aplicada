---
description: "Tareas de validación del servicio de modelo Azure AI Foundry"
---

# Tasks: Validación del servicio de modelo de Azure

**Input**: Design documents from `/specs/003-validacion-modelo-azure/`

**Azure Boards**: Feature #5. Las User Stories/Tasks de Boards se proponen **después** de este archivo y solo se crean con aprobación explícita (skill `ado-work-items`).

**Prerequisites**: `plan.md`, `spec.md` (post-clarify), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Unitarias sin Azure incluidas (config, fake tool, tool loop mock, redaction). Llamadas reales a Foundry = procedimiento local, no CI.

**Organization**: Por User Story; resultados verificables.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Paralelo (archivos distintos, sin depender de tarea incompleta).
- **[Story]**: US1–US4 de `spec.md`.
- Antes de instalar SDK: presentar paquete/versión y esperar aprobación.

## Phase 1: Setup

**Purpose**: Estructura del módulo y exclusiones sensibles.

- [x] T001 Crear `backend/src/flowsight/llm/` con `__init__.py` y `specs/003-validacion-modelo-azure/validation/` con `.gitignore` que excluya claves, dumps crudos y `.env`; incluir plantilla de resumen según `contracts/validation-evidence.md`
- [x] T002 [P] Extender `.env.example` con variables de `contracts/azure-model-config.md` (sin secretos) y aclarar en `specs/003-validacion-modelo-azure/quickstart.md` que API/worker no las exigen para arrancar

**Checkpoint**: Estructura lista; sin SDK Azure instalado.

---

## Phase 2: Foundational

**Purpose**: Settings opcionales, tool ficticia y redaction (bloquean historias de red).

- [x] T003 Implementar settings Azure opcionales (API key) en `backend/src/flowsight/llm/settings.py` con fallos accionables sin eco de secretos y pruebas en `backend/tests/unit/test_llm_config.py`
- [x] T004 [P] Implementar `get_session_traffic` según `contracts/fake-analytics-tool.md` en `backend/src/flowsight/llm/fake_tools.py` con pruebas en `backend/tests/unit/test_llm_fake_tool.py`
- [x] T005 [P] Implementar evidencia/redaction en `backend/src/flowsight/llm/evidence.py` (nunca serializar keys ni headers) con prueba unitaria de redaction en `backend/tests/unit/test_llm_evidence.py`

**Checkpoint**: Fake tool y config probables sin red Foundry.

---

## Phase 3: User Story 1 - Acceso Foundry y deployment/modelo (Priority: P1) 🎯 MVP

**Goal**: Inventario de acceso; registrar modelo **habilitado** (`gpt-5-mini`); documentar región/deployment/modelo o bloqueo.

**Independent Test**: Paso de inventario del script deja `available`/`blocked`/`not_evaluated` sin tool calling.

- [x] T006 [US1] Implementar inventario en `backend/src/flowsight/llm/inventory.py` registrando `AzureAccessInventory` (`service_kind=azure_ai_foundry`, `auth_method=api_key`, modelo habilitado + `model_selection_notes`). **Sin SDK nuevo** en esta tarea: basarse en variables `.env`, documentación del portal Foundry y, si hace falta, sonda HTTP con stdlib; proponer paquete candidato solo al final de T008
- [x] T007 [US1] Crear `scripts/validate-azure-model.ps1` con paso de inventario que lea `.env`, invoque el módulo y escriba salida local en `specs/003-validacion-modelo-azure/validation/` sin secretos
- [x] T008 [US1] Ejecutar inventario contra el proyecto Foundry compartido (o registrar bloqueo) y completar borrador de evidencia de acceso; **no instalar SDK sin aprobación**; proponer paquete/versión candidato según endpoint descubierto

**Checkpoint**: Foundry usable (o bloqueo) + deployment/modelo habilitados documentados.

---

## Phase 4: User Story 2 - Llamada simple (Priority: P1)

**Goal**: Completion autenticada vía script local.

**Independent Test**: Una invocación produce texto del modelo o error seguro; sin PostgreSQL, frontend ni HTTP de chat.

**Dependency**: US1 con `available` (si bloqueado → `not_evaluated`, no forzar éxito).

- [x] T009 [US2] Tras aprobación, añadir la dependencia candidata en `backend/pyproject.toml` / lockfile alineada al endpoint Foundry de US1
- [x] T010 [US2] Implementar cliente mínimo de completion en `backend/src/flowsight/llm/client.py` usando endpoint, API key y deployment de settings
- [x] T011 [US2] Integrar la llamada simple en `scripts/validate-azure-model.ps1`, registrar `ModelCallResult` con `latency_ms` (criterio SC-003: ≤5 min una vez configurado) en evidencia local (corrida mínima)
- [x] T012 [US2] Verificar que fallos de auth/config no imprimen secretos (aserción en `backend/tests/unit/test_llm_config.py` o prueba dedicada)

**Checkpoint**: Camino de red autenticado o bloqueo documentado.

---

## Phase 5: User Story 3 - Tool calling ficticio (Priority: P1)

**Goal**: Ciclo modelo → `get_session_traffic` → modelo → respuesta.

**Independent Test**: Con `demo-session-001`, evidencia muestra tool, resultado hardcodeado y respuesta basada en él; o `not_supported`/`not_evaluated`.

**Dependency**: Cliente US2 operativo.

- [x] T013 [US3] Implementar orquestación mínima de tool calling en `backend/src/flowsight/llm/tool_loop.py` registrando solo la herramienta ficticia
- [x] T014 [US3] Añadir el paso de tool calling a `scripts/validate-azure-model.ps1` con prompt de prueba estable (`demo-session-001`)
- [x] T015 [US3] Ejecutar la corrida mínima real (o documentar `not_supported`/`not_evaluated`) y adjuntar traza redactada a `specs/003-validacion-modelo-azure/validation/`
- [x] T016 [P] [US3] Pruebas unitarias del orquestador con cliente mock en `backend/tests/unit/test_llm_tool_loop.py` (camino feliz y `session_id` desconocido)

**Checkpoint**: Tool calling con estado explícito `demonstrated` | `not_supported` | `not_evaluated`.

---

## Phase 6: User Story 4 - Cuotas, env y evidencia (Priority: P2)

**Goal**: Guía reproducible + resumen anonimizado + cuotas/costos o `not_measured`.

**Independent Test**: Otro integrante configura `.env` contra Foundry compartido y obtiene el mismo tipo de resultado.

- [x] T017 [US4] Completar resumen anonimizado versionable en `specs/003-validacion-modelo-azure/validation/` (`README.md` y/o `summary.json`) según `contracts/validation-evidence.md`, con `runs_policy: minimal`, `latency_ms` de la llamada simple (o justificación), cuotas/costos o `not_measured`, y `tool_calling_status` ∈ {demonstrated, not_supported, not_evaluated}
- [x] T018 [US4] Actualizar `docs/decisiones-tecnicas.md` (apartado chat/validaciones) con resultado de Foundry/modelo habilitado o bloqueos, sin cambiar PostgreSQL local ni Features #4/#6
- [x] T019 [P] [US4] Actualizar `README.md` con enlace breve a la guía Foundry y aclarar que CI no requiere credenciales Azure
- [x] T020 [US4] Revisar `.gitignore`, ausencia de secretos y que `pytest -q tests/unit -k llm` pase sin Azure

**Checkpoint**: Evidencia presentable y reproducible.

---

## Phase 7: Polish

- [x] T021 [P] Alinear docstrings de `backend/src/flowsight/llm/` con constitución VI (tools acotadas, no SQL arbitrario)
- [x] T022 Verificar FR-012–FR-016: sin chat HTTP, sin PG compartido, sin cambios a specs 001/002 ni Features #4/#6; `quickstart.md` coincide con el script real

---

## Dependencies & Execution Order

```text
Setup (T001–T002)
  └─ Foundational (T003–T005)
       └─ US1 (T006–T008)
            └─ US2 (T009–T012)   # gate: aprobación SDK
                 └─ US3 (T013–T016)
                      └─ US4 (T017–T020)
                           └─ Polish (T021–T022)
```

### User Story dependencies

- **US1**: tras Foundational
- **US2**: tras US1 + aprobación de dependencia
- **US3**: tras US2
- **US4**: cierra tras US1–US3 (plantillas pueden adelantarse en Setup)

### Parallel opportunities

- T002 ‖ T001 (archivos distintos tras crear dirs)
- T004 ‖ T005 tras T003
- T016 ‖ T014–T015 una vez definido el contrato del loop
- T019 ‖ T018 tras T017

## Implementation Strategy

### MVP primero (US1)

1. Setup + Foundational  
2. US1 inventario Foundry / modelo habilitado (`gpt-5-mini`)  
3. **STOP**: validar acceso antes de instalar SDK  

### Entrega incremental

1. US2 llamada simple  
2. US3 tool calling  
3. US4 evidencia + docs  

## Azure Boards (propuesto; no creado aquí)

| Spec | Tipo ADO propuesto | Padre |
|---|---|---|
| US1 | User Story | Feature #5 |
| US2 | User Story | Feature #5 |
| US3 | User Story | Feature #5 |
| US4 | User Story | Feature #5 |
| T001–T005 | Tasks prep | #51 bajo US4 #44 |
| T006–T008 | Tasks | #45–#46 bajo US1 #41 |
| T009–T012 | Tasks | #47–#48 bajo US2 #42 |
| T013–T016 | Tasks | #49–#50 bajo US3 #43 |
| T017–T022 | Tasks | #52 bajo US4 #44 |

Work items creados en Boards (2026-09-25). Implementación en rama `feat/validacion-modelo-azure`.
