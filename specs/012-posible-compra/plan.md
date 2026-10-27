# Implementation Plan: Evaluación de posible compra

**Branch**: `feature/012-posible-compra` | **Date**: 2026-10-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-posible-compra/spec.md`

**Azure Boards**: Feature #9 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

## Summary

Al completar un análisis de archivo, la sesión gana la cantidad de visitas con posible compra estimada. El tramo del resultado y el local elegido no la recalculan. Nunca se presenta como venta.

- Una bolsa es un recuadro de `backpack`, `handbag` o `suitcase`. Se ata a una visita solo si se solapa con exactamente ese recuadro ([R1](./research.md#r1--qué-cuenta-como-bolsa), [R2](./research.md#r2--solape-exclusivo-con-exactamente-una-visita)).
- El cálculo ocurre en el worker, en el mismo análisis que hechos, funnel y patrones. Se guarda el resultado. No hay otra pasada ni un archivo por fotograma ([R3](./research.md#r3--se-cierra-en-el-mismo-análisis), [R4](./research.md#r4--qué-se-guarda)).
- Una visita cuenta una vez si el solape exclusivo suma al menos 1 segundo de video. Un hueco de hasta 1 segundo no inventa solapes ([R2](./research.md#r2--solape-exclusivo-con-exactamente-una-visita)).
- La lectura es `GET /sessions/{id}/possible-purchases`. Métricas, funnel, patrones y chat mínimo no reciben esta cifra ([R5](./research.md#r5--lectura-webcam-tramo-y-cifras-que-no-se-tocan)).
- El contraste de un clip real queda fuera de la suite. El bloque dice que la precisión no está comprometida ([R6](./research.md#r6--contraste-manual)).

## Technical Context

**Language/Version**: Python 3.11.16 en backend. TypeScript 5.9 con `strict` y React 19.1 en el bloque.

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3. En el frontend, Vite 7.3 y CSS Modules. No se agregan paquetes. El detector sigue Ultralytics/YOLO del stack; se amplía solo para emitir recuadros de bolsa además de personas. El detector falso cubre la suite.

**Storage**: PostgreSQL vía `FLOWSIGHT_DATABASE_URL`. Migración `0016_possible_purchase`, con `down_revision` `0015_visit_patterns`: tablas `possible_purchase_reports` y `possible_purchase_members`. No agrega códigos a `shop_metric_code`.

**Testing**: pytest para la regla pura, el cierre del trabajo y el contrato. Vitest para el bloque. El caso de mano usa recuadros sintéticos. El detector falso cubre que un archivo completado persiste y que las cifras ya cerradas no cambian. No hay prueba de GPU ni de clip real en CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Toca el worker de archivo, una regla nueva en `vision/`, una ampliación mínima del contrato del detector, la API y la pantalla de resultados de archivo.

**Performance Goals**:

- No hay meta de tiempo real. El cálculo corre una vez, dentro del recorrido que ya observa cada fotograma, y conserva estado por identificador. No escribe un recuadro por fotograma.
- SC-001: solape exclusivo ≥ 1 segundo cuenta una vez; menos de 1 segundo no cuenta; hueco ≤ 1 segundo no inventa; pérdida de seguimiento no hereda.
- SC-002: dos capas — (1) suite sintética con recuadros conocidos (bloquea merge); (2) clip real anotado antes de cerrar Feature #9 en Boards (no entra en CI). Dos visitas o ninguna no cuentan; entrada/atención sin bolsa no cuentan; segunda corrida idéntica.
- SC-003: el 100 % se lee como estimación, nunca como venta.
- SC-004: las ocho métricas, la tasa de ingreso, el funnel y los patrones quedan iguales.
- SC-005: cero indicios es cero disponible; incompleto no se presenta como resultado.
- SC-006: cambiar el tramo o el local no cambia el bloque. Una webcam no lo muestra.
- SC-007: al entregar código, `validation/contrast.md` en «no ejecutado» + aviso de precisión; el ensayo con clip cierra Boards.

**Constraints**:

- Tiempos con el instante del video. El reloj es `(fotograma final − fotograma inicial) / fps`.
- Umbral guardado: `1` segundo.
- Solape = intersección axis-aligned con área > 0; exclusivo = exactamente una visita.
- Webcam: no se calculan filas y el pedido responde `409` `live_purchase_unavailable`.
- Análisis no completado: `409` `result_incomplete`.
- Sin identidad, sin venta confirmada, sin atribución a un local, sin etapa nueva en el funnel, sin chat ampliado.

**Scale/Scope**: seis integrantes; un video a la vez; pocas visitas simultáneas por cámara. El bloque es uno en la pantalla de resultados que ya existe.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R6).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa recuadros sintéticos, el detector falso y PostgreSQL de test. No pide GPU ni el clip real. La migración es la 0016 | Aprobado |
| II. Responsabilidades separadas | La regla vive en `vision/possible_purchase.py`, sin FastAPI ni SQL. El worker la llama al completar. `services/` persiste. La API solo lee | Aprobado |
| III. Trazabilidad y aislamiento | Cada fila lleva el trabajo y la sesión. Los instantes son del video. El pedido no acepta tramo. Dos sesiones no comparten filas. Cero es disponible | Aprobado |
| IV. Privacidad | El identificador sigue siendo temporal. El rótulo dice que no es una venta y no identifica. No hay rostro ni seguimiento entre cámaras | Aprobado |
| V. Eventos confiables | `scene_events`, funnel y patrones no se tocan. Entrada o atención sin bolsa no se reinterpretan. El solape ambiguo no cuenta | Aprobado |
| VI. Analytics acotado | El chat mínimo no recibe esta cifra. No hay llamada nueva al modelo ni un código nuevo en `get_session_figures` | Aprobado |
| VII. Evidencia e incrementos | Feature #9. El contraste manual queda en `validation/` y no bloquea la suite | Aprobado |

**Revisión post-diseño**: se mantiene. Separar las tablas de `shop_metrics`, del funnel y de los patrones evita que el tablero y el chat pasen a contar bolsas. Cerrar el resultado en el mismo análisis cumple la aclaración y la prohibición de una segunda pasada.

## Project Structure

### Documentation (this feature)

```text
specs/012-posible-compra/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── possible-purchase-ui.md
├── validation/
│   └── contrast.md
├── spec.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0016_possible_purchase.py
├── src/flowsight/
│   ├── vision/possible_purchase.py   # solapes y conteo, sin SQL
│   ├── vision/detector.py            # contrato de recuadros de bolsa
│   ├── vision/fake.py                # emite bolsas en casos de prueba
│   ├── vision/ultralytics_tracker.py # clases backpack/handbag/suitcase
│   ├── services/possible_purchase.py # persiste y lee; webcam no escribe
│   ├── worker/video_analysis.py      # llama al cierre, junto a funnel y patrones
│   ├── api/routes.py                 # GET /sessions/{id}/possible-purchases
│   └── api/schemas.py
└── tests/
    ├── unit/test_possible_purchase.py
    ├── integration/test_possible_purchase_job.py
    └── contract/test_possible_purchase_api.py

frontend/
├── src/
│   ├── api/possiblePurchases.ts
│   ├── components/PossiblePurchasePanel.tsx
│   └── pages/SessionResultsPage.tsx
└── tests/PossiblePurchasePanel.test.tsx
```

**Structure Decision**: monorepo ya existente. La regla nueva entra en `vision/` y observa los recuadros del mismo fotograma que el detector ya produce, sin modificar los hechos de specs/006. La pantalla entra en el resultado de archivo de specs/007 y no en la vista en vivo de specs/009.

## Complexity Tracking

No aplica. El diseño no viola la constitución. La ampliación del detector se limita a emitir recuadros de bolsa; no cambia el seguimiento de personas ni agrega paquetes.
