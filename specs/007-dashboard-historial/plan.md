# Implementation Plan: Dashboard e historial

**Branch**: `feature/007-dashboard-historial` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-dashboard-historial/spec.md`

**Azure Boards**: Feature #15 (Epic #1). User Stories #65, #66 y #67.

## Summary

El historial y el tablero leen lo que ya quedó guardado. No hay métricas nuevas ni migración.

- `GET /processed-sessions` arma la fila con el análisis más reciente, su versión y el video. `GET /sessions` no cambia ([R1](./research.md#r1--de-dónde-sale-cada-fila-del-historial)).
- Abrir una fila va a `/sessions/{id}/results`. La pantalla de carga y de escena queda donde está ([R2](./research.md#r2--qué-pantalla-abre-el-historial)).
- En curso: solo las tres medidas parciales. Completado: los ocho indicadores de toda la sesión. El tramo filtra minutos y hechos, sin recalcular ([R3](./research.md#r3--parciales-y-cifras-finales-no-salen-del-mismo-pedido), [R4](./research.md#r4--el-tramo-no-recalcula-los-ocho-indicadores)).
- Sin el archivo en este equipo se lee igual y el frame de referencia sigue. El mapa es aparte y no bloquea ([R5](./research.md#r5--mapa-de-calor)).
- El flujo usa Recharts `3.10.1`, ya elegido en las decisiones técnicas ([R6](./research.md#r6--gráfico)).

## Technical Context

**Language/Version**: TypeScript 5.9 con `strict`, React 19.1. El backend que lee es Python 3.11.16.

**Primary Dependencies**: Vite 7.3, CSS Modules, Recharts 3.10.1. FastAPI y Pydantic siguen los de specs/006. No hay otro paquete.

**Storage**: Sin migración. El historial lee `sessions`, `video_sources`, `processing_jobs` y `scene_versions`. Las cifras salen de `shop_metrics` y `traffic_buckets`. El mapa, si entra, lee el JSONL de specs/005.

**Testing**: Vitest para el filtro de minutos. Pytest de contrato para el historial. Playwright para el recorrido. El detector de prueba alcanza. No hay prueba de GPU.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Esta feature toca la presentación y una lectura nueva en la API.

**Performance Goals**:

- No hay meta de tiempo real. El historial no espera a que termine un análisis para listarse.
- SC-001: el 100 % de las filas muestra nombre, video, estado, fecha de procesamiento y versión. El 100 % de las fallidas y canceladas muestra el motivo.
- SC-003: el 100 % de los ocho indicadores coincide con las cifras ya registradas de ese local para toda la sesión. Los minutos visibles se solapan con el tramo y se muestran enteros.
- SC-005: sin el video en este equipo, los resultados y el frame siguen.

**Constraints**:

- Los ocho indicadores no cambian con el tramo. Un minuto no se parte.
- En curso solo se muestran entradas, salidas y ocupación visible, como parciales.
- La versión es la del análisis, no la última de la cámara.
- La fecha de procesamiento es `finished_at`, no el reloj del video.
- Sin chat, sin contraste manual y sin identidad.

**Scale/Scope**: seis integrantes y pocas sesiones. Dos pantallas: historial y resultados. El mapa no entra en el recorrido que da por válida la feature.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R6).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa el detector de prueba y PostgreSQL de test. No pide GPU ni el clip real | Aprobado |
| II. Responsabilidades separadas | La API solo lee. El filtro de minutos vive en el frontend y no toca visión ni métricas | Aprobado |
| III. Trazabilidad y aislamiento | La fila y los resultados llevan la sesión. El flujo sigue en tiempo de video. Dos sesiones no se mezclan | Aprobado |
| IV. Privacidad | El tráfico se rotula como estimación de visitas. La ocupación se rotula como visible. El mapa no identifica personas | Aprobado |
| V. Eventos confiables | No se crean eventos. Las cifras finales son las de specs/006 y las tres oficiales siguen siendo las de specs/005 | Aprobado |
| VI. Analytics acotado | No hay llamada al modelo. El tablero lee los mismos pedidos que va a leer el chat | Aprobado |
| VII. Evidencia e incrementos | Historias #65 a #67. El mapa no bloquea el recorrido | Aprobado |

**Revisión post-diseño**: se mantiene. `GET /processed-sessions` no agrega una métrica: junta columnas que ya existen. El pedido de métricas de specs/006 no gana un filtro de tramo.

## Project Structure

### Documentation (this feature)

```text
specs/007-dashboard-historial/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── dashboard-ui.md
├── checklists/
│   └── requirements.md
├── cross-feature-analysis.md
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
backend/src/flowsight/
├── services/processed_sessions.py    # arma la fila; no calcula métricas
├── services/position_samples.py      # lee el JSONL; solo si entra el mapa
└── api/routes.py, api/schemas.py

frontend/src/
├── pages/ProcessedSessionsSection.tsx
├── pages/SessionResultsPage.tsx
├── flow/visibleBuckets.ts            # solapamiento de minutos, puro
└── styles de esas pantallas, en CSS Modules

frontend/e2e/session-results.spec.ts
backend/tests/contract/test_processed_sessions_api.py
```

**Structure Decision**: se mantiene el monorepo. No hay worker nuevo ni migración. La pantalla de sesiones sigue registrando el video.

## Implementation Phases

1. **Historial (#65)**: `GET /processed-sessions` y la sección en la pantalla de sesiones. La fila abre `/sessions/{id}/results`.
2. **Indicadores (#66)**: la pantalla de resultados. En curso usa las tres medidas parciales. Completado usa el pedido de métricas y filtra minutos y hechos en el navegador. Recharts `3.10.1` para el flujo.
3. **Mapa (#67)**: después de las dos anteriores. `GET /jobs/{id}/position-samples` y el dibujo sobre el frame. Si no entra, #65 y #66 igual se dan por válidas.

#65 bloquea a #66. #67 no bloquea a ninguna.

## Verification Strategy

- **#65**: sesión sin análisis ausente del historial. Completada con nombre, archivo, estado, fecha y versión usada. Fallida con motivo. Dos sesiones no se cruzan. Sin archivo, el frame sigue.
- **#66**: los ocho indicadores iguales al pedido de métricas. Mover el tramo no los cambia y no parte un minuto. En curso, solo tres cifras y el texto «parcial». Tasa sin pasos, «no disponible».
- **#67**: con muestra, los pies caen sobre el frame. Sin archivo de muestra, el vacío está explicado y los indicadores siguen. El recorrido de #65 y #66 pasa sin esta historia.
