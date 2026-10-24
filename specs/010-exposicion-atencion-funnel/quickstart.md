# Quickstart: validar el funnel comercial

Esta guía valida la feature. No la implementa. El modelo está en [data-model.md](./data-model.md), el pedido en [contracts/openapi.yaml](./contracts/openapi.yaml) y la pantalla en [contracts/funnel-ui.md](./contracts/funnel-ui.md).

## Prerrequisitos

- Entorno de specs/002, specs/004, specs/005 y specs/006, con `alembic upgrade head` desde `backend/` (incluida la migración `0014_shop_funnel`). No hacer `downgrade`.
- `FLOWSIGHT_DETECTOR=fake` para la suite. No hace falta el peso ni la GPU.
- El contraste manual del clip real no entra en esta corrida. Queda en `validation/`.

## Caso sintético

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests/unit/test_showcase_stop.py tests/unit/test_funnel.py tests/integration/test_showcase_stop_job.py -q
```

El caso de mano, para un local con zona frontal, vidriera y línea, cubre:

- Un identificador que pisa el frente y la vidriera menos de 3 segundos, y no entra: paso observado y exposición, sin detención.
- Otro que permanece en la vidriera 5 segundos de video y sale sin perderse: detención, sin atención.
- Otro que permanece 8 segundos o más y después cruza la línea de entrada: atención e ingreso vinculado.
- Otro que entra al local sin haber estado 8 segundos en la vidriera: la entrada oficial sube y el ingreso vinculado no.
- Otro que solo pisa la vidriera: cuenta en excluidas y no en la exposición.
- El mismo identificador que entra y sale de la vidriera dos veces, una de ellas de 3 segundos o más: una sola detención en el funnel, aunque haya dos hechos si las dos estadías califican.
- Varias entradas de zona por oscilación en el borde: una sola exposición en el funnel y las entradas de zona siguen guardadas.
- Uno que desaparece dentro de la vidriera, y un video que termina con el pie adentro: ni detención ni atención.
- Sin polígono de vidriera: exposición, detención, atención e ingreso vinculado no disponibles, con motivo reconocible. El paso observado sigue. La tasa de ingreso ya existente no cambia.
- Atención menor o igual que detención, detención menor o igual que exposición, exposición menor o igual que paso observado, ingreso vinculado menor o igual que atención y menor o igual que las entradas oficiales.

Al completar, `GET /sessions/{id}/shops/{shop_id}/funnel` devuelve esas etapas y las cuatro tasas con los códigos de [data-model.md](./data-model.md). `GET /sessions/{id}/shops/{shop_id}/metrics` sigue trayendo las ocho métricas, sin etapas del funnel.

## Aislamiento, webcam y tramo

```powershell
.\.venv\Scripts\pytest tests/contract/test_funnel_api.py tests/contract/test_chat_api.py -q
```

- Consultar otra sesión no devuelve este funnel.
- Un trabajo `cancelled` o `failed` responde `409` con `result_incomplete`.
- Una sesión webcam responde `409` con `live_funnel_unavailable` y no muestra el bloque.
- El pedido del funnel no acepta tramo. `GET /sessions/{id}/events` sigue filtrando hechos.
- La herramienta del chat sigue ofreciendo las cinco cifras de specs/008 y no estas etapas.

## Pantalla

Desde `frontend/`:

```powershell
npm test -- FunnelPanel
```

- En una sesión de archivo completada se leen los cinco nombres, los dos umbrales, el rótulo de estimación, las cuatro tasas por par de etapas y el aviso de precisión no comprometida.
- Cambiar el tramo no dispara otro pedido del funnel.
- La tasa de ingreso existente conserva su nombre.
- Una sesión webcam no renderiza el bloque.
