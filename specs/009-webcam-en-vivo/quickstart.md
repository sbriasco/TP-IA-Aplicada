# Webcam en vivo: arranque y verificación

Implementación local para la Expo, fuera de Azure Boards. No graba video: conserva referencia de escena, eventos, cifras y posiciones muestreadas. IP queda para el próximo incremento mediante FrameSource.

## Configurar

API y worker comparten FLOWSIGHT_MACHINE_ID y FLOWSIGHT_LIVE_CHANNEL_TOKEN en .env. El token debe ser aleatorio, privado y no versionado; vacío deshabilita vivo. Usar PostgreSQL local. El worker conecta por loopback al puerto FLOWSIGHT_API_PORT: no existe una variable adicional de URL live.

Para personas reales: FLOWSIGHT_LIVE_CAPTURE_SOURCE=webcam, FLOWSIGHT_DETECTOR=ultralytics y FLOWSIGHT_YOLO_WEIGHTS con una ruta al peso local yolo11m.pt. El modelo debe existir: esta guía no lo descarga. La instalación de esta PC usa PyTorch CPU; GPU y velocidad física no están medidas. fake no detecta personas reales.

La pantalla muestra webcams detectadas por Windows con sus nombres, incluidas cámaras virtuales si están registradas. Actualizar cámaras renueva la lista; si desaparece la selección, hay que elegir otra. No se configura el dispositivo en .env. La detección lee monikers DirectShow sin abrir streams, en un helper con timeout3s y una sola enumeración activa. El probe de Windows usa DSHOW para conservar el mismo orden de índices; máximo1920×1080. Detectada no significa disponible: preparar/comprobar verifica permisos y uso por otras aplicaciones. Cambiar dimensiones exige nueva preparación/escena. La enumeración automática está implementada para Windows; otros sistemas muestran una explicación de indisponibilidad.

## Iniciar desde la raíz

```powershell
./scripts/update-database.ps1
./scripts/start-api.ps1
```

En otra terminal:

```powershell
./scripts/start-worker.ps1
```

En una tercera terminal, usando el Node instalado en esta PC:

```powershell
$env:PATH = (Resolve-Path .tools/node).Path + ';' + $env:PATH
Set-Location frontend
../.tools/node/npm.cmd run dev
```

Abrir la URL de Vite → Webcam → preparar dispositivo → configurar zona/línea con el editor → comprobar y confirmar encuadre → iniciar. Se muestran imagen analizada, cruces en ambos sentidos, total y cruces por minuto. Para pasillo elegir A→B/B→A; entradas/salidas corresponde a un acceso. No se cuentan asistentes únicos ni visitas estimadas.

Cerrar el navegador no detiene el trabajo. Detener solicita cierre y espera el estado final; el historial conserva resultados parciales, huecos y heatmap. Al perder cámara se hacen tres intentos; antes de analizar otra vez hay que confirmar una comprobación nueva. Agotados los intentos, Reintentar o Detener. No borrar datos para liberar el dispositivo.

## Medición

Captura e inferencia separadas, último frame pendiente. El origen analítico comienza después de cargar el modelo. Descartes conservan tiempo de captura; gap mayor a1s reinicia tracking/continuidad. Ventanas temporales de1/3s para oscilación/confirmación; cada cruce confirmado conserva su minuto original. El tramo final sin analizar se marca perdido, aunque sea corto.

FPS usan ventana reciente5s. Latencia captura-pantalla se estima después de cargar/pintar la imagen y calibrar relojes; informa incertidumbre. Evento flowsight:live-latency permite recolectar agregados sin imágenes. Pestaña oculta/reloj sin calibrar no produce muestra válida. Antigüedad y captura-publicación son mediciones distintas.

## Pruebas automatizadas

La limpieza elimina datos de la base de pruebas bajo el guard local existente; no usar la base de demo. Downgrade no conserva trabajos live y requiere retirar sus datos de prueba primero. No ejecutar pytest DB y Playwright al mismo tiempo: ambas suites usan una base local de prueba con modificaciones destructivas del esquema. Nunca usar Azure.

```powershell
Set-Location backend
./.venv/Scripts/ruff.exe check .
# Limpieza de la base local de pruebas tras E2E con datos live:
./.venv/Scripts/python.exe -m pytest tests/integration/test_live_machine.py::test_absent_or_stale_worker_is_unavailable -q -p no:cacheprovider --basetemp=../.verification/pytest-reset-01
./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=../.verification/pytest-manual-01
```

Elegir otro basetemp por ejecución si el anterior tiene permisos residuales en Windows.

```powershell
Set-Location frontend
npm run lint
npm test -- --maxWorkers=1
npm run build
npm run test:e2e -- live.spec.ts
```

En esta PC, PLAYWRIGHT_BROWSERS_PATH apunta a .tools/playwright. E2E usa API/worker/PostgreSQL/Chromium reales con captura y detector sintéticos; no requiere webcam ni pesos.

## Ensayos prolongados

```powershell
./scripts/validate-live.ps1 -Scenario Overload -DurationSeconds 600
./scripts/validate-live.ps1 -Scenario Stability -DurationSeconds 7200
```

El harness prueba captura en proceso real y sampler acotado. Overload captura30FPS y consume como máximo10 durante el primer80%, luego elimina la demora. Es un ensayo de componentes, no valida aplicación completa ni precisión física. JSON agregado en .verification registra pendientes, descartes, muestras, RSS y captura-lectura. ProcessIds agrega RSS de API/worker activos; StorageDirectory mide crecimiento total de archivos. No mide VRAM ni captura-pantalla. Comparar memoria requiere muestras después de los primeros10min. No declara SC-003/SC-007 aprobados automáticamente.

Falta aceptación física: webcam10min, ≥40cruces anotados por sentido, p95 captura-pantalla/error y estabilidad completa2h. Registrar equipo/encuadre/resultados en [hardware.md](validation/hardware.md). Estabilidad no necesita multitud. Evidencia de software: [implementation.md](validation/implementation.md). No se promete precisión o rendimiento para200asistentes sin medir concurrencia visible.
