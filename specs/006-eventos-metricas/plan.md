# Implementation Plan: Eventos espaciales, métricas y persistencia

**Branch**: `feature/006-eventos-metricas` | **Date**: 2026-09-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-eventos-metricas/spec.md`

**Azure Boards**: Feature #14 (Epic #1). User Stories #61, #62, #63 y #64.

## Summary

Al completar un análisis, la sesión queda consultable por local:

- Entrada y salida del local se leen de los cruces confirmados. No hay un segundo cruce de la línea ([R1](./research.md#r1--de-dónde-salen-los-hechos)).
- Zona, paso y permanencia de la zona frontal se deciden en el mismo recorrido de fotogramas y se guardan solo al completar. Interior y vidriera no generan permanencia ni ocupación.
- Las ocho métricas y el flujo de un minuto viven en tablas nuevas. Las tres medidas oficiales siguen en `analysis_measures` y se copian, no se recalculan ([R2](./research.md#r2--qué-se-persiste), [R3](./research.md#r3--las-ocho-métricas-y-el-horario-pico)).
- El tablero y el chat futuro leen los mismos dos endpoints. Esta feature no llama al modelo ([R4](./research.md#r4--consulta)).
- El conteo manual de un clip real queda fuera de la suite ([R5](./research.md#r5--contraste-manual)).

## Technical Context

**Language/Version**: Python 3.11.16. Esta feature no cambia el frontend.

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3. No se agregan paquetes. El detector sigue el que ya configuró specs/005.

**Storage**: PostgreSQL vía `FLOWSIGHT_DATABASE_URL`. Migración `0005_scene_metrics`: `scene_events`, `shop_metrics`, `traffic_buckets`. El JSONL de trayectoria no se usa para calcular.

**Testing**: pytest. El detector falso de specs/005 arma el caso con resultado a mano. No hay prueba de GPU ni de video real en CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Esta feature toca el backend (visión pura, worker y API).

**Performance Goals**:

- No hay meta de tiempo real. El cálculo ocurre dentro del recorrido que specs/005 ya hace, más una escritura al completar.
- SC-002: el caso de mano coincide y una segunda lectura no cambia números.
- SC-003: entradas, salidas y ocupación visible consultadas son iguales a las oficiales en el 100 % de ese caso.
- SC-005: el 100 % de los hechos devueltos pertenecen a la sesión pedida.

**Constraints**:

- Tiempos con el instante del video. Intervalo de flujo de 60 s. Pico = mayor conteo y, en empate, el más temprano.
- Oscilación de 10 fotogramas, la misma de `vision/spatial.py`.
- Permanencia solo en zona frontal. Perder el identificador no crea salida ni permanencia.
- Tasa sin pasos, o permanencia sin estadías cerradas: no disponible.
- Un análisis no completado no se consulta como resultado final (`409`, `result_incomplete`).
- Sin identidad, sin seguimiento entre cámaras, sin chat y sin tablero en esta feature.

**Scale/Scope**: seis integrantes; un video a la vez; pocos locales por cámara. Fuera de alcance: mapa de calor, exposición, atención, posible compra y grupos.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R5).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa el detector falso y PostgreSQL de test. No pide GPU ni el clip real. La migración es la 0005 | Aprobado |
| II. Responsabilidades separadas | La regla de zona y permanencia vive en `vision/`, sin FastAPI ni SQL. El worker la llama. `services/` persiste. La API solo lee | Aprobado |
| III. Trazabilidad y aislamiento | Cada hecho lleva sesión, local e instante de video. El flujo usa el inicio del video. Dos sesiones no comparten filas | Aprobado |
| IV. Privacidad | El tráfico es una estimación de visitas por identificador temporal. La ocupación es la visible oficial. No hay permanencia interior | Aprobado |
| V. Eventos confiables | La oscilación y el cambio de identificador siguen la regla de specs/005. Las tres medidas oficiales no se reemplazan | Aprobado |
| VI. Analytics acotado | No hay llamada al modelo. El endpoint es la herramienta que el chat va a leer | Aprobado |
| VII. Evidencia e incrementos | Historias #61 a #64. El contraste manual queda en `validation/` y no bloquea la suite | Aprobado |

**Revisión post-diseño**: se mantiene. Copiar las tres medidas a `shop_metrics` no abre un segundo cálculo: el test las compara con `analysis_measures`.

## Project Structure

### Documentation (this feature)

```text
specs/006-eventos-metricas/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
├── cross-feature-analysis.md
├── validation/                  # contraste manual, cuando exista
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0005_scene_metrics.py
├── src/flowsight/
│   ├── vision/events.py                 # zona, paso, permanencia frontal; puro
│   ├── vision/metrics.py                # ocho medidas y flujo, a partir de hechos y oficiales
│   ├── services/scene_metrics.py        # persistencia al completar y lectura
│   ├── worker/video_analysis.py         # llama a events en el bucle; vuelca al completar
│   └── api/routes.py, api/schemas.py    # metrics y events
└── tests/
    ├── unit/test_shop_metrics.py
    ├── integration/test_scene_metrics_job.py
    └── contract/test_scene_metrics_api.py
```

**Structure Decision**: se mantiene el monorepo. No hay pantalla nueva. El worker sigue siendo el único que ve fotogramas. La consulta no abre el video ni el JSONL.

## Implementation Phases

1. **Esquema**: migración `0005` y modelos de `scene_events`, `shop_metrics` y `traffic_buckets`, sin tocar el valor de `analysis_measures`.
2. **US1 (#61)**: `vision/events.py` sobre el pie de cada fotograma. Al completar, los cruces confirmados se copian como `store_enter` / `store_exit`. Oscilación, pérdida de identificador e interior sin permanencia quedan cubiertos por el caso de mano.
3. **US2 (#62)**: `vision/metrics.py` arma las ocho medidas y los intervalos. Entradas, salidas y ocupación visible se copian de las filas oficiales.
4. **US3 (#63)**: los dos GET. `409` si el análisis no está completado. El listado de sesiones no cambia.
5. **US4 (#64)**: la suite no lo exige. El quickstart deja el lugar del informe manual.

#61 bloquea a #62. #62 bloquea a #63. El detector falso alcanza para las tres.

## Verification Strategy

- **#61**: oscilación sin entrada confirmada; identificador perdido sin salida ni permanencia; interior sin permanencia; cruce fuera del segmento sin entrada.
- **#62**: el caso de mano coincide en las ocho medidas, el flujo y el pico. Segunda lectura, mismos números. Sin pasos, tasa no disponible.
- **#63**: las tres medidas del GET nuevo iguales a `/jobs/{id}/measures`. Otra sesión no las ve. Cancelado responde `result_incomplete`.
- **#64**: no se afirma en CI. El informe manual, cuando exista, clasifica diferencias y no promete igualdad.
