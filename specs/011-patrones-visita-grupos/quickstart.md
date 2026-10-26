# Quickstart: validar patrones de visita y grupos estimados

Esta guía valida la feature. No la implementa. El modelo está en [data-model.md](./data-model.md), el pedido en [contracts/openapi.yaml](./contracts/openapi.yaml) y la pantalla en [contracts/visit-patterns-ui.md](./contracts/visit-patterns-ui.md).

## Prerrequisitos

- Entorno de specs/002, specs/004, specs/005 y specs/006, con `alembic upgrade head` desde `backend/` (incluida la migración `0015_visit_patterns`). No hacer `downgrade`.
- `FLOWSIGHT_DETECTOR=fake` para la suite. No hace falta el peso ni la GPU.
- El contraste manual del clip real no entra en esta corrida. Queda en `validation/`.

## Caso sintético

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests/unit/test_visit_patterns.py tests/integration/test_visit_patterns_job.py -q
```

El caso de pies conocidos, sin leer `trajectory.jsonl`, cubre:

- Una visita que sale de un área y queda en otra dentro de 1 segundo de video: una transición y una secuencia en ese orden.
- El pie dentro de dos áreas a la vez: esa presencia no suma transición. El paso aparece al salir de una y quedar en la otra.
- Volver a la misma área sin pasar por otra: el área no se repite.
- La misma transición repetida por la misma visita: el conteo de esa visita sigue en uno.
- Una ausencia de más de 1 segundo, o más de 1 segundo fuera de las áreas: la secuencia siguiente no se pega a la anterior.
- Dos áreas seguidas de locales distintos: un cambio de local. Dos áreas del mismo local: transición de áreas y ningún cambio de local.
- Dos visitas a no más de 0,08 del ancho, con direcciones a no más de 45 grados, durante al menos 2 segundos de video: un grupo estimado.
- Una visita quieta, un acercamiento de menos de 2 segundos y una tercera lejos de una de las otras: no entran en ese grupo.
- Una visita que cumpliría dos grupos en el mismo instante: queda en uno solo.
- Un grupo que se desarma y vuelve a cumplir otros 2 segundos: otro grupo.
- El video termina después de los 2 segundos: el grupo llega hasta el último instante observado. Antes de los 2 segundos, no se confirma.
- Sin ningún polígono: patrones no disponibles con motivo `no_areas`. Los grupos siguen y, si no hubo ninguno, la cantidad es cero.
- Las ocho métricas, la tasa de ingreso y el funnel quedan iguales. La muestra del mapa no cambia estos conteos.

Al completar, `GET /sessions/{id}/visit-patterns` devuelve esas listas, los tres umbrales y `precision_uncommitted` en verdadero. `GET /sessions/{id}/shops/{shop_id}/metrics` sigue trayendo las ocho métricas.

## Aislamiento, webcam y tramo

```powershell
.\.venv\Scripts\pytest tests/contract/test_visit_patterns_api.py tests/contract/test_chat_api.py tests/contract/test_funnel_api.py -q
```

- Consultar otra sesión no devuelve estos patrones ni estos grupos.
- Un trabajo `cancelled` o `failed` responde `409` con `result_incomplete`.
- Una sesión webcam responde `409` con `live_patterns_unavailable` y no muestra el bloque.
- El pedido no acepta tramo ni local. `GET /sessions/{id}/events` sigue filtrando hechos.
- La herramienta del chat sigue ofreciendo las cinco cifras de specs/008.
- El funnel de specs/010 conserva sus etapas y sus tasas.

## Pantalla

Desde `frontend/`:

```powershell
npm test -- VisitPatternsPanel SessionResultsPage
```

- En una sesión de archivo completada se leen las transiciones, las secuencias, los cambios de local, los grupos, los tres umbrales, el rótulo de estimación y el aviso de precisión no comprometida.
- Sin áreas, los patrones dicen que no hay áreas y los grupos siguen.
- Cero grupos se lee como cero.
- Cambiar el tramo o el local no dispara otro pedido.
- Una sesión webcam no renderiza el bloque.
