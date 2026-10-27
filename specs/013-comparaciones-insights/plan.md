# Implementation Plan: Comparaciones e insights

**Branch**: `feature/013-comparaciones-insights` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-comparaciones-insights/spec.md`

**Azure Boards**: Feature #10 (Epic #3). Comparaciones entre sesiones e insights desde métricas estructuradas; no depende de bolsas ni de Feature #9.

## Summary

El analista elige ≥2 sesiones de archivo ya completadas y un nombre de zona; el backend arma un contraste de solo lectura (métricas + pico obligatorios; funnel / patrones / posible compra si existen) e insights deterministas. No hay migración ni recálculo desde video. P1 = sesión vs sesión; día / horario / zona son P2 en la misma feature si alcanza el tiempo ([research.md](./research.md)).

## Technical Context

**Language/Version**: Python 3.11.16 en backend. TypeScript 5.9 con `strict` y React 19.1 en el frontend.

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic (sin revisión nueva). Vite 7.3 y CSS Modules. No se agregan paquetes ni llamadas al modelo.

**Storage**: PostgreSQL vía `FLOWSIGHT_DATABASE_URL`. Solo lectura de tablas existentes (sesiones, trabajos, métricas, funnel, patrones, posible compra, escenas). Sin migración.

**Testing**: pytest (unitario del ensamblado + contrato `POST /comparisons` + regresión de lecturas). Vitest del flujo/pantalla de comparación. Sin GPU ni clip real.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Toca servicio de comparación, API, cliente y una pantalla/flujo aparte del resultado individual.

**Performance Goals**:

- Lectura acotada a N sesiones del historial local (orden de unidades, no miles).
- SC-001–007: diferencias correctas, no disponible ≠ cero, insights verificables, lecturas individuales intactas, rechazo de &lt;2 elegibles / webcam, UI legible, chat mínimo sin estas cifras.

**Constraints**:

- MUST NOT recalcular desde video, eventos ni trajectory.
- MUST NOT usar LLM para insights (Feature #11 leerá después).
- MUST NOT alterar cuerpos de métricas, funnel, patrones, possible-purchases ni chat.
- Horario P2 = tiempo de video; zona P2 = misma cámara + mismo nombre.
- Diferencia solo con ambos lados available.

**Scale/Scope**: seis integrantes; historial pequeño; P1 obligatorio; P2 opcional en la misma feature.

No quedan `NEEDS CLARIFICATION`. Resueltas en clarificaciones de spec y [research.md](./research.md) (R1–R7).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | Suite con sesiones sintéticas y PostgreSQL de test; sin GPU ni cloud de procesamiento | Aprobado |
| II. Responsabilidades separadas | Ensamblado en `services/comparison.py` (o equivalente) sin visión; API solo orquesta; UI aparte | Aprobado |
| III. Trazabilidad y aislamiento | Columnas por sesión; no cruce de cifras entre columnas; horario P2 = timestamps de video; no disponible documentado | Aprobado |
| IV. Privacidad | Sin identidad ni unificación entre cámaras; zona por nombre+cámara, no comercio real | Aprobado |
| V. Eventos confiables | No reescribe eventos ni estimaciones; insights no inventan causas ni ventas | Aprobado |
| VI. Analytics acotado | Sin herramientas nuevas en chat mínimo; sin SQL del modelo; insights por reglas | Aprobado |
| VII. Evidencia e incrementos | Feature #10; pytest/Vitest; P2 no bloquea cierre de P1 | Aprobado |

**Revisión post-diseño**: se mantiene. Documentos de solo lectura + `POST /comparisons` evitan contaminar contratos 006–012/008. Sin tablas nuevas reduce riesgo de migraciones.

## Project Structure

### Documentation (this feature)

```text
specs/013-comparaciones-insights/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── comparison-ui.md
├── cross-feature-analysis.md
├── spec.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/flowsight/
│   ├── services/comparison.py    # elegibilidad, resolución de zona, filas, insights
│   ├── api/routes.py             # POST /comparisons
│   └── api/schemas.py
└── tests/
    ├── unit/test_comparison.py
    └── contract/test_comparison_api.py

frontend/
├── src/
│   ├── api/comparisons.ts
│   ├── components/ComparisonPanel.tsx   # o página dedicada
│   └── pages/...                        # entrada desde historial
└── tests/Comparison*.test.tsx
```

**Structure Decision**: monorepo existente. No toca `vision/` ni el worker. Reutiliza loaders de métricas/funnel/patrones/possible-purchases. UI nueva separada de `SessionResultsPage`.

## Complexity Tracking

No aplica. El diseño no viola la constitución.
