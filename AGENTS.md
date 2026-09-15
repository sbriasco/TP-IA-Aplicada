# FlowSight

## Contexto del producto

FlowSight es una plataforma de analítica de espacios comerciales para el Grupo 6, seis estudiantes de Ingeniería en Informática. El MVP vence el 2 de octubre de 2026 y la versión final el 13 de noviembre de 2026.

El usuario carga un video de una cámara fija y configura la escena sobre un frame: polígonos de interés, líneas de entrada/salida y locales identificados manualmente. El sistema procesa el video y sincroniza detecciones, `track_id` temporales, zonas y eventos con los timestamps de los frames analizados; luego ofrece un dashboard y consultas sobre resultados actuales o históricos. El procesamiento es local. La PC de referencia tiene Windows y una RTX 5080 de 16 GB de VRAM, pero no se debe asumir esa GPU en todos los equipos ni prometer velocidad de video en tiempo real antes de medirla.

## Alcance

### MVP

- Carga de videos y configuración visual de locales, zonas y líneas.
- Detección de personas y tracking por video.
- Tráfico, flujo temporal, paso frente a locales, entradas/salidas, permanencia y ocupación observable, tasa de ingreso y horarios pico.
- Persistencia local en PostgreSQL de sesiones, configuración, eventos y métricas.
- Dashboard y chat mínimo que consulte métricas mediante una API de modelo disponible en Azure.
- Heatmap solo si el avance lo permite.

### Evolución final

Exposición, detención y atención estimada hacia vidrieras; funnel comercial y patrones de visita dentro de una cámara; análisis de grupos; detección de bolsas como señal de posible compra; chat analítico ampliado e insights. Validar estas capacidades con los videos disponibles antes de comprometer su precisión. Reconocimiento facial, identidad real, seguimiento entre cámaras y confirmación de compras están fuera del alcance comprometido.

## Arquitectura y datos

- Separar procesamiento de video, detección/tracking, reglas espaciales, eventos, métricas, API y presentación.
- Utilizar YOLO con ByteTrack como tracker inicial; validar su desempeño con los videos seleccionados y comparar con BoT-SORT si los resultados lo justifican.
- Respetar el stack acordado a continuación. Evaluar y documentar cambios antes de adoptarlos; no asumir versiones ni compatibilidad de GPU sin validarlas.
- El LLM consulta herramientas/API de analytics. No calcula métricas desde el video ni ejecuta SQL arbitrario generado por el modelo.
- Mantener credenciales y llamadas al modelo en el backend.
- Un `track_id` es temporal y pertenece a una sesión/cámara: no representa una identidad real ni garantiza una persona única.
- Medir tiempos con timestamps del video, no con el tiempo de procesamiento.
- Debe existir persistencia y aislamiento por sesión; versionar migraciones, configuración de ejemplo e instrucciones.

## Stack acordado

- Frontend: React, TypeScript con `strict` y Vite; CSS Modules para estilos, SVG sobre el frame para el editor visual y Recharts para gráficos.
- Backend: Python, FastAPI y Pydantic. Worker Python separado para visión, en el mismo repositorio.
- Datos: PostgreSQL local por integrante, SQLAlchemy y migraciones con Alembic. Videos y archivos derivados en disco local.
- Visión: Ultralytics YOLO, PyTorch y OpenCV; ByteTrack como punto de partida sujeto a evaluación.
- Comunicación: REST para carga, configuración y consultas; WebSocket para avances y previsualización sincronizada. Validar el transporte de frames antes de comprometer rendimiento.
- Chat: API de modelo disponible en Azure, consumida desde el backend mediante herramientas acotadas de analytics; servicio y modelo concretos pendientes de validar.
- Entorno: Python con `venv` y `pip`, Node.js con `npm` y PostgreSQL instalado localmente. Un worker y trabajos persistidos en PostgreSQL inicialmente.
- Calidad: pytest y Playwright; GitHub Actions para CI cuando exista código.
- Fijar versiones en los archivos de dependencias y lockfiles al preparar el entorno. Elegir tecnologías no autoriza su instalación en esta etapa.

Consultar [Decisiones técnicas](docs/decisiones-tecnicas.md) para los motivos, límites y validaciones pendientes. Mantener ambos documentos alineados al cambiar una decisión.

## Reglas de medición

- Evitar eventos duplicados por oscilaciones en líneas y bordes.
- Distinguir ocupación visible de ocupación total de un local.
- No inferir permanencia dentro de un comercio si se pierde el seguimiento.
- Documentar denominadores, deduplicación y tratamiento de datos incompletos; una división por cero se muestra como no disponible.
- Calcular conversiones entre etapas solo con tracks vinculados y criterios compatibles.
- Mostrar atención y posible compra como estimaciones.
- Validar conjuntamente los videos candidatos y su adecuación.

## Trabajo en equipo e IA

- Usar GitHub para código, ramas y pull requests; Azure DevOps para historias, tareas y bugs. Consultar el contexto mediante Azure DevOps MCP cuando corresponda.
- GitHub Copilot y Spec Kit forman parte del proceso. Definir roles de agentes, skills y MCP adicionales según necesidades.
- Usar Playwright para verificar recorridos de la interfaz.
- Incluir datos sintéticos mínimos para que los seis integrantes reproduzcan el entorno.
- Registrar brevemente decisiones y validaciones relevantes realizadas con asistencia de IA.

## Flujo de Git

- Usar `main` como rama principal, sin rama `develop`.
- Trabajar en una rama por cambio, con nombres como
  `feat/carga-video`, `fix/conteo-entradas` o `docs/entorno`.
- Integrar cambios mediante un pull request breve que indique:
  qué cambió, cómo se verificó y la tarea relacionada de Azure Boards.
- Usar squash merge y eliminar la rama después de integrarla.
- Mantener el flujo simple para dos o tres desarrolladores activos.
- Incorporar CI cuando exista código, empezando por build y pruebas
  relevantes para el stack aprobado.

## Reglas de implementación

- Trabajar en incrementos pequeños y verificables, vinculados a una tarea; no ampliar alcance ni hacer refactors ajenos.
- Consultar antes de instalar dependencias nuevas; no pedir autorización reiterada para dependencias ya aprobadas.
- En TypeScript, activar `strict` y no usar `any`. En React, un componente por archivo y exports nombrados.
- Usar HTML semántico, controles nativos y etiquetas accesibles.
- En pruebas, preferir selectores por rol y nombre accesible; agregar `data-testid` solo para identificadores estables necesarios.
- Verificar cruces, duplicados, tiempos, aislamiento entre sesiones y métricas. No afirmar que algo funciona sin ejecutar pruebas; informar pruebas y limitaciones.
- No subir secretos, videos, pesos de modelos ni bases de datos a Git. No agregar servicios cloud obligatorios para el procesamiento local.
