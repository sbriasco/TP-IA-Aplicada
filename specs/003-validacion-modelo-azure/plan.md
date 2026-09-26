# Implementation Plan: Validación del servicio de modelo de Azure

**Branch**: `feat/validacion-modelo-azure` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)

**Azure Boards**: Feature #5 (Epic #2). User Stories / Tasks de Boards se cargan **después** de `/speckit-tasks` y aprobación explícita.

**Input**: Feature specification from `/specs/003-validacion-modelo-azure/spec.md` (post-clarify)

## Summary

Validar con un **módulo mínimo en el backend** y un **script local** que FlowSight puede usar **Azure AI Foundry** (proyecto compartido, suscripción de estudiantes ~100 USD): autenticación por **API key**, modelo **habilitado** en Foundry (**`gpt-5-mini`**, región **`brazilsouth`**), una llamada simple y un ciclo de tool calling con `get_session_traffic` hardcodeada. Producir evidencia anonimizada y `.env.example`. Sin chat HTTP, sin PostgreSQL, sin tocar Features #4/#6.

## Technical Context

**Language/Version**: Python 3.11.16 (runtime del backend existente)

**Primary Dependencies**: Cliente **`openai==1.109.1`** (OpenAI-compatible) contra el endpoint Foundry del proyecto. Sin framework de agentes.

**Storage**: Sin tablas nuevas. Evidencia local en `specs/003-validacion-modelo-azure/validation/` (resumen anonimizado versionable). No usa PostgreSQL.

**Testing**: pytest unitario sin Azure (config, fake tool, orquestador mock, redaction). Llamadas reales a Foundry: procedimiento local, fuera de CI ordinaria.

**Target Platform**: Windows local, red hacia Azure AI Foundry

**Project Type**: extensión mínima del backend + script PowerShell de validación

**Performance Goals**: corridas mínimas (inventario + 1 completion + 1 tool loop); llamada simple en menos de 5 minutos una vez configurado el entorno (SC-003)

**Constraints**: API key solo en `.env`; proyecto Foundry compartido; sin endpoint de chat; sin Entra ID en esta Feature; sin baterías exploratorias de crédito; CI sin secretos Azure

**Scale/Scope**: un deployment/modelo habilitado (`gpt-5-mini`), una herramienta ficticia, evidencia para el equipo y el TP

## Constitution Check

*GATE: aprobado antes de Phase 0; revalidado tras Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | Script local; guía + resumen; Foundry compartido con `.env` por integrante | Aprobado |
| II. Separación | `llm` (cliente, tools, orquestación, evidencia) distinto de worker/visión/API de chat | Aprobado |
| III. Trazabilidad | Evidencia con región/deployment/modelo/resultados; sin métricas de negocio inventadas | Aprobado |
| IV. Privacidad | `session_id` ficticio; sin tracks reales | Aprobado |
| V. Estimaciones explícitas | Tool calling y costos: `demonstrated` / `not_supported` / `not_evaluated` / `not_measured` | Aprobado |
| VI. Analytics acotado | Credenciales backend; tool ficticia; modelo no calcula métricas; sin SQL arbitrario | Aprobado |
| VII. Evidencia e incrementos | Feature #5; incrementos por US; sin ampliar a #16 | Aprobado |

Post-diseño: sin excepciones. `tasks.md` regenerado con `/speckit-tasks` (post-clarify/plan).

## Project Structure

### Documentation (this feature)

```text
specs/003-validacion-modelo-azure/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── azure-model-config.md
│   ├── fake-analytics-tool.md
│   └── validation-evidence.md
├── checklists/
│   └── requirements.md
├── validation/                 # evidencia; solo resumen anonimizado versionable
└── tasks.md                    # se regenera con /speckit-tasks
```

### Source Code (repository root)

```text
backend/src/flowsight/llm/      # NUEVO: settings, client, fake_tools, tool_loop, evidence, inventory
backend/tests/unit/             # tests sin Azure
scripts/validate-azure-model.ps1
.env.example                    # variables Foundry (sin secretos)
```

**Structure Decision**: módulo `flowsight.llm` reutilizable por Feature #16 + script de validación. No hay endpoints FastAPI de chat en esta Feature.

## Complexity Tracking

> Sin violaciones constitucionales.
