# Implementation Plan: Exposición, detención, atención estimada y funnel comercial

**Branch**: `feature/010-exposicion-atencion-funnel` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-exposicion-atencion-funnel/spec.md`

**Azure Boards**: Feature #7 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

## Summary

Al completar un análisis de archivo, cada local gana un funnel de toda la sesión. El tramo del resultado no lo recalcula.

- La exposición es el `zone_enter` de vidriera (`zone_role=window`) que specs/006 ya guarda. No hay un segundo hecho ni se reescriben las entradas de zona ([R1](./research.md#r1--la-exposición-no-es-un-hecho-nuevo)).
- La detención es un hecho nuevo, `showcase_stop`, de al menos 3 segundos de video. La atención estimada es esa detención cuando dura al menos 8 segundos. No es un `dwell` ([R2](./research.md#r2--la-detención-es-un-hecho-nuevo-la-atención-no), [R3](./research.md#r3--reloj-de-la-estadía)).
- Los conteos y las cuatro tasas viven en tablas nuevas. `shop_metrics`, la tasa de ingreso y el chat mínimo no los reciben ([R4](./research.md#r4--conteos-del-funnel-aparte-de-las-ocho-métricas)).
- La lectura es `GET /sessions/{id}/shops/{shop_id}/funnel`, solo para un análisis completado que no sea webcam ([R5](./research.md#r5--cuándo-se-calcula-y-quién-lo-lee)).
- El contraste de un clip real queda fuera de la suite. El panel dice que la precisión no está comprometida ([R6](./research.md#r6--contraste-manual)).

## Technical Context

**Language/Version**: Python 3.11.16 en backend. TypeScript 5.9 con `strict` y React 19.1 en el panel.

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3. En el frontend, Vite 7.3 y CSS Modules. No se agregan paquetes. El detector sigue el de specs/005.

**Storage**: PostgreSQL vía `FLOWSIGHT_DATABASE_URL`. Migración `0014_shop_funnel`: valor `showcase_stop` en `scene_event_kind`, checks de duración y de rol, tablas `shop_funnels`, `shop_funnel_stages` y `shop_funnel_rates`. `shop_metrics` no gana códigos.

**Testing**: pytest para la regla pura, el cierre del trabajo y el contrato. Vitest para el panel. El detector falso de specs/005 arma el caso. No hay prueba de GPU ni de clip real en CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Toca la regla de zona, el worker, la API y la pantalla de resultados de archivo.

**Performance Goals**:

- No hay meta de tiempo real. El funnel se arma una vez, al completar, sobre hechos que el recorrido ya tiene en memoria.
- SC-001: una oscilación deja varias entradas de zona y una sola exposición en el funnel. Perder el identificador, o terminar el video adentro, no crea detención ni atención.
- SC-002: el caso de mano coincide y una segunda lectura no cambia números.
- SC-003: las ocho métricas y la tasa de ingreso quedan iguales. Ninguna tasa del funnel se llama tasa de ingreso.
- SC-005: atención ≤ detención ≤ exposición ≤ paso observado, y el ingreso vinculado ≤ atención y ≤ entradas oficiales. El 100 % de las cifras son de la sesión pedida.
- SC-006: cambiar el tramo no cambia las cinco etapas ni las tasas. Una webcam no muestra el funnel.

**Constraints**:

- Tiempos con el instante del video, con la misma cuenta de fotogramas y fps que el `dwell` frontal.
- Umbrales guardados: 3 segundos para la detención y 8 para la atención.
- Paso observado incluye a quienes entraron. `store_pass` no cambia.
- Sin vidriera, las cuatro etapas que dependen de ella quedan no disponibles con motivo `no_showcase`.
- Tasa sin etapa anterior: no disponible. No se muestra un cero.
- Webcam: no se calculan filas y el pedido responde `409` `live_funnel_unavailable`.
- Análisis no completado: `409` `result_incomplete`.
- Sin identidad, sin mirada, sin seguimiento entre cámaras, sin grupos, sin posible compra y sin chat ampliado.

**Scale/Scope**: seis integrantes; un video a la vez; pocos locales por cámara. El panel es un bloque en la pantalla de resultados que ya existe.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R6).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa el detector falso y PostgreSQL de test. No pide GPU ni el clip real. La migración es la 0014 | Aprobado |
| II. Responsabilidades separadas | La detención y el agregado viven en `vision/`, sin FastAPI ni SQL. El worker los llama al completar. `services/` persiste. La API solo lee | Aprobado |
| III. Trazabilidad y aislamiento | Cada detención lleva sesión, local e instante de video. El funnel no acepta tramo. Dos sesiones no comparten filas. Una división sin etapa anterior queda no disponible | Aprobado |
| IV. Privacidad | El paso observado y la atención son visitas vinculadas, no personas únicas. No hay rostro ni identidad. La permanencia sigue solo en el frente | Aprobado |
| V. Eventos confiables | La oscilación de la línea no se toca. El ingreso vinculado usa el `store_enter` ya cerrado y no reemplaza las entradas oficiales. La atención se rotula como estimación | Aprobado |
| VI. Analytics acotado | El chat mínimo no recibe estas cifras. No hay llamada nueva al modelo ni un código nuevo en `get_session_figures` | Aprobado |
| VII. Evidencia e incrementos | Feature #7. El contraste manual queda en `validation/` y no bloquea la suite | Aprobado |

**Revisión post-diseño**: se mantiene. Separar las tablas del funnel de `shop_metrics` evita que el tablero y el chat pasen a ver etapas que esta feature les prohíbe. Copiar el umbral en `shop_funnels` no abre un segundo cálculo: el test compara el conteo con los hechos.

## Project Structure

### Documentation (this feature)

```text
specs/010-exposicion-atencion-funnel/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── funnel-ui.md
├── spec.md
└── tasks.md             # /speckit-tasks, no esta corrida
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0014_shop_funnel.py
├── src/flowsight/
│   ├── vision/events.py          # cierra showcase_stop; no toca dwell ni la línea
│   ├── vision/funnel.py          # conteos y tasas, sin SQL
│   ├── services/funnel.py        # persiste y lee
│   ├── services/scene_metrics.py # misma transacción de cierre; no agrega códigos
│   ├── api/routes.py             # GET .../funnel
│   └── api/schemas.py
└── tests/
    ├── unit/test_funnel.py
    ├── integration/test_funnel_job.py
    └── contract/test_funnel_api.py

frontend/
├── src/
│   ├── api/funnel.ts
│   ├── components/FunnelPanel.tsx
│   └── pages/SessionResultsPage.tsx
└── tests/FunnelPanel.test.tsx
```

**Structure Decision**: monorepo ya existente. La regla nueva entra en `vision/` porque specs/006 ya decide ahí los hechos de zona. La pantalla entra en el resultado de archivo de specs/007 y no en la vista en vivo de specs/009.

## Complexity Tracking

No aplica. El diseño no viola la constitución.
