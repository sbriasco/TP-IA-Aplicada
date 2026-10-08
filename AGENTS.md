# FlowSight

## Contexto del producto

Actualización de vocabulario del producto (2026-10-05, indicada por el usuario): la interfaz usa zonas de análisis, no locales comerciales. Cada zona de análisis agrupa áreas externas, interiores o de interés y sus líneas de acceso. Los identificadores históricos `shops`, `shop_id`, `front`, `interior` y `showcase` se conservan en contratos y persistencia para mantener compatibilidad con escenas existentes; esto no modifica los criterios de medición.

FlowSight es una plataforma de analítica de espacios comerciales para el Grupo 6, seis estudiantes de Ingeniería en Informática. El MVP vence el 2 de octubre de 2026 y la versión final el 13 de noviembre de 2026.

El usuario carga un video de una cámara fija y configura la escena sobre un frame: polígonos de interés, líneas de entrada/salida y locales identificados manualmente. El sistema procesa el video y sincroniza detecciones, `track_id` temporales, zonas y eventos con los timestamps de los frames analizados; luego ofrece un dashboard y consultas sobre resultados actuales o históricos. El procesamiento es local. La PC de referencia tiene Windows y una RTX 5080 de 16 GB de VRAM, pero no se debe asumir esa GPU en todos los equipos ni prometer velocidad de video en tiempo real antes de medirla.

## Alcance

### MVP

- Carga de videos y configuración visual de locales, zonas y líneas.
- Detección de personas y tracking por video.
- Tráfico, flujo temporal, paso frente a locales, entradas/salidas, permanencia y ocupación observable, tasa de ingreso y horarios pico.
- Persistencia en PostgreSQL de sesiones, configuración, eventos y métricas (local para desarrollo/tests; Azure Flexible Server opcional para integración/demo — ver decisiones técnicas).
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
- La conexión local de webcam se inicializa automáticamente por API y worker; no exigir configurar identificador o token en `.env` para listar dispositivos. Los valores explícitos siguen siendo overrides opcionales. La credencial generada vive en `.tools/runtime/webcam.json`, fuera de Git.
- Un `track_id` es temporal y pertenece a una sesión/cámara: no representa una identidad real ni garantiza una persona única.
- Medir tiempos con timestamps del video en archivos y timestamps de captura relativos al inicio analítico en fuentes en vivo, no con el tiempo de procesamiento. Descartar frames no comprime el tiempo observado; una interrupción no demuestra continuidad de un track.
- Debe existir persistencia y aislamiento por sesión; versionar migraciones, configuración de ejemplo e instrucciones.
- Eliminar una sesión del historial es una baja lógica (`deleted_at`): se conservan archivos y referencias de escenas inmutables; los trabajos activos bloquean la baja. Los endpoints públicos omiten las sesiones retiradas, excepto el frame que sigue siendo referencia de una escena guardada.
- Eliminar una cámara es una baja lógica (`cameras.deleted_at`): sale del selector para videos nuevos, conserva sus sesiones y escenas, y no admite nuevos trabajos. Los trabajos activos bloquean su baja. Se conserva la unicidad de sus nombres, incluidos los retirados. Ver la migración `0007_camera_management` y las decisiones técnicas.
- Eliminar una configuración la retira del selector mediante `scene_version_removals` (migración `0008_scene_configuration_removal`); no modifica ni borra la escena inmutable. Los análisis históricos conservan su acceso, los trabajos activos bloquean la baja y no se admiten nuevos trabajos con ella. No reutilizar números de configuraciones retiradas.

## Stack acordado

- Frontend: React, TypeScript con `strict` y Vite; CSS Modules y variables CSS para estilos/temas, SVG sobre el frame para el editor visual y Recharts para gráficos. Tailwind CSS 4.3.3 con su plugin de Vite, sin preflight global, para el editor de escenas (pedido explícito del usuario el 2026-10-05). Lucide React para iconografía de interfaz; el isotipo propio de FlowSight conserva su SVG.
- Backend: Python, FastAPI y Pydantic. Worker Python separado para visión, en el mismo repositorio.
- Datos: PostgreSQL (SQLAlchemy + Alembic). **Local** por integrante para desarrollo aislado, tests y CI; **Azure Database for PostgreSQL – Flexible Server** para integración/demo compartida. Selección solo vía `FLOWSIGHT_DATABASE_URL`. Videos y archivos derivados en disco local. El worker de visión permanece local.
- Visión: Ultralytics YOLO, PyTorch y OpenCV; ByteTrack como punto de partida sujeto a evaluación.
- Comunicación: REST para carga, configuración y consultas; WebSocket para avances y previsualización sincronizada. Validar el transporte de frames antes de comprometer rendimiento.
- Chat: Azure AI Foundry (suscripción de estudiantes), consumida desde el backend mediante herramientas acotadas de analytics; validado en Feature #5 con `openai==1.109.1` y deployment `gpt-5-mini` (tool calling demostrado; cuotas `not_measured`).
- Entorno: Python con `venv` y `pip`, Node.js con `npm`. PostgreSQL local para tests/CI; instancia Azure Flexible Server opcional para trabajo integrado. Un worker y trabajos persistidos en PostgreSQL inicialmente.
- Calidad: pytest y Playwright; GitHub Actions para CI cuando exista código.
- Fijar versiones en los archivos de dependencias y lockfiles al preparar el entorno. Elegir tecnologías no autoriza su instalación en esta etapa.

Consultar [Decisiones técnicas](docs/decisiones-tecnicas.md) para los motivos, límites y validaciones pendientes. Mantener ambos documentos alineados al cambiar una decisión.

## Reglas de medición

- Evitar eventos duplicados por oscilaciones en líneas y bordes. Un cruce se confirma al pasar 1/3 s sin el sentido contrario; en video ese plazo usa el tiempo del archivo (a 30 fps equivale a los 10 frames anteriores). Un pie dentro de la franja de 0,004 normalizada conserva el último lado válido. En video, el mismo `track_id` no une posiciones ni confirma un cruce pendiente si reaparece después de más de 1 s.
- Distinguir ocupación visible de ocupación total de un local.
- No inferir permanencia dentro de un comercio si se pierde el seguimiento.
- En webcam, la estadía promedio por zona usa visitas observadas de duración positiva, incluidas las visitas en curso; una pérdida de track, cambio de segmento o intervalo mayor a un segundo corta la continuidad. Se guarda con el checkpoint (migración `0011_live_zone_dwell`).
- La pausa manual de webcam cierra captura e inferencia sin terminar el job; conserva sus métricas y reserva el worker/modelo. Retomar exige un encuadre nuevo confirmado y segmento nuevo sin vincular tracks anteriores. El intervalo `operator_pause` no suma estadía ni observaciones; forma parte de la duración conocida y de la cobertura incompleta (migración `0012_live_manual_pause`).
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
- Trabajar en una rama por cambio. Las features de Spec Kit usan
  `feature/NNN-slug` (ej. `feature/004-carga-video`), creada por
  `/speckit-specify` con el número de su carpeta en `specs/`. Otros cambios
  usan el tipo como prefijo: `fix/conteo-entradas`, `docs/entorno`, `chore/...`.
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
- No subir secretos, videos, pesos de modelos ni bases de datos a Git. No agregar servicios cloud obligatorios para el **procesamiento** local de video; la persistencia compartida en Azure PostgreSQL es opcional y se selecciona por configuración.
