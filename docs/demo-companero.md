# Preparar la presentación en otra PC

Guía para Windows. El código se publica en la rama `fix/chat-grounding`; se integra a `main` mediante el PR correspondiente. Publicar el repositorio permite ejecutar la app en la PC del presentador; el despliegue web se trata por separado en [Vercel](despliegue-vercel.md).

## Obtener la versión

Para una copia nueva:

```powershell
git clone --branch fix/chat-grounding https://github.com/sbriasco/TP-IA-Aplicada.git
Set-Location TP-IA-Aplicada
```

Si ya tenés el repositorio, guardá tus cambios locales antes de actualizar:

```powershell
git fetch origin
git switch fix/chat-grounding
git pull --ff-only
```

Después de integrar el PR, se puede usar `main` con `git pull --ff-only`.

## Entorno y configuración

Si todavía no instalaste el entorno, seguí [Requisitos y preparación del README](../README.md#requisitos). Los scripts de instalación e inicio aceptan `-ProjectRoot`; desde la raíz podés indicarlo explícitamente como `-ProjectRoot (Get-Location).Path`, también en Windows PowerShell 5.1. Se usa Python 3.11, Node del `.node-version` y las dependencias fijadas del repositorio.

Actualizar las dependencias de una instalación existente:

```powershell
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock --no-deps
& backend\.venv\Scripts\python.exe -m pip install --no-deps -e backend
Push-Location frontend
npm ci
Pop-Location
```

Crear `.env` desde `.env.example` solo si todavía no existe:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Completar en esa PC:

- `FLOWSIGHT_DATABASE_URL`: PostgreSQL local para una presentación aislada, o la base compartida del equipo. Si elegís Azure PostgreSQL, pedir la contraseña y autorizar la IP pública de esa PC según [acceso compartido](acceso-compartido-azure.md).
- `FLOWSIGHT_AZURE_AI_API_KEY`: clave del equipo por canal privado. El ejemplo ya contiene los endpoints y el deployment. La clave es necesaria para el chat real, incluso usando PostgreSQL local.
- `FLOWSIGHT_VIDEOS_DIR`: carpeta absoluta de esa PC, por ejemplo `C:\FlowSight\videos`. `FLOWSIGHT_MACHINE_ID`: identificador propio, por ejemplo `equipo-demo`.
- Para detección real: `FLOWSIGHT_DETECTOR=ultralytics` y `FLOWSIGHT_YOLO_WEIGHTS=C:\FlowSight\weights\yolo11m.pt`. Obtener ese peso por separado y verificar la ruta; no viene en Git. El lock usa PyTorch CPU, que permite presentar sin asumir GPU; medir el tiempo con el clip elegido. `fake` es para pruebas y no demuestra detección real.
- API y frontend locales: conservar `127.0.0.1:8000` y `127.0.0.1:5173`. Mantener desactivado `FLOWSIGHT_CHAT_FAKE_DRAFTER` si existiera en el entorno de pruebas.

Para presentar videos propios, una base local evita que un worker de otra PC reclame trabajos cuyos archivos no tiene. Si usás la base compartida, coordinar **un solo worker**, ejecutado en el equipo que contiene los videos del análisis. Git y Azure PostgreSQL no transfieren videos ni archivos derivados entre PCs.

## Migrar e iniciar

Con PostgreSQL disponible, desde la raíz:

```powershell
& scripts\check-environment.ps1 -ProjectRoot (Get-Location).Path
Push-Location backend
& .venv\Scripts\python.exe -c "from dotenv import load_dotenv; load_dotenv('../.env'); from alembic import command; from alembic.config import Config; command.upgrade(Config('alembic.ini'), 'head')"
Pop-Location
```

El esquema debe llegar a `0006_session_removal`. La base Azure configurada por el equipo ya se migró el 2026-10-01; comprobar la revisión en la base elegida. No ejecutar `downgrade` para preparar una demo.

Abrir tres terminales en la raíz del repositorio:

```powershell
# Terminal 1: API.
& scripts\start-api.ps1 -ProjectRoot (Get-Location).Path
```

```powershell
# Terminal 2: único worker del entorno elegido.
& scripts\start-worker.ps1 -ProjectRoot (Get-Location).Path
```

```powershell
# Terminal 3: frontend.
Set-Location frontend
npm run dev
```

Abrir [FlowSight local](http://127.0.0.1:5173). Si había procesos anteriores de API o worker, detenerlos con `Ctrl+C` y volver a iniciarlos desde esta versión.

## Ensayo antes de presentar

1. Cargar un clip corto de cámara fija disponible en esa PC. Identificar un local, dibujar sus zonas y línea, guardar la escena y procesarlo.
2. Esperar `Resultados listos`; revisar las cifras finales y la previsualización. Un video registrado sin análisis no es un resultado procesado.
3. Seleccionar el local y preguntar por tráfico, ingresos, permanencia y horario pico. Comparar con sus indicadores; ver [validación del chat](chat-validacion-2026-10-01.md). Las cifras del chat corresponden a toda la sesión.
4. Si aparece que no hay métricas guardadas, elegir un análisis completo generado con esta versión. Esa respuesta no significa que Azure esté caído. No usar un histórico sin métricas como demostración de cifras.
5. Probar cambiar de sesión y eliminar una sesión de prueba sin trabajos activos. Reservar el video y el resultado principal para la presentación.

Las pruebas automatizadas validan el flujo; el ensayo debe hacerse en la PC que presentará, con su red, sus credenciales y su video real. El tiempo de procesamiento y la disponibilidad de Azure dependen de ese entorno. No se guardan claves, `.env`, videos ni pesos en el repositorio.
