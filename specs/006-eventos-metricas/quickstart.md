# Quickstart: validar eventos y métricas

Esta guía valida la feature. No la implementa. El modelo está en [data-model.md](./data-model.md) y el contrato en [contracts/openapi.yaml](./contracts/openapi.yaml).

## Prerrequisitos

- Entorno de specs/002, specs/004 y specs/005, con `alembic upgrade head` desde `backend/` (incluida la migración de esta feature). No hacer `downgrade`.
- `FLOWSIGHT_DETECTOR=fake` para la suite. No hace falta el peso ni la GPU.
- El contraste manual del clip real no entra en esta corrida.

## Caso sintético

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests/unit/test_shop_metrics.py tests/integration/test_scene_metrics_job.py -q
```

El caso de mano cubre, para un local con zona frontal y línea:

- Un identificador que cruza en el sentido de entrada y no vuelve dentro de 10 fotogramas: una entrada oficial, ningún paso.
- Otro que solo pisa la zona frontal: un paso, ninguna entrada.
- El mismo que entra y sale de la zona frontal sin perderse: una permanencia con duración en segundos del video.
- Uno que desaparece dentro de la zona: ni salida ni permanencia.
- Uno que solo pisa la zona interior: ni permanencia ni ocupación.
- Dos idas y vueltas sobre la línea dentro de 10 fotogramas: ninguna entrada ni salida confirmada.
- Tráfico igual a la suma de los intervalos de 60 s. El pico es el intervalo mayor y, si empatan, el primero.
- Tasa = entradas oficiales / pasos. Sin pasos, no disponible.

Al completar, `GET /sessions/{id}/shops/{shop_id}/metrics` devuelve esas cifras. `entries`, `exits` y `visible_occupancy` son iguales a `GET /jobs/{id}/measures` con `partial=false`.

## Aislamiento y cierre

```powershell
.\.venv\Scripts\pytest tests/contract/test_scene_metrics_api.py -q
```

- Consultar otra sesión no devuelve estos hechos.
- Un trabajo `cancelled` o `failed` responde `409` con `result_incomplete` y no entrega las ocho métricas como finales.
- `GET /sessions/{id}/events?from_seconds=0&to_seconds=1` solo trae hechos con instante en `[0, 1)`.

## Contraste manual

Cuando haya un clip elegido y un conteo a mano de entradas, salidas y pasos, el informe va a `validation/` con las diferencias clasificadas como en el experimento 001. No reemplaza el caso sintético y no se promete coincidencia.
