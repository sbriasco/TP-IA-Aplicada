# Decisiones técnicas de FlowSight

Fecha: 14 de septiembre de 2026.

El equipo adopta este stack para planificar FlowSight con GitHub Copilot y Spec Kit. Se prioriza un entorno local que puedan reproducir los seis integrantes y mantener dos o tres desarrolladores activos. Las reglas del proyecto están en [AGENTS.md](../AGENTS.md).

La elección de tecnologías queda acordada; sus versiones, compatibilidad y rendimiento todavía deben comprobarse. Este documento no registra instalaciones ni pruebas ejecutadas y no autoriza instalar dependencias.

## Aplicación web

El frontend utiliza React, TypeScript con `strict` y Vite. React permite separar carga de video, editor de escena, previsualización, dashboard y chat en componentes; TypeScript ayuda a expresar los contratos de configuración, eventos y métricas.

Los estilos se organizan con CSS Modules. El editor utiliza SVG sobre el frame de referencia para representar polígonos, líneas y puntos editables. Las coordenadas deben conservar su correspondencia con las dimensiones originales del video al redimensionar la vista. Recharts se utiliza para los gráficos del dashboard.

El backend utiliza Python, FastAPI y Pydantic para exponer la API y validar datos. Python también se utiliza en el worker de visión, lo que permite compartir contratos y reglas sin incorporar otro lenguaje de backend. Se mantiene una API modular y un proceso separado para el trabajo pesado, dentro de un único repositorio.

## Persistencia local

Cada integrante utiliza PostgreSQL local, con SQLAlchemy para el acceso a datos y Alembic para las migraciones. Las migraciones, configuración de ejemplo y datos sintéticos pequeños se versionan para reproducir la estructura y las pruebas.

Esta elección permite desarrollar sin depender de un servidor de base de datos compartido y evita que una prueba modifique los datos de otros integrantes. Una vez disponibles las dependencias y los modelos, el procesamiento y la consulta local de resultados no requieren internet; el chat mediante Azure sí lo requiere.

Las bases no se sincronizan automáticamente. Las sesiones que deban compartirse requieren exportar e importar sus datos y, cuando corresponda, los archivos asociados. La demostración integrada puede ejecutarse desde la PC de referencia.

PostgreSQL conserva sesiones, configuración, trabajos, eventos y métricas. Los videos y archivos derivados permanecen en disco local y fuera de Git. No se guarda una fila por persona y frame por defecto; el almacenamiento de trayectorias detalladas se define según las métricas que lo requieran.

## Detección y tracking

Se utiliza Ultralytics YOLO sobre PyTorch, con OpenCV para el manejo de frames. ByteTrack es el tracker inicial. Su adopción definitiva depende de evaluar cruces, oclusiones, pérdidas de tracks y duplicados con los videos seleccionados y un conteo manual de referencia. BoT-SORT es una alternativa a comparar si los resultados lo justifican.

La variante y los pesos de YOLO, los umbrales del tracker y la combinación de Python, PyTorch y CUDA se fijarán después de la validación técnica. La RTX 5080 de 16 GB es la GPU de referencia, pero el entorno debe contemplar ejecución en CPU y pruebas sintéticas para equipos sin esa GPU. No se promete velocidad de video en tiempo real.

Antes de distribuir el proyecto, registrar las condiciones de licencia aplicables a la versión de Ultralytics y a los pesos seleccionados.

## Trabajos y previsualización

Inicialmente se ejecuta un único worker que toma trabajos persistidos en PostgreSQL y procesa un video por vez. La gestión de estados y recuperación ante fallos se detallará en el plan de esta funcionalidad. Esta decisión evita incorporar un servicio de colas adicional al entorno inicial.

REST se utiliza para carga de videos, configuración, control de trabajos y consultas. WebSocket se utiliza para avances y previsualización durante el procesamiento. Los frames y sus detecciones deben asociarse por sesión, identificador de frame y timestamp del video, de modo que una actualización tardía no mezcle imágenes y resultados.

La codificación de imágenes, frecuencia de actualización y manejo de clientes lentos requieren una prueba técnica. Se puede reducir la frecuencia de la previsualización sin cambiar los tiempos de medición, que siempre provienen del video. Las métricas parciales deben identificarse como tales.

## Chat analítico

El backend consume por API un modelo disponible mediante Azure. El servicio, SDK y modelo concretos quedan pendientes de comprobar acceso, créditos, región, cuotas y soporte de las herramientas necesarias.

Las credenciales permanecen en el backend. El modelo consulta herramientas acotadas de analytics y redacta respuestas basadas en sus resultados; no procesa el video, no calcula las métricas y no ejecuta SQL arbitrario. El MVP utiliza integración directa con la API del modelo, sin incorporar un framework de agentes inicialmente.

## Entorno y calidad

- Python se gestiona con `venv` y `pip`; el frontend utiliza Node.js y `npm`.
- PostgreSQL se instala localmente. Los contenedores no son un requisito del entorno inicial.
- Las versiones compatibles se fijan en archivos de dependencias y lockfiles al preparar el entorno. La configuración de PyTorch debe distinguir CPU y GPU cuando corresponda.
- pytest verifica reglas, eventos, métricas e integración del backend. Playwright verifica recorridos del navegador, incluido el editor visual.
- GitHub Actions ejecutará CI cuando exista código, comenzando por build y pruebas relevantes. Las verificaciones ordinarias de PR deben funcionar sin GPU ni credenciales de Azure; las evaluaciones pesadas se ejecutan por separado y se documentan.
- El flujo de ramas y PRs se mantiene en `AGENTS.md`. GitHub aloja el código; Azure Boards concentra historias, tareas y bugs.

## Validaciones pendientes

La base sintética fue validada en CPU el 16 de septiembre de 2026. El flujo y la consulta de salud cumplieron los límites definidos; la evidencia anonimizada está en `specs/002-entorno-arquitectura-base/validation/`. La RTX 5080 continúa como `not_evaluated` hasta ejecutar el mismo procedimiento en esa PC.

La previsualización base ya cuenta con verificaciones automáticas de reemplazo del frame pendiente, entrega antes del estado terminal y desconexión. La validación con video real y carga sostenida corresponde a las funcionalidades posteriores.

Continúan pendientes:

1. Comprobar compatibilidad y ejecución en la PC con RTX 5080.
2. Evaluar YOLO y ByteTrack con los videos disponibles, usando referencias manuales y registrando errores y tiempos.
3. Comprobar acceso y una consulta mínima al servicio de modelo de Azure antes de fijar el SDK y modelo.
4. Verificar que las migraciones y los datos sintéticos permiten reproducir el entorno en otra computadora.

Estas validaciones pueden motivar ajustes documentados; no deben presentarse como completadas por haber elegido el stack.

## Referencias técnicas

- [Vite](https://vite.dev/guide/).
- [Recharts](https://recharts.github.io/).
- [WebSocket en FastAPI](https://fastapi.tiangolo.com/advanced/websockets/).
- [Alembic](https://alembic.sqlalchemy.org/en/latest/).
- [PostgreSQL en Windows](https://www.postgresql.org/download/windows/).
- [Tracking con Ultralytics](https://docs.ultralytics.com/modes/track/).
- [Licencias de Ultralytics](https://www.ultralytics.com/license).
- [Instalación de PyTorch](https://pytorch.org/get-started/locally/).

## Registro de asistencia de IA

La selección se preparó con asistencia de IA a partir del alcance, `AGENTS.md`, las preferencias del equipo y documentación oficial. Se documentaron los motivos de elección y se distinguieron las decisiones del stack de las pruebas pendientes. No se instalaron dependencias ni se ejecutaron pruebas de la aplicación en esta etapa.
