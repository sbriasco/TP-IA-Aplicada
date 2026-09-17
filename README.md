# FlowSight

**Analítica de espacios comerciales a partir de videos de cámaras fijas.**

Proyecto del Grupo 6, integrado por seis estudiantes de Ingeniería en Informática, para Inteligencia Artificial Aplicada.

FlowSight busca transformar videos en información sobre circulación, entradas y salidas, permanencia y ocupación observable. El usuario podrá cargar un video, identificar locales y dibujar zonas y líneas sobre un frame; luego consultar los resultados en un dashboard y mediante un chat analítico.

El procesamiento de video y la persistencia se ejecutan localmente. El chat previsto consultará un modelo disponible en Azure desde el backend.

## Estado del proyecto

El proyecto está en desarrollo. Actualmente existen dos incrementos:

| Incremento | Estado y alcance |
| --- | --- |
| [Validación de videos y tracking](experiments/video-tracking-validation/README.md) | Experimento independiente con YOLO y ByteTrack en CPU, referencia manual, eventos y mediciones. Sus conclusiones dependen de los fragmentos y la configuración evaluados. |
| [Entorno y arquitectura base](specs/002-entorno-arquitectura-base/spec.md) | API, worker, PostgreSQL, sesiones y trabajos persistidos, trazabilidad y previsualización sintética en React mediante WebSocket. Validado localmente en Windows/CPU y mediante CI en Ubuntu. |

La aplicación base todavía no integra el procesamiento de videos reales. La carga de videos, el editor de escenas, las métricas comerciales, el dashboard y el chat son funcionalidades planificadas. La GPU permanece `not_evaluated`.

La [evidencia de validación de la base](specs/002-entorno-arquitectura-base/validation/base-verification.md) detalla pruebas ejecutadas y limitaciones.

## Alcance previsto

### MVP — 2 de octubre de 2026

- Carga de videos y configuración visual de locales, zonas y líneas.
- Detección de personas y tracking por video.
- Tráfico, flujo temporal, paso frente a locales, entradas/salidas, permanencia y ocupación observable, tasa de ingreso y horarios pico.
- Historial de sesiones, configuración, eventos y métricas en PostgreSQL local.
- Dashboard y chat mínimo para consultar métricas mediante herramientas del backend.
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
| Interfaz | React, TypeScript estricto y Vite; CSS Modules. SVG para el futuro editor y Recharts para gráficos. |
| API y validación | Python, FastAPI y Pydantic. |
| Persistencia | PostgreSQL local, SQLAlchemy y migraciones Alembic. |
| Visión | Ultralytics YOLO, PyTorch, OpenCV y ByteTrack inicial, evaluados en el experimento. |
| Chat previsto | API de modelo en Azure; servicio y modelo pendientes de validar. Credenciales y herramientas de analytics en el backend. |
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

Ejecutá los comandos desde la raíz del repositorio, salvo cuando se indique otra carpeta. Cada integrante utiliza su propia base PostgreSQL.

## Requisitos

- Git.
- Python 3.11.16 de 64 bits.
- Node.js 22.20.0 y npm.
- PostgreSQL 17 local.
- PowerShell.

## Preparación

```powershell
Copy-Item .env.example .env

& "C:\ruta\a\python-3.11.16.exe" -m venv backend\.venv
& "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.lock
& "backend\.venv\Scripts\python.exe" -m pip install --no-deps -e backend

Push-Location frontend
npm ci
Pop-Location
```

Completá `.env` con un usuario y una base PostgreSQL exclusivos de tu equipo. No uses una base compartida ni subas `.env` al repositorio.

PostgreSQL 17 puede instalarse con el instalador oficial para Windows. Si no tenés permisos administrativos, también puede usarse el ZIP oficial de binarios en `.tools/postgresql-17/pgsql`; esa carpeta y `.postgres-data` están excluidas de Git.

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
$env:FLOWSIGHT_DATABASE_URL = (Get-Content .env | Where-Object {
    $_ -like "FLOWSIGHT_DATABASE_URL=*"
}).Substring("FLOWSIGHT_DATABASE_URL=".Length)

Push-Location backend
& ".venv\Scripts\alembic.exe" upgrade head
Pop-Location
Remove-Item Env:FLOWSIGHT_DATABASE_URL
```

Si una migración falla, no borres la base ni ejecutes `downgrade`. Corregí la causa, consultá `alembic current` y volvé a ejecutar `upgrade head`.

## Orden de inicio

1. PostgreSQL local.
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

`test:e2e` aplica las migraciones, inicia temporalmente API y frontend, crea una sesión y un
trabajo sintético, ejecuta el worker y verifica en Chromium la conexión WebSocket, la preview
JPEG y el estado terminal. Los procesos temporales se cierran al finalizar. La API no inicia si
PostgreSQL no está disponible.

## Trabajo en equipo

GitHub contiene el código y los pull requests; [Azure Boards](https://dev.azure.com/sbriascocalvo/IA%20Aplicada/_boards) contiene épicas, features, historias, tareas y bugs.

Se trabaja en una rama por cambio y se integra a `main` mediante un PR breve con el cambio, su verificación y la tarea de Azure relacionada. Se utiliza squash merge y se elimina la rama integrada. Los estados del tablero deben reflejar la evidencia de implementación y validación.

El desarrollo se guía con Spec Kit: especificación y clarificaciones, checklist, plan técnico, tareas, análisis e implementación. La convergencia contrasta lo implementado con los requisitos antes de cerrar el incremento. Los documentos viven en `specs/`; su trazabilidad con Azure se mantiene explícitamente.

Antes de contribuir, consultá:

- [AGENTS.md](AGENTS.md): alcance, stack y reglas del proyecto.
- [Constitución](.specify/memory/constitution.md): principios de desarrollo y calidad.
- [Decisiones técnicas](docs/decisiones-tecnicas.md): fundamentos y validaciones pendientes.
- [Especificaciones](specs/): requisitos, planes y tareas de cada incremento.

Los asistentes de IA apoyan la planificación, implementación y verificación; sus cambios se revisan y sus afirmaciones se contrastan con pruebas. No se versionan credenciales, videos, pesos, bases de datos ni resultados locales. Las licencias de las dependencias y modelos deben revisarse antes de distribuir el proyecto; el experimento registra la procedencia de sus pesos en [SOURCE.md](experiments/video-tracking-validation/weights/SOURCE.md).
