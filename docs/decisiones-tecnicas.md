# Decisiones técnicas de FlowSight

Fecha: 14 de septiembre de 2026.

El equipo adopta este stack para planificar FlowSight con GitHub Copilot y Spec Kit. Se prioriza un entorno local que puedan reproducir los seis integrantes y mantener dos o tres desarrolladores activos. Las reglas del proyecto están en [AGENTS.md](../AGENTS.md).

La elección de tecnologías queda acordada; sus versiones, compatibilidad y rendimiento todavía deben comprobarse. Este documento no registra instalaciones ni pruebas ejecutadas y no autoriza instalar dependencias.

## Aplicación web

El frontend utiliza React, TypeScript con `strict` y Vite. React permite separar carga de video, editor de escena, previsualización, dashboard y chat en componentes; TypeScript ayuda a expresar los contratos de configuración, eventos y métricas.

Los estilos se organizan con CSS Modules. El editor utiliza SVG sobre el frame de referencia para representar polígonos, líneas y puntos editables. Las coordenadas deben conservar su correspondencia con las dimensiones originales del video al redimensionar la vista. Recharts se utiliza para los gráficos del dashboard.

Actualización de presentación (2026-10-01): se mantiene el stack y se carga Recharts al abrir el gráfico de resultados. `FLOWSIGHT_CORS_ORIGINS` permite configurar una lista JSON de orígenes exactos del frontend; conserva los orígenes locales por defecto. Esta configuración habilita pruebas en puertos aislados y prepara la conexión con un frontend alojado, pero no proporciona autenticación ni reemplaza HTTPS o controles de acceso. El procesamiento de visión sigue local.

El backend utiliza Python, FastAPI y Pydantic para exponer la API y validar datos. Python también se utiliza en el worker de visión, lo que permite compartir contratos y reglas sin incorporar otro lenguaje de backend. Se mantiene una API modular y un proceso separado para el trabajo pesado, dentro de un único repositorio.

## Persistencia

PostgreSQL sigue siendo la base relacional principal del producto (SQLAlchemy + Alembic).

### Evolución (2026-09-26)

**Antes (Feature #6 / spec 002):** cada integrante usaba solo PostgreSQL local. Eso era correcto para el entorno base, pero dificultaba integración, demo y pruebas compartidas de dashboard/historial/agente (seis bases distintas, export/import).

**Ahora:** dos modos de despliegue de la **misma** base, elegidos solo por `FLOWSIGHT_DATABASE_URL`:

| Modo | Uso | Servicio |
|---|---|---|
| **Compartido** | Integración entre integrantes, demo del MVP, datos comunes de sesión/métricas | **Azure Database for PostgreSQL – Flexible Server** |
| **Local** | Desarrollo aislado, tests automatizados, CI, trabajo sin red | PostgreSQL instalado en el equipo |

El código de aplicación **no** distingue Azure vs localhost: solo lee la URL. SSL y parámetros van en la connection string cuando el destino es Azure.

### Qué va en PostgreSQL

Sesiones, cámaras (identificadores), locales, configuración espacial (polígonos/líneas), processing jobs, eventos, métricas/resultados agregados, versiones necesarias para reproducibilidad y, desde specs/004, el **frame de referencia** de cada sesión de video.

### Qué NO va en PostgreSQL

Los videos originales nunca se guardan en la base (FR-007 de specs/004): permanecen en **disco local**, en la carpeta `FLOWSIGHT_VIDEOS_DIR` de cada equipo. Los previews en vivo del procesamiento y las trayectorias/archivos pesados también permanecen fuera de PostgreSQL, salvo decisión posterior.

**Excepción confirmada (specs/004, R5, 2026-09-26):** el frame de referencia de cada sesión de video sí va en PostgreSQL, como JPEG (calidad 90, resolución original) en la columna `bytea` de la tabla `reference_frames`, separada de `video_sources` para no cargar los listados. Se sirve con `GET /sessions/{id}/reference-frame` (`image/jpeg`, cacheable). Es la única forma de verlo desde un equipo distinto al que registró el video, sin exponer el archivo original ni sumar un file server.

### Qué permanece local (sin cambio)

El procesamiento de visión (YOLO, ByteTrack, worker) sigue siendo **local**. Azure PostgreSQL solo aloja la persistencia compartida; no mueve el pipeline de video a la nube.

### Migraciones y secretos

**Eliminación del historial (2026-10-01):** `DELETE /sessions/{id}` realiza una baja lógica con `sessions.deleted_at` (migración `0006_session_removal`). Se conservan archivos, resultados y escenas inmutables para no romper su uso desde otras sesiones. Los trabajos pendientes o en proceso bloquean la baja; crear trabajos y retirar la sesión comparten un bloqueo de fila. La sesión retirada deja de estar disponible en endpoints públicos, con la excepción del frame que siga referenciado por una escena guardada. No implica liberación de espacio en disco.

Las mismas migraciones Alembic aplican a local y a Azure. Credenciales de Azure PostgreSQL y Foundry solo en `.env` local / canal seguro del equipo; nunca en Git. Instrucciones para compañeros: [acceso-compartido-azure.md](acceso-compartido-azure.md). CI y pytest usan PostgreSQL local (o efímero) sin depender de la instancia compartida.

**Instancia compartida (2026-09-26):** host `ia-aplicada-flowsight.postgres.database.azure.com`, database `postgres`, usuario `flowsight`, migraciones `0001_initial` aplicadas. Cada integrante debe registrar su IP en el firewall.

### Relación con Feature #6

La spec 002 y la Feature #6 documentan e implementaron correctamente el entorno base **local**. Esta sección **evoluciona** la decisión de persistencia para el MVP integrado; no reescribe la historia de #6.

Arquitectura conceptual:

```text
Video (disco local)
    ↓
Worker local (YOLO + ByteTrack)
    ↓
Backend FastAPI
    ↓
FLOWSIGHT_DATABASE_URL
    ├── Azure PostgreSQL Flexible Server  → integración / demo
    └── PostgreSQL local                  → tests / CI / desarrollo aislado
```

## Detección y tracking

Se utiliza Ultralytics YOLO sobre PyTorch, con OpenCV para el manejo de frames. ByteTrack es el tracker inicial. Su adopción definitiva depende de evaluar cruces, oclusiones, pérdidas de tracks y duplicados con los videos seleccionados y un conteo manual de referencia. BoT-SORT es una alternativa a comparar si los resultados lo justifican.

**Dependencia confirmada (specs/004, R4, 2026-09-26):** el backend agrega `opencv-python-headless==4.10.0.84` (con su `numpy` fijado en el lock) a `backend/pyproject.toml` y `backend/requirements.lock`, la misma versión que usa `experiments/video-tracking-validation`. Se eligió la variante *headless* porque no trae dependencias de GUI y se instala en CI (Ubuntu) sin librerías de sistema adicionales; el worker de análisis de video (#56) la va a necesitar igual. No se agrega `python-multipart`: la subida de video usa el cuerpo crudo de la request (ver `specs/004-configuracion-escenas/research.md`, R1).

**Combinación fijada para el MVP (specs/005, actualizada 2026-09-30):** Ultralytics `8.4.153`, peso `yolo11m.pt` (YOLO11 medium, detección) y ByteTrack. El `yolov8n.pt` del experimento 001 marcaba carteles y perdía personas. Ultralytics documenta que YOLO11m sube el mAP de COCO respecto de YOLOv8m con 22 % menos parámetros ([YOLO11](https://docs.ultralytics.com/models/yolo11/)). El worker rechaza un archivo que no se llame `yolo11m.pt`. Esa comparación es de COCO, no de estos videos. El lock del repositorio trae `torch==2.7.1+cpu` y `torchvision==0.22.1+cpu`. El wheel de GPU no se versiona: en la RTX se instala `torch==2.7.1` y `torchvision==0.22.1` desde el índice CUDA 12.8, después del lock. Tests y CI usan `FLOWSIGHT_DETECTOR=fake` y no cargan el peso. Las tres medidas oficiales (entradas, salidas y ocupación visible) viven en `analysis_measures`.

En la RTX, un video de 2360 frames terminó con `execution_mode=cuda`, sin limitaciones, a 29,8 frames por segundo de procesamiento. Esa corrida usó `yolov8n` y quedó en `specs/005-procesamiento-tracking/validation/reference-run.json`. No se volvió a medir con `yolo11m`. Esa cifra no promete la misma velocidad para otros videos ni para el peso nuevo. Los equipos sin placa siguen en CPU.

Antes de distribuir el proyecto, registrar las condiciones de licencia aplicables a la versión de Ultralytics y a los pesos seleccionados.

## Trabajos y previsualización

Inicialmente se ejecuta un único worker que toma trabajos persistidos en PostgreSQL y procesa un video por vez. La gestión de estados y recuperación ante fallos se detallará en el plan de esta funcionalidad. Esta decisión evita incorporar un servicio de colas adicional al entorno inicial.

REST se utiliza para carga de videos, configuración, control de trabajos y consultas. WebSocket se utiliza para avances y previsualización durante el procesamiento. Los frames y sus detecciones deben asociarse por sesión, identificador de frame y timestamp del video, de modo que una actualización tardía no mezcle imágenes y resultados.

La codificación de imágenes, frecuencia de actualización y manejo de clientes lentos requieren una prueba técnica. Se puede reducir la frecuencia de la previsualización sin cambiar los tiempos de medición, que siempre provienen del video. Las métricas parciales deben identificarse como tales.

## Chat analítico

El backend consume por API un modelo disponible mediante **Azure AI Foundry**, usando la suscripción de estudiantes del equipo (crédito ~100 USD). La Feature #5 validó acceso con API key, cliente **`openai==1.109.1`** (OpenAI-compatible), deployment **`gpt-5-mini`** y región **`brazilsouth`**. La llamada simple y el tool calling con `get_session_traffic` ficticia quedaron demostrados; cuotas/costos del crédito: `not_measured`. Evidencia: `specs/003-validacion-modelo-azure/validation/summary.json`.

Las credenciales permanecen en el backend. El modelo consulta herramientas acotadas de analytics y redacta respuestas basadas en sus resultados; no procesa el video, no calcula las métricas y no ejecuta SQL arbitrario. El MVP utiliza integración directa con la API del modelo, sin incorporar un framework de agentes inicialmente.

Validación de chat real (2026-10-01): el presupuesto de 256 tokens agotaba la segunda llamada en razonamiento sin producir texto. Se usa `max_completion_tokens=2048` y `reasoning_effort=low`, conservando el deployment y el máximo de dos llamadas por pregunta. Prueba sintética contra Azure y petición a una API local completadas; cuotas y disponibilidad sostenida siguen sin medir. Ver [flujo compacto y evidencia](frontend-compacto-2026-10-01.md).

Revisión posterior del chat (2026-10-01): se exige consultar la herramienta acotada en la primera llamada y finalizar sin herramientas en la segunda. Nombres, unidades y motivos de no disponibilidad se entregan al modelo en lenguaje cotidiano. El filtro distingue referencias explícitas a identificadores de las cifras, conserva el conteo real de llamadas después de un rechazo y no cita un pico si faltan intervalos guardados. La interfaz mantiene el contexto del local; cada pregunta sigue siendo independiente y sobre toda la sesión. Ver [validación del agente y sus límites](chat-validacion-2026-10-01.md).

## Entorno y calidad

- Python se gestiona con `venv` y `pip`; el frontend utiliza Node.js y `npm`.
- PostgreSQL local sigue disponible para desarrollo aislado, tests y CI. Para integración/demo del MVP el equipo puede usar **Azure Database for PostgreSQL – Flexible Server** vía la misma `FLOWSIGHT_DATABASE_URL` (ver [Decisiones técnicas](docs/decisiones-tecnicas.md)). Los contenedores no son un requisito del entorno inicial.
- Las versiones compatibles se fijan en archivos de dependencias y lockfiles al preparar el entorno. La configuración de PyTorch debe distinguir CPU y GPU cuando corresponda.
- pytest verifica reglas, eventos, métricas e integración del backend. Playwright verifica recorridos del navegador, incluido el editor visual.
- GitHub Actions ejecutará CI cuando exista código, comenzando por build y pruebas relevantes. Las verificaciones ordinarias de PR deben funcionar sin GPU ni credenciales de Azure; las evaluaciones pesadas se ejecutan por separado y se documentan.
- El flujo de ramas y PRs se mantiene en `AGENTS.md`. GitHub aloja el código; Azure Boards concentra historias, tareas y bugs.

## Validaciones pendientes

La base sintética fue validada en CPU el 16 de septiembre de 2026. El flujo y la consulta de salud cumplieron los límites definidos; la evidencia anonimizada está en `specs/002-entorno-arquitectura-base/validation/`. La RTX 5080 quedó medida el 29 de septiembre de 2026: CUDA, 2360 frames, 29,8 frames por segundo de procesamiento (`specs/005-procesamiento-tracking/validation/reference-run.json`).

La previsualización base ya cuenta con verificaciones automáticas de reemplazo del frame pendiente, entrega antes del estado terminal y desconexión. La validación con video real y carga sostenida corresponde a las funcionalidades posteriores.

Continúan pendientes:

1. Comprobar compatibilidad y ejecución en la PC con RTX 5080. **Hecho (2026-09-29) con `yolov8n`:** `execution_mode=cuda`, 8.4.153, ByteTrack, 2360 frames, 29,8 frames por segundo de procesamiento. Ver `specs/005-procesamiento-tracking/validation/reference-run.json`. El worker pasó a `yolo11m` el 2026-09-30; esa velocidad no se volvió a medir.
2. Evaluar YOLO y ByteTrack con los videos disponibles, usando referencias manuales y registrando errores y tiempos.
3. Comprobar acceso a Azure AI Foundry (suscripción de estudiantes / crédito) y una consulta mínima con tool calling ficticio antes de fijar el SDK y el modelo. **Hecho (2026-09-26)**: Foundry `available`, `openai==1.109.1`, `gpt-5-mini`, tool calling `demonstrated`; ver `specs/003-validacion-modelo-azure/validation/summary.json`. Cuotas/costos siguen `not_measured`.
4. Verificar que las migraciones y los datos sintéticos permiten reproducir el entorno en otra computadora (PostgreSQL local) y aplicar las mismas migraciones a Azure Flexible Server cuando un integrante se conecte por primera vez (`alembic upgrade head`). **Hecho en instancia compartida (2026-09-30):** schema `0004_video_analysis`.
5. Comprobar firewall/SSL de **Azure Database for PostgreSQL – Flexible Server** por integrante (IP en portal). Guía: [acceso-compartido-azure.md](acceso-compartido-azure.md).

Estas validaciones pueden motivar ajustes documentados; no deben presentarse como completadas por haber elegido el stack.

## Referencias técnicas

- [Vite](https://vite.dev/guide/).
- [Recharts](https://recharts.github.io/).
- [WebSocket en FastAPI](https://fastapi.tiangolo.com/advanced/websockets/).
- [Alembic](https://alembic.sqlalchemy.org/en/latest/).
- [Azure Database for PostgreSQL – Flexible Server](https://learn.microsoft.com/azure/postgresql/flexible-server/).
- [PostgreSQL en Windows](https://www.postgresql.org/download/windows/).
- [Tracking con Ultralytics](https://docs.ultralytics.com/modes/track/).
- [Licencias de Ultralytics](https://www.ultralytics.com/license).
- [Instalación de PyTorch](https://pytorch.org/get-started/locally/).

## Registro de asistencia de IA

La selección se preparó con asistencia de IA a partir del alcance, `AGENTS.md`, las preferencias del equipo y documentación oficial. Se documentaron los motivos de elección y se distinguieron las decisiones del stack de las pruebas pendientes. No se instalaron dependencias ni se ejecutaron pruebas de la aplicación en esta etapa.

La evolución de persistencia (PostgreSQL local + Azure Flexible Server para integración/demo, 2026-09-26) y la guía de acceso del equipo (`docs/acceso-compartido-azure.md`) se registraron con asistencia de IA sin modificar Features #4/#5/#6 ni el esquema SQLAlchemy más allá de aplicar migraciones existentes a Azure.
