# Implementation Plan: Chat analítico ampliado

**Branch**: `feature/014-chat-analitico-ampliado` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-chat-analitico-ampliado/spec.md`

**Azure Boards**: Feature #11 (Epic #3). Agente con más herramientas de analytics; supersede el chat mínimo en el mismo panel. Depende de lecturas 006/008/010–013 y del modelo ya validado en 003.

## Summary

El panel de resultados deja de citar solo cinco cifras: el backend expone un catálogo cerrado ampliado y una herramienta de contraste que reutiliza el ensamblado de comparaciones (013). El modelo en Azure solo elige herramientas y redacta; no mide, no hace SQL ni RAG. Preguntas independientes (US3 diferido). Grounding demostrable con redactor falso ([research.md](./research.md)).

## Technical Context

**Language/Version**: Python 3.11.16 en backend. TypeScript 5.9 con `strict` y React 19.1 en el frontend.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy (ya fijados). Cliente `openai==1.109.1` y deployment `gpt-5-mini` (specs/003). Sin paquetes nuevos. Sin framework de agentes ni vector store.

**Storage**: Sin migración. Lectura de métricas, pico, funnel, patrones, posible compra y del servicio `comparison` ya existente. El hilo de UI no se persiste.

**Testing**: pytest (lecturas ampliadas, resolución de contraste, guards, `POST /chat` con redactor falso). Vitest del panel. Regresión: lecturas individuales y `POST /comparisons` intactos. Azure real manual, no bloquea CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Extiende `services/chat*.py`, schemas/routes de `POST /chat` y el panel existente; no toca visión/worker.

**Performance Goals**:

- Tope por pregunta independiente: mismo presupuesto que 008 (máx. 2 llamadas al modelo; timeout `FLOWSIGHT_CHAT_TIMEOUT_SECONDS`).
- SC-001–006: grounding 100 %, contraste alineado a 013, rechazos, UI usable sin modelo de pago, demo «tools ≠ RAG» &lt; 2 min.

**Constraints**:

- MUST NOT RAG / knowledge store / SQL libre / recalcular desde video.
- MUST NOT segundo modo «solo cinco cifras» en resultados.
- MUST NOT US3 (hilo con memoria de cifras) en esta entrega.
- Contraste: mismas reglas 013; sesiones = nombres y/o última + abierta; ejes session/day/time_of_day/zone.
- Webcam: chat comercial indisponible (009).
- Secretos solo en backend.

**Scale/Scope**: seis integrantes; pocas sesiones; un panel; catálogo cerrado + una herramienta de contraste.

No quedan `NEEDS CLARIFICATION`. Resueltas en clarificaciones de spec y [research.md](./research.md) (R1–R8).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | Suite con PostgreSQL de test + redactor falso; Azure no requerido en CI | Aprobado |
| II. Responsabilidades separadas | Lecturas/contraste en servicios; modelo solo redacta; panel no calcula | Aprobado |
| III. Trazabilidad y aislamiento | Sesión/zona/eje explícitos; no mezclar al cambiar selección; día = UTC `finished_at`; horario = tiempo de video | Aprobado |
| IV. Privacidad | Guards de identidad / multi-cámara; zona no unifica cámaras | Aprobado |
| V. Estimaciones explícitas | Rótulos de tráfico/grupos/posible compra; no venta confirmada | Aprobado |
| VI. Analytics acotado | Tools cerradas; sin SQL del modelo; sin RAG de cifras; credenciales en backend | Aprobado |
| VII. Evidencia e incrementos | Feature #11; pytest/Vitest; US3 diferido documentado | Aprobado |

**Revisión post-diseño**: se mantiene. Se reutiliza `POST /chat` y `comparison.py`; no hay tablas nuevas ni segundo endpoint de chat.

## Project Structure

### Documentation (this feature)

```text
specs/014-chat-analitico-ampliado/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── metric-tools.md
│   └── chat-ui.md
├── cross-feature-analysis.md
├── spec.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/flowsight/
│   ├── services/chat_metrics.py   # catálogo ampliado + payload para tools
│   ├── services/chat.py           # tools, resolución de contraste, filtros
│   ├── services/chat_guard.py     # rechazo compra/identidad/fuera de catálogo
│   ├── services/comparison.py     # reutilizado (sin recalcular)
│   └── api/routes.py, schemas.py  # POST /chat (contrato ampliado)
└── tests/
    ├── unit/test_chat_*.py
    └── contract/test_chat_api.py

frontend/
├── src/
│   ├── components/SessionChatPanel.tsx  # mismo panel; cifras/labels ampliados
│   └── pages/SessionResultsPage.tsx
└── tests/…Chat….test.tsx
```

**Structure Decision**: monorepo existente. Ampliar el chat de 008; invocar el ensamblado de 013 desde una tool interna. Sin cambios en `vision/` ni worker. UI = mismo panel (supersesión).

## Complexity Tracking

No aplica. El diseño no viola la constitución.
