# Medición en el equipo de referencia

CI no exige este archivo ni una placa de video. La suite normal no recolecta la prueba marcada `gpu`. El lock del repo instala PyTorch para CPU a propósito: en el equipo con la RTX hay que reemplazar solo esas dos ruedas, sin tocar el lock.

La rama es `feature/005-procesamiento-tracking`. Hasta que esté en el remoto, el otro equipo no puede clonarla.

## Qué hay que tener antes

Python, Node y PostgreSQL no entran en `backend/requirements.lock` ni en `frontend/package.json`. Esos archivos instalan librerías dentro de un Python y un Node que ya están en la máquina. En Windows los baja `scripts/install-prerequisites.ps1`: Python 3.11.16 de 64 bits, Node.js 22.20.0 y PostgreSQL 17, más la base local `flowsight` del `.env.example`.

También hace falta un driver reciente de la RTX 5080. No hace falta instalar el CUDA Toolkit: el wheel de PyTorch trae el runtime. Y un video corto (uno o dos minutos alcanza) más el peso `yolo11m.pt` fuera del repositorio. El worker no acepta `yolov8n.pt` ni `yolov8s.pt`.

## Instalación

```powershell
git clone https://github.com/sbriasco/TP-IA-Aplicada.git
cd TP-IA-Aplicada
git checkout feature/005-procesamiento-tracking
.\scripts\install-prerequisites.ps1
& "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.lock --no-deps
& "backend\.venv\Scripts\python.exe" -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
& "backend\.venv\Scripts\python.exe" -m pip install --no-deps -e backend
```

Abrí una terminal nueva si el script avisó que agregó Node al PATH, y desde `frontend` corré `npm ci`.

El segundo `pip` tiene que ir después del lock. Si se invierte el orden, el lock vuelve a dejar PyTorch de CPU y la placa no se usa. No commitear ese cambio.

Descargar `yolo11m.pt` desde https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11m.pt a una carpeta fuera del repo, por ejemplo `C:\FlowSight\weights\yolo11m.pt`. Es el modelo medium de detección, licencia AGPL-3.0. Tamaño 40684120 bytes. SHA-256: `D5FFC1A674953A08E11A8D21E022781B1B23A19B730AFC309290BD9FB5305B95`. El experimento 001 sigue usando `yolov8n.pt`; ese archivo no sirve para el worker.

Comprobar la placa antes de analizar un video:

```powershell
& "backend\.venv\Scripts\python.exe" -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

Tiene que imprimir una versión `2.7.1+cu128`, CUDA `12.8` y `True`. Si imprime `False`, el análisis va a terminar en CPU y esa corrida no sirve como medición de la RTX.

## Configuración

Copiar `.env.example` a `.env` y dejar:

- `FLOWSIGHT_DATABASE_URL` apuntando a PostgreSQL local, por ejemplo `postgresql+psycopg://flowsight:flowsight@127.0.0.1:5432/flowsight`.
- `FLOWSIGHT_DETECTOR=ultralytics`
- `FLOWSIGHT_YOLO_WEIGHTS` con la ruta del `.pt`.
- `FLOWSIGHT_VIDEOS_DIR` con una carpeta absoluta fuera del repo.
- `FLOWSIGHT_MACHINE_ID` con un identificador de equipo, por ejemplo `equipo-rtx`. No usar un nombre de persona ni el usuario de Windows.

La base `flowsight` ya la crea el script de prerrequisitos. Aplicar migraciones:

```powershell
cd backend
& ".\.venv\Scripts\alembic.exe" upgrade head
cd ..
.\scripts\check-environment.ps1
```

## Cómo correrlo

Tres terminales, en este orden, con el venv activo donde haga falta:

```powershell
.\scripts\start-api.ps1
.\scripts\start-worker.ps1
cd frontend; npm run dev
```

En el navegador, `http://127.0.0.1:5173`:

1. Registrar una cámara y una sesión con el video corto.
2. En el editor de escena, agregar un local, una zona frontal y una línea de entrada, y guardar.
3. Volver a la sesión y pulsar **Iniciar análisis**. El texto que dice que el trabajo queda pendiente es viejo: si el worker está corriendo, lo toma solo.
4. Abrir `http://127.0.0.1:5173/?job=<id>` con el id que muestra la página y esperar a que el estado pase a completado.

## Resultado

`reference-run.json` es la corrida del 2026-09-29 en la RTX, con PostgreSQL local y `yolov8n`. `execution_mode` es `cuda`, sin limitaciones. El video tiene 2360 frames y la tasa fue 29,8 frames por segundo de procesamiento. El worker pasó a `yolo11m` y esa medición no se repitió.

## Qué devolver

Al terminar, el worker escribe `derived/<sesión>/<trabajo>/evidence.json` dentro de `FLOWSIGHT_VIDEOS_DIR`. Ese archivo de la corrida con `yolov8n` ya está copiado como `reference-run.json`. Una corrida nueva con `yolo11m` no reemplaza ese JSON.

Tiene que traer `execution_mode` en `cuda`, las versiones del detector y del tracker, y `frames_per_processing_second`. Si `execution_mode` es `cpu` o `limitations` dice que la placa no se usó, la medición no cuenta.

No mandar el `.env`, el video, el peso, capturas con el usuario de Windows, ni el nombre de la máquina.
