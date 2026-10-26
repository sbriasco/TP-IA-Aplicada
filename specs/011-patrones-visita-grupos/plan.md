# Implementation Plan: Patrones de visita y grupos estimados

**Branch**: `feature/011-patrones-visita-grupos` | **Date**: 2026-10-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-patrones-visita-grupos/spec.md`

**Azure Boards**: Feature #8 (Epic #3). Las historias de esta feature todavía no están desglosadas en Boards.

## Summary

Al completar un análisis de archivo, la sesión gana los patrones de recorrido y los grupos estimados de toda la cámara. El tramo del resultado y el local elegido no los recalculan.

- Un área es un polígono ya guardado, `(shop_id, zone_role)` con rol `front`, `interior` o `window`. El paso se anota al salir de un área y quedar en otra dentro de 1 segundo de video. El solape no adelanta la secuencia ([R1](./research.md#r1--un-área-es-un-polígono-ya-configurado)).
- El cálculo ocurre en el worker, con los mismos pies que ya cierran los hechos de zona. Se guarda el resultado. La muestra del mapa de calor no es la fuente y no se crea un archivo por fotograma ([R2](./research.md#r2--se-cierran-en-el-análisis-con-los-pies-que-ya-miran-los-hechos), [R3](./research.md#r3--qué-se-guarda)).
- Un grupo exige pares a no más de 0,08 del ancho, direcciones a no más de 45 grados y al menos 2 segundos de video. Quien se desplaza menos de 0,005 del ancho no aporta dirección. Una visita ocupa un solo grupo por instante ([R4](./research.md#r4--dirección-y-visita-quieta), [R5](./research.md#r5--quiénes-forman-el-grupo)).
- La lectura es `GET /sessions/{id}/visit-patterns`. Métricas, funnel y chat mínimo no reciben estas cifras ([R6](./research.md#r6--lectura-webcam-tramo-y-cifras-que-no-se-tocan)).
- El contraste de un clip real queda fuera de la suite. El bloque dice que la precisión no está comprometida ([R7](./research.md#r7--contraste-manual)).

## Technical Context

**Language/Version**: Python 3.11.16 en backend. TypeScript 5.9 con `strict` y React 19.1 en el bloque.

**Primary Dependencies**: FastAPI 0.141, Pydantic 2, SQLAlchemy 2.0, Alembic 1.20, psycopg 3. En el frontend, Vite 7.3 y CSS Modules. No se agregan paquetes. El detector sigue el de specs/005. No se toca `ultralytics_tracker.py`.

**Storage**: PostgreSQL vía `FLOWSIGHT_DATABASE_URL`. Migración `0015_visit_patterns`, con `down_revision` `0014_shop_funnel`: tablas `visit_pattern_reports`, `visit_area_transitions`, `visit_sequences`, `visit_shop_transitions`, `visit_groups` y `visit_group_members`. Reutiliza el enum `scene_zone_role`. No agrega códigos a `shop_metric_code`.

**Testing**: pytest para la regla pura, el cierre del trabajo y el contrato. Vitest para el bloque. El caso de mano usa pies sintéticos. El detector falso cubre que un archivo completado persiste y que las cifras ya cerradas no cambian. No hay prueba de GPU ni de clip real en CI.

**Target Platform**: Windows 10/11 en desarrollo; CI en `ubuntu-latest`.

**Project Type**: aplicación web monorepo. Toca el worker de archivo, una regla nueva en `vision/`, la API y la pantalla de resultados de archivo.

**Performance Goals**:

- No hay meta de tiempo real. El cálculo corre una vez, dentro del recorrido que ya observa cada fotograma, y conserva estado por identificador. No escribe un pie por fotograma.
- SC-001: el solape no suma transición. El vaivén en la misma área no repite el paso. Una pausa de más de 1 segundo abre otra secuencia. Repetir la transición no aumenta el conteo de esa visita.
- SC-002: el caso de mano coincide, incluido el cambio de local. Una segunda lectura y un cambio de la muestra del mapa no alteran números.
- SC-003: dos visitas que cumplen los tres umbrales forman un grupo estimado. Una quieta, una tercera lejos y un acercamiento corto no entran. El 100 % de los grupos se lee como estimación.
- SC-004: las ocho métricas, la tasa de ingreso y el funnel quedan iguales. La consulta de esas ocho métricas sigue sin estas cifras.
- SC-005: sin polígonos, los patrones quedan no disponibles con `no_areas`. Sin grupos, la cantidad es cero y está disponible.
- SC-006: cambiar el tramo no cambia el bloque. Una webcam no lo muestra.

**Constraints**:

- Tiempos con el instante del video. El reloj de una estadía de grupo es `(fotograma final − fotograma inicial) / fps`.
- Umbrales guardados: `0.08`, `45`, `2` y el corte interno `0.005` del ancho.
- Cada visita cuenta una vez por transición ordenada y una vez por secuencia.
- Sin polígonos: patrones no disponibles con `no_areas`. Grupos disponibles si la escena del análisis existe.
- Webcam: no se calculan filas y el pedido responde `409` `live_patterns_unavailable`.
- Análisis no completado: `409` `result_incomplete`.
- Sin identidad, sin parentesco, sin seguimiento entre cámaras, sin posible compra y sin chat ampliado.

**Scale/Scope**: seis integrantes; un video a la vez; pocos locales y pocas visitas simultáneas por cámara. El bloque es uno en la pantalla de resultados que ya existe.

No quedan `NEEDS CLARIFICATION`. Están resueltas en [research.md](./research.md) (R1 a R7).

## Constitution Check

*GATE: aprobado antes de Phase 0 y revisado después del diseño de Phase 1.*

| Principio | Evidencia | Estado |
|---|---|---|
| I. Local y reproducible | La suite usa pies sintéticos, el detector falso y PostgreSQL de test. No pide GPU ni el clip real. La migración es la 0015 | Aprobado |
| II. Responsabilidades separadas | La regla vive en `vision/visit_patterns.py`, sin FastAPI ni SQL. El worker la llama al completar. `services/` persiste. La API solo lee | Aprobado |
| III. Trazabilidad y aislamiento | Cada fila lleva el trabajo y la sesión. Los instantes son del video. El pedido no acepta tramo. Dos sesiones no comparten filas. Cero grupos queda disponible y la falta de áreas queda no disponible | Aprobado |
| IV. Privacidad | El identificador sigue siendo temporal. El grupo se rotula como estimación y no afirma una relación. No hay rostro ni seguimiento entre cámaras | Aprobado |
| V. Eventos confiables | `scene_events` y la oscilación de la línea no se tocan. El solape no fabrica un cambio de local. El grupo no se confirma si falta tiempo o si una visita no tiene dirección | Aprobado |
| VI. Analytics acotado | El chat mínimo no recibe estas cifras. No hay llamada nueva al modelo ni un código nuevo en `get_session_figures` | Aprobado |
| VII. Evidencia e incrementos | Feature #8. El contraste manual queda en `validation/` y no bloquea la suite | Aprobado |

**Revisión post-diseño**: se mantiene. Separar las tablas de `shop_metrics` y del funnel evita que el tablero, el chat y las tasas ya cerradas pasen a contar secuencias. Guardar el resultado al completar, y no la muestra del mapa, cumple la aclaración y la prohibición de un archivo por instante.

## Project Structure

### Documentation (this feature)

```text
specs/011-patrones-visita-grupos/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── visit-patterns-ui.md
├── spec.md
└── tasks.md             # /speckit-tasks, no esta corrida
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0015_visit_patterns.py
├── src/flowsight/
│   ├── vision/visit_patterns.py   # transiciones, secuencias y grupos, sin SQL
│   ├── services/visit_patterns.py # persiste y lee; webcam no escribe
│   ├── worker/video_analysis.py   # llama al cierre, junto al funnel
│   ├── api/routes.py              # GET /sessions/{id}/visit-patterns
│   └── api/schemas.py
└── tests/
    ├── unit/test_visit_patterns.py
    ├── integration/test_visit_patterns_job.py
    └── contract/test_visit_patterns_api.py

frontend/
├── src/
│   ├── api/visitPatterns.ts
│   ├── components/VisitPatternsPanel.tsx
│   └── pages/SessionResultsPage.tsx
└── tests/VisitPatternsPanel.test.tsx
```

**Structure Decision**: monorepo ya existente. La regla nueva entra en `vision/` y observa los mismos pies que `SceneEventRecorder`, sin modificar los hechos de specs/006. La pantalla entra en el resultado de archivo de specs/007 y no en la vista en vivo de specs/009.

## Complexity Tracking

No aplica. El diseño no viola la constitución.
