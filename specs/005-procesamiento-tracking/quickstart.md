# Quickstart: validar procesamiento y vista en vivo

Esta guía valida la feature. No la implementa. El modelo está en [data-model.md](./data-model.md) y los contratos en [contracts/](./contracts/). La evidencia del equipo de referencia se escribe en `validation/` sin rutas absolutas, nombres de equipo ni secretos.

## Prerrequisitos

- El entorno de specs/002 y specs/004 funcionando, con PostgreSQL local y `alembic upgrade head` desde `backend/` (incluida la migración de esta feature). No hacer `downgrade`.
- `.env` con `FLOWSIGHT_VIDEOS_DIR` y `FLOWSIGHT_MACHINE_ID`, como en specs/004.
- Para la suite y el recorrido reproducible: `FLOWSIGHT_DETECTOR=fake`. No hace falta el peso ni la GPU.
- Para un video real: el peso `yolov8n.pt` fuera de Git y `FLOWSIGHT_DETECTOR=ultralytics`. El lock agrega las versiones de CPU del experimento 001 (`ultralytics==8.4.153`, `torch==2.7.1+cpu`). Son dependencias del stack ya acordado.

## Verificaciones automáticas

Desde `backend/`, con el venv:

```powershell
.\.venv\Scripts\pytest tests\unit\test_spatial_counts.py
.\.venv\Scripts\pytest tests\unit\test_trajectory_sample.py
.\.venv\Scripts\pytest tests\integration\test_video_analysis_job.py
.\.venv\Scripts\pytest tests\contract\test_video_analysis_api.py
.\.venv\Scripts\pytest
```

`pytest` no incluye las pruebas marcadas `gpu`.

Resultado esperado:

- Un trabajo `video_analysis` con el detector falso pasa de `pending` a `processing` y termina `completed`.
- Al 50 % de los fotogramas, el avance informado es el 50 %, con tolerancia de un fotograma.
- Entradas, salidas y ocupación visible quedan `partial=false` y no hay una segunda copia.
- Una oscilación dentro de 10 fotogramas no suma. Un cambio de identificador no suma una entrada ni una salida.
- Dos sesiones con el mismo `track_id` no comparten cruces.
- Cancelar deja `cancelled`, `result_complete=false` y las medidas en `partial=true`. No se procesan fotogramas posteriores.
- Matar el proceso y volver a arrancar deja ese trabajo en `failed` con `worker_interrupted`, no en `cancelled`.
- La suite de specs/002 y specs/004 sigue en verde. El trabajo sintético sigue publicando `schema_version` `1`.

Desde `frontend/`:

```powershell
npm run lint
npm test
npm run build
npm run test:e2e
```

El E2E abre la vista de un análisis con detector falso, comprueba que la imagen corresponde al instante informado y que cancelar deja el trabajo cancelado.

## Escenario manual con video real

1. Registrar un video ya usado (por ejemplo el de ~94 s) y confirmar una escena con zona frontal y línea.
2. Iniciar el análisis con `FLOWSIGHT_DETECTOR=ultralytics` y abrir la vista en vivo.
3. Ver recuadros, identificadores, zonas y línea sobre el fotograma de ese instante. El avance sigue a los fotogramas del video.
4. Al completar, `GET /jobs/{id}/measures` devuelve las tres medidas con `partial=false`.

No se exige que la vista iguale la velocidad del video.

## Equipo de referencia (SC-006)

En el equipo con procesador gráfico, correr el mismo video real y guardar el resumen en `validation/`. Debe incluir dispositivo, versiones del método y fotogramas procesados por segundo de procesamiento. Si el procesador gráfico no puede usarse, repetir en el procesador principal y escribir esa limitación. Esta medición no forma parte de CI.
