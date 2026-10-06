# FlowSight

**Analítica de espacios comerciales a partir de videos de cámaras fijas.**

Proyecto del Grupo 6, integrado por seis estudiantes de Ingeniería en Informática, para Inteligencia Artificial Aplicada.

FlowSight busca transformar videos en información sobre circulación, entradas y salidas, permanencia y ocupación observable. El usuario podrá cargar un video, identificar locales y dibujar zonas y líneas sobre un frame; luego consultar los resultados en un dashboard y mediante un chat analítico.

El procesamiento de video se ejecuta localmente. PostgreSQL puede ser local o compartido en Azure según configuración. El chat consulta un modelo disponible en Azure desde el backend.

Para preparar la presentación en otra PC, seguir la [guía para el compañero](docs/demo-companero.md), con configuración, migraciones, orden de inicio y ensayo del chat.

## Estado del proyecto

El proyecto está en desarrollo. Los incrementos implementados y sus límites son:

| Incremento | Estado y alcance |
| --- | --- |
| [Validación de videos y tracking](experiments/video-tracking-validation/README.md) | Experimento independiente con YOLO y ByteTrack en CPU, referencia manual, eventos y mediciones. Sus conclusiones dependen de los fragmentos y la configuración evaluados. |
| [Entorno y arquitectura base](specs/002-entorno-arquitectura-base/spec.md) | API, worker, PostgreSQL, sesiones y trabajos persistidos, trazabilidad y previsualización sintética en React mediante WebSocket. Validado localmente en Windows/CPU y mediante CI en Ubuntu. *(Persistencia compartida Azure Flexible Server: decisión posterior; ver [decisiones técnicas](docs/decisiones-tecnicas.md).)* |
| [Configuración de escenas](specs/004-configuracion-escenas/spec.md) | Registro de video (cámaras, subida, sondeo de frames/fps/SHA-256 con OpenCV, frame de referencia, disponibilidad del video por equipo), configuración de escena versionada e inmutable (locales con zonas frontal/interior/vidriera y línea de entrada con sentido A→B) y editor visual en `/sessions/{id}/editor`. Desde ahí se crea el trabajo `video_analysis`. Validado con la suite automática de backend, frontend y Playwright (ver "Pruebas") y con las mediciones manuales de [quickstart.md](specs/004-configuracion-escenas/quickstart.md): SC-004 en la suite, SC-003 en aproximadamente 3 min y SC-001 en 0,77 s sobre el video real más largo disponible (94 s; no había uno de ~5 min). El escenario de un segundo equipo con la base compartida sigue pendiente. |
| [Procesamiento y tracking](specs/005-procesamiento-tracking/spec.md) | El worker procesa `video_analysis` con YOLO y ByteTrack. Tests y CI usan el detector `fake` y no cargan el peso. El lock fija PyTorch de CPU (`torch==2.7.1+cpu`); el wheel de GPU no entra al repositorio. Entradas, salidas y ocupación visible se guardan en `analysis_measures`. La vista en vivo muestra el seguimiento y el avance. El peso del worker es `yolo11m.pt`. En la RTX, un video de 2360 frames se procesó en CUDA a 29,8 frames por segundo con `yolov8n` ([reference-run.json](specs/005-procesamiento-tracking/validation/reference-run.json)); esa cifra no se volvió a medir con `yolo11m`. |
| [Eventos y métricas](specs/006-eventos-metricas/spec.md) | Eventos por track, ocho métricas por local, flujo temporal y horario pico persistidos. Los tiempos corresponden al video; los valores incompletos y las divisiones sin denominador se muestran como no disponibles. |
| [Dashboard e historial](specs/007-dashboard-historial/spec.md) | Historial por sesión, resultados, filtro temporal de hechos/flujo y muestra de posiciones sobre el frame. El tramo no recalcula los indicadores de toda la sesión. |
| [Chat analítico mínimo](specs/008-chat-analitico-minimo/spec.md) | Consulta acotada a cifras registradas del local y sesión, con credenciales en backend y pruebas de respuestas/rechazos. La suite usa un redactor de prueba; no valida disponibilidad ni cuotas reales de Azure. |

El frontend incluye una interfaz común adaptable a escritorio y móvil, navegación entre las etapas de una sesión, tarjetas de indicadores y gráficos cargados por separado. Ver [auditoría del MVP](docs/auditoria-mvp-2026-10-01.md) y [validación del rediseño](docs/frontend-redesign-2026-10-01.md). La entrega pública requiere preparar acceso y operación del backend/worker; generar el build del frontend no completa ese despliegue.

Para alojarlo: [propuesta de despliegue con frontend en Vercel](docs/despliegue-vercel.md), configuración del proyecto y pendientes de API/worker.

La [evidencia de validación de la base](specs/002-entorno-arquitectura-base/validation/base-verification.md) detalla pruebas ejecutadas y limitaciones.

## Alcance previsto

### MVP — 2 de octubre de 2026

- Carga de videos y configuración visual de locales, zonas y líneas.
- Detección de personas y tracking por video.
- Tráfico, flujo temporal, paso frente a locales, entradas/salidas, permanencia y ocupación observable, tasa de ingreso y horarios pico.
- Historial de sesiones, configuración, eventos y métricas en PostgreSQL (local y/o Azure Flexible Server según configuración).
- Dashboard y chat mínimo para consultar métricas mediante herramientas del backend.
- Historial único con estados y eliminación lógica de sesiones. Interfaz compacta y agente de IA: ver [validación del flujo](docs/frontend-compacto-2026-10-01.md).
- Heatmap, sujeto al avance del proyecto.

### Versión final — 13 de noviembre de 2026

Se evaluarán exposición, detención y atención estimada hacia vidrieras, funnel comercial, patrones de visita dentro de una cámara, grupos estimados, señales de posible compra, comparaciones e insights y un chat ampliado. Estas capacidades requieren validación con los videos disponibles.

### Límites de interpretación

Un `track_id` es temporal y pertenece a una sesión; no identifica a una persona real ni garantiza un conteo de personas únicas. Las métricas usan timestamps del video, y la ocupación corresponde a lo observable por la cámara. No se infiere permanencia dentro de un local cuando se pierde el seguimiento.

Quedan fuera del alcance comprometido el reconocimiento facial, la identidad real, el seguimiento entre cámaras y la confirmación de compras. Atención y posible compra se presentarán como estimaciones. No se promete procesamiento en tiempo real antes de medirlo.

## Arquitectura y tecnologías

El repositorio reúne una interfaz web, una API y un worker Python separado. La API gestiona las consultas y los trabajos persistidos en PostgreSQL; el worker procesa un trabajo por vez. REST comunica las operaciones y WebSocket entrega avances y previsualización. Videos y archivos derivados permanecen en disco local.

| Capa | Stack acordado |
| --- | --- |
| Interfaz | React, TypeScript estricto y Vite; CSS Modules, editor SVG y Recharts para gráficos. |
| API y validación | Python, FastAPI y Pydantic. |
| Persistencia | PostgreSQL (SQLAlchemy + Alembic). Local para tests/CI; Azure Flexible Server opcional para integración/demo. Videos en disco local. |
| Visión | Ultralytics YOLO, PyTorch, OpenCV y ByteTrack inicial, evaluados en el experimento. |
| Chat | Azure AI Foundry con el deployment validado `gpt-5-mini`. Credenciales y herramientas acotadas de analytics en el backend. |
| Calidad | pytest, Vitest, Playwright y workflow de GitHub Actions. |

El stack acordado incluye componentes futuros; los archivos de dependencias de cada módulo indican qué está instalado actualmente. Los motivos y validaciones pendientes se documentan en [Decisiones técnicas](docs/decisiones-tecnicas.md).

## Organización del repositorio

```text
backend/       API, worker, persistencia, migraciones y pruebas
frontend/      Interfaz de supervisión y pruebas de navegador
fixtures/      Datos sintéticos versionados
scripts/       Inicio y verificación del entorno local
experiments/   Experimentos independientes de validación técnica
specs/         Especificaciones, planes, tareas y evidencia por feature
docs/          Decisiones y documentación del proyecto
.github/       CI e instrucciones, skills y agentes de desarrollo
.specify/      Configuración y constitución de Spec Kit
```

## Empezar a desarrollar

Las instrucciones siguientes preparan la **aplicación base con datos sintéticos**. Este recorrido no necesita videos, pesos, GPU ni credenciales de Azure. Para ejecutar el experimento de visión, usá su [README específico](experiments/video-tracking-validation/README.md) y su entorno independiente.

Ejecutá los comandos desde la raíz del repositorio, salvo cuando se indique otra carpeta. Para desarrollo aislado y tests usá PostgreSQL local. Para integración/demo del equipo podés apuntar `FLOWSIGHT_DATABASE_URL` a Azure Database for PostgreSQL – Flexible Server (misma app, distinta URL).

## Requisitos

- Git.
- PowerShell.
- Python 3.11.16 de 64 bits, Node.js 22.20.0 y PostgreSQL 17. No van en `requirements.lock` ni en `package.json`: son los programas donde después se instalan las librerías.

En Windows, este script los descarga en `.tools/` (no va a Git), crea `backend\.venv` y una base local `flowsight` en el puerto 5432, la misma del `.env.example`:

```powershell
.\scripts\install-prerequisites.ps1
```

Si Node quedó en `.tools\node`, abrí una terminal nueva para que `npm` esté en el PATH. Si el puerto 5432 ya está ocupado, el script no toca ese servidor.

## Preparación

```powershell
.\scripts\install-prerequisites.ps1

& "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.lock --no-deps
& "backend\.venv\Scripts\python.exe" -m pip install --no-deps -e backend

Push-Location frontend
npm ci
Pop-Location
```

Completá `.env` con `FLOWSIGHT_DATABASE_URL`. Por defecto el ejemplo apunta a PostgreSQL local. Para la base compartida de integración/demo y para Foundry (API key), seguí **[`docs/acceso-compartido-azure.md`](docs/acceso-compartido-azure.md)**: secretos solo por canal seguro del equipo, nunca en Git. Cada integrante debe agregar su IP al firewall de Azure PostgreSQL.

Para registrar videos (specs/004), completá además `FLOWSIGHT_VIDEOS_DIR` (ruta absoluta a una carpeta fuera del repo, donde se copian los videos registrados). La API y el worker arrancan sin ella, pero registrar o recargar un video responde 503 (`videos_dir_not_configured`) hasta que esté configurada. El identificador del equipo y la conexión local de webcam se generan automáticamente y se comparten mediante `.tools/runtime/webcam.json`, excluido de Git. No hace falta completar `FLOWSIGHT_MACHINE_ID` ni `FLOWSIGHT_LIVE_CHANNEL_TOKEN`; los valores explícitos siguen disponibles como ajustes opcionales.

PostgreSQL queda en `.tools/postgresql-17/pgsql`. Esa carpeta y `.postgres-data` están excluidas de Git. Para volver a levantarlo:

```powershell
& ".tools\postgresql-17\pgsql\bin\pg_ctl.exe" -D ".postgres-data" -l ".postgres-data\server.log" start
```

## Verificación inicial

Con PostgreSQL iniciado:

```powershell
# Solo para la instalación binaria local de este equipo:
& ".tools\postgresql-17\pgsql\bin\pg_ctl.exe" `
    -D ".postgres-data" `
    -l ".postgres-data\server.log" start

& scripts\check-environment.ps1
```

El comando comprueba versiones, variables obligatorias y conexión. Devuelve código distinto de cero ante un requisito faltante y nunca imprime la URL de conexión ni contraseñas.

Para aplicar el esquema de forma repetible:

```powershell
./scripts/update-database.ps1
```

Si una migración falla, no borres la base ni ejecutes `downgrade`. Corregí la causa, consultá `alembic current` y volvé a ejecutar `upgrade head`.

Al actualizar el repositorio, ejecutá este script antes de reiniciar la API y el worker. Usa la base configurada en `.env` y aplica solo las migraciones que falten. `0007` permite retirar cámaras conservando sus análisis; `0008` permite retirar configuraciones sin modificar las escenas guardadas ni los resultados históricos.

La migración `0002` (specs/004) crea una cámara por cada `camera_id` de texto distinto usado en sesiones sintéticas previas. Si dos `camera_id` solo difieren en mayúsculas/espacios (por ejemplo `"Cam01"` y `"cam01 "`), no se fusionan: la cámara con la sesión más antigua conserva el nombre y las siguientes reciben un sufijo (`"cam01 (2)"`, `"cam01 (3)"`, …) para no violar la unicidad de nombre. Cada conflicto queda registrado con `logger.warning` en el log de Alembic, con los nombres involucrados. No se fusionan sesiones ni se modifica `sessions.camera_id`.

## Orden de inicio

1. PostgreSQL (local o la URL configurada en `.env`).
2. `scripts/check-environment.ps1`.
3. `scripts/start-api.ps1`.
4. `scripts/start-worker.ps1`.
5. `npm run dev` desde `frontend/`.

La API y el worker leen `.env` y detienen el arranque si la configuración obligatoria o PostgreSQL no están disponibles. El worker recupera trabajos interrumpidos antes de reclamar trabajos pendientes.

## Detención

Detené frontend, worker y API con `Ctrl+C`. Para la instalación binaria local de este equipo:

```powershell
& ".tools\postgresql-17\pgsql\bin\pg_ctl.exe" -D ".postgres-data" stop
```

La detención conserva la base y no ejecuta migraciones descendentes.

## Pruebas

Con PostgreSQL disponible y `.env` configurado:

```powershell
Push-Location backend
& ".venv\Scripts\ruff.exe" check .
& ".venv\Scripts\pytest.exe"
Pop-Location

Push-Location frontend
npm run lint
npm test
npm run build
npm run test:e2e
Pop-Location
```

`pytest` nunca corre contra la base compartida de Azure: las pruebas que hacen `downgrade`, `TRUNCATE` o insertan datos usan el helper `destructive_database_url()` (`backend/tests/conftest.py`), que toma `FLOWSIGHT_TEST_DATABASE_URL` si está definida y, si falta, acepta `FLOWSIGHT_DATABASE_URL` solo cuando el host es `localhost`, `127.0.0.1` o `::1`. Un host `*.postgres.database.azure.com` se rechaza siempre, aunque venga en `FLOWSIGHT_TEST_DATABASE_URL`. Si tu `FLOWSIGHT_DATABASE_URL` apunta a Azure, definí `FLOWSIGHT_TEST_DATABASE_URL` con un PostgreSQL local (en la terminal o en `.env`, ver `.env.example`) para poder correr esas pruebas.

`test:e2e` aplica las migraciones, inicia temporalmente API y frontend, crea una sesión y un
trabajo sintético, ejecuta el worker y verifica en Chromium la conexión WebSocket, la preview
JPEG y el estado terminal. Los procesos temporales se cierran al finalizar. La API no inicia si
PostgreSQL no está disponible. Las variables exportadas en la terminal tienen prioridad sobre `.env`
(que solo completa las faltantes), y el runner aborta antes de migrar si `FLOWSIGHT_DATABASE_URL`
apunta a un host `*.postgres.database.azure.com`. Si `FLOWSIGHT_TEST_DATABASE_URL` está definida (en la
terminal o en `.env`), el e2e la usa como `FLOWSIGHT_DATABASE_URL`, igual que las pruebas del backend.

## Trabajo en equipo

GitHub contiene el código y los pull requests; [Azure Boards](https://dev.azure.com/sbriascocalvo/IA%20Aplicada/_boards) contiene épicas, features, historias, tareas y bugs.

Validación del modelo en Azure AI Foundry (Feature #5): guía en [`specs/003-validacion-modelo-azure/quickstart.md`](specs/003-validacion-modelo-azure/quickstart.md), credenciales del equipo en [`docs/acceso-compartido-azure.md`](docs/acceso-compartido-azure.md) y evidencia anonimizada en [`specs/003-validacion-modelo-azure/validation/`](specs/003-validacion-modelo-azure/validation/). La CI ordinaria **no** requiere credenciales Azure; las pruebas `pytest -k llm` son locales/mock.

Se trabaja en una rama por cambio y se integra a `main` mediante un PR breve con el cambio, su verificación y la tarea de Azure relacionada. Se utiliza squash merge y se elimina la rama integrada. Los estados del tablero deben reflejar la evidencia de implementación y validación.

El desarrollo se guía con Spec Kit: especificación y clarificaciones, checklist, plan técnico, tareas, análisis e implementación. La convergencia contrasta lo implementado con los requisitos antes de cerrar el incremento. Los documentos viven en `specs/`; su trazabilidad con Azure se mantiene explícitamente.

Antes de contribuir, consultá:

- [AGENTS.md](AGENTS.md): alcance, stack y reglas del proyecto.
- [Constitución](.specify/memory/constitution.md): principios de desarrollo y calidad.
- [Decisiones técnicas](docs/decisiones-tecnicas.md): fundamentos y validaciones pendientes.
- [Acceso compartido Azure](docs/acceso-compartido-azure.md): PostgreSQL Flexible Server + Foundry (sin secretos en Git).
- [Especificaciones](specs/): requisitos, planes y tareas de cada incremento.

Los asistentes de IA apoyan la planificación, implementación y verificación; sus cambios se revisan y sus afirmaciones se contrastan con pruebas. No se versionan credenciales, videos, pesos, bases de datos ni resultados locales. Las licencias de las dependencias y modelos deben revisarse antes de distribuir el proyecto; el experimento registra la procedencia de sus pesos en [SOURCE.md](experiments/video-tracking-validation/weights/SOURCE.md).
