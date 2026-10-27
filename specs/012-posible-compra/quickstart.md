# Quickstart: validar posible compra estimada

Esta guía valida la feature. No la implementa. El modelo está en [data-model.md](./data-model.md), el pedido en [contracts/openapi.yaml](./contracts/openapi.yaml) y la pantalla en [contracts/possible-purchase-ui.md](./contracts/possible-purchase-ui.md).

## Prerrequisitos

- Entorno de specs/002, specs/005, specs/006, specs/010 y specs/011, con `alembic upgrade head` desde `backend/` (incluida la migración `0016_possible_purchase`). No hacer `downgrade`.
- `FLOWSIGHT_DETECTOR=fake` para la suite. No hace falta el peso ni la GPU.
- El contraste manual del clip real no entra en esta corrida (SC-002 capa 1). Queda en `validation/` en «no ejecutado» hasta el cierre de Feature #9 en Boards (capa 2).

## Caso sintético

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests/unit/test_possible_purchase.py tests/integration/test_possible_purchase_job.py -q
```

El caso de recuadros conocidos, sin leer `trajectory.jsonl`, cubre:

- Una visita cuyo recuadro se solapa en exclusiva con el de una bolsa al menos 1 segundo de video: cuenta una vez.
- Un solape de menos de 1 segundo: no cuenta.
- Un hueco de hasta 1 segundo sin solape: no inventa el solape ni parte el indicio si luego vuelve.
- Un hueco de más de 1 segundo, o la pérdida del seguimiento: cierra el tramo. Una visita nueva no hereda la bolsa.
- El recuadro de la bolsa se solapa con dos visitas, o con ninguna: no cuenta.
- La misma visita vuelve a solaparse después de un corte: sigue contando una sola vez.
- Una entrada, una detención o una atención sin solape exclusivo: no cuentan como posible compra.
- Las ocho métricas, la tasa de ingreso, el funnel y los patrones quedan iguales.

Al completar, `GET /sessions/{id}/possible-purchases` devuelve la cantidad, el umbral `"1"` y `precision_uncommitted` en verdadero. `GET /sessions/{id}/shops/{shop_id}/metrics` sigue trayendo las ocho métricas.

## Aislamiento, webcam y tramo

```powershell
.\.venv\Scripts\pytest tests/contract/test_possible_purchase_api.py tests/contract/test_chat_api.py tests/contract/test_funnel_api.py tests/contract/test_visit_patterns_api.py -q
```

- Consultar otra sesión no devuelve esta cifra.
- Un trabajo `cancelled` o `failed` responde `409` con `result_incomplete`.
- Una sesión webcam responde `409` con `live_purchase_unavailable` y no muestra el bloque.
- El pedido no acepta tramo ni local.
- La herramienta del chat sigue ofreciendo las cinco cifras de specs/008 y no responde con bolsas ni compras.
- El funnel y los patrones conservan su forma.

## Pantalla

Desde `frontend/`:

```powershell
npm test -- PossiblePurchasePanel SessionResultsPage
```

- En una sesión de archivo completada se leen la cantidad, el umbral de 1 segundo, el rótulo de que no es una venta y el aviso de precisión no comprometida.
- Cero visitas se lee como cero.
- Cambiar el tramo o el local no dispara otro pedido.
- Una sesión webcam no renderiza el bloque.
