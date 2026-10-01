# Revisión del MVP y propuesta de frontend

Fecha: 1 de octubre de 2026. Revisión asistida por IA sobre la rama `feat/frontend-shell`. Se preservaron los cambios locales existentes. No se instalaron dependencias ni se modificó la base compartida.

Seguimiento: el usuario aprobó la propuesta y se implementó en `fix/frontend-redesign`. Ver [entrega y verificación del rediseño](frontend-redesign-2026-10-01.md) para el estado posterior: 281 pruebas de frontend y 9 recorridos E2E aprobados. Los hallazgos y resultados siguientes corresponden a la auditoría inicial.

## Conclusión

El repositorio implementa los recorridos principales del MVP y tiene cobertura automática considerable. No se puede afirmar que esté completamente validado ni listo para exposición pública: falta ejecutar integración y navegador en una base local de pruebas, comprobar el recorrido con los videos reales seleccionados y preparar acceso, transporte y operación del despliegue.

## Alcance contrastado

| Requisito | Evidencia encontrada | Límite de esta revisión |
| --- | --- | --- |
| Carga y configuración visual | VideoUploadForm, SceneEditorPage, API de sesiones/escenas y migraciones | Pendiente recorrido de navegador en este equipo |
| Detección y tracking | Worker, tracker Ultralytics y pruebas de geometría/trayectorias | No se ejecutó YOLO real ni se midió precisión o rendimiento |
| Eventos y métricas comerciales | Servicios de eventos/métricas, tests y ocho métricas en resultados | Integración PostgreSQL y validación real pendientes |
| Persistencia e historial | SQLAlchemy, cinco migraciones, sesiones procesadas y pruebas de aislamiento | El entorno actual usa Azure compartido y no tiene URL local de tests seleccionada |
| Dashboard | SessionResultsPage, Recharts, filtros y hechos | Diseño poco jerarquizado; ancho fijo del gráfico |
| Chat mínimo | SessionChatPanel y servicios de chat con herramientas acotadas | No se probó una llamada real a Azure en esta revisión |
| Heatmap opcional | PositionHeatmap y muestras de posiciones | Existencia de implementación no demuestra precisión del mapa |

El README está desactualizado: presenta métricas, dashboard y chat como pendientes aunque existen sus implementaciones. La evidencia de rendimiento publicada con yolov8n no certifica el desempeño actual de yolo11m.

## Verificaciones ejecutadas

- `npm test`: 24 archivos y 273 pruebas aprobadas.
- `npm run build`: aprobado; TypeScript y Vite generan el bundle. Advertencia de JavaScript de 549,43 kB sin comprimir, 169,80 kB gzip.
- Backend, `pytest tests/unit -q -o addopts= --basetemp=.pytest-audit-20261001`: 269 aprobadas, 1 omitida, 3 errores de preparación por ausencia de una base local de pruebas; 5 subtests aprobados. Los tres errores pertenecen a `test_chat_metrics.py` y la protección rechazó usar Azure compartido.
- `npm run test:e2e`: abortó antes de migrar porque la URL seleccionada apunta a Azure compartido. No se verificó visualmente la aplicación en navegador.
- Azure Boards: consulta de solo lectura del listado de features del proyecto IA Aplicada. No se modificaron work items ni se certificaron estados de entrega.

## Hallazgos del frontend

1. AppShell solo contiene título y contexto. Falta navegación consistente, marca y un acceso claro de regreso entre etapas.
2. Resultados concentra filtros, ocho métricas, gráfico, hechos y chat en la columna lateral de Split. La jerarquía dificulta comparar cifras y consultar el análisis.
3. BarChart usa 480 × 240 fijos dentro de un contenedor de 12 rem de alto. Puede desbordar y no acompaña el ancho disponible.
4. Desde/Hasta recortan eventos y buckets visibles; la consulta de métricas no recibe ese intervalo. Debe explicarse que las cifras son de toda la sesión y que el flujo conserva buckets de un minuto.
5. Eventos muestran códigos técnicos sin traducir; las cifras necesitan unidades, formato consistente y explicación legible de indisponibilidad.
6. El estilo global apenas define fondo, colores y tipografía. Controles, foco, espacios y estados necesitan un sistema común.
7. La consulta inicial de resultados descarga el listado de sesiones procesadas para encontrar una sesión. Es una limitación de escalabilidad para una fase posterior, no un motivo para cambiar contratos durante el rediseño.

## Diseño propuesto para revisión

Mantener React/TypeScript estricto, CSS Modules, SVG y Recharts, sin dependencias nuevas. Mejorar los recorridos existentes, sin ampliar métricas ni introducir autenticación como parte del trabajo visual.

- Identidad sobria: fondo claro, superficies blancas, tinta oscura y acento azul petróleo; tipografía del sistema, bordes suaves y espaciado uniforme. Colores espaciales de zonas/líneas se conservan.
- Cáscara común con marca FlowSight, enlace a sesiones, contexto de etapa, título y navegación de regreso. Adaptación a móvil y foco de teclado visible.
- Sesiones: introducción breve, carga de video en panel claro y tablas legibles con estados consistentes y adaptación a pantallas pequeñas.
- Detalle: frame, metadatos y acciones organizadas en secciones; edición y análisis visibles junto con sus requisitos.
- Editor: lienzo principal amplio y panel de herramientas agrupadas; mensajes y guardado visibles sin alterar geometría ni reglas.
- Supervisión: preview dominante, progreso y estado legibles; cancelación y acceso al resultado según el estado existente.
- Resultados: tarjetas de métricas en un área amplia, filtros con alcance explicado, gráfico adaptable, frame/heatmap, hechos con nombres en español y chat en una sección propia. Indicar unidades, datos incompletos y estimaciones.
- Carga, error, vacío y no disponible con presentación consistente y roles accesibles.

Validación prevista: suite existente y build; Playwright para carga, configuración, procesamiento sintético, resultados y chat en PostgreSQL local; revisión visual de escritorio y móvil. Los cambios de comportamiento que aparezcan se evaluarán explícitamente y no se ocultarán como estilo.

## Preparación para alojamiento

La aplicación completa incluye API, PostgreSQL, worker y archivos locales. Publicar solo el frontend no hace accesible el procesamiento ni los videos.

- `VITE_API_BASE_URL` usa `http://127.0.0.1:8000` por defecto: en un navegador remoto señalaría la computadora del visitante.
- CORS está fijado a los dos orígenes de desarrollo del puerto 5173.
- Settings admite solamente `development` y `test`; falta definir configuración operativa de producción.
- No se encontró autenticación de usuarios ni autorización por propietario en las rutas. Aislamiento por sesión en consultas no equivale a control de acceso.
- La escritura de uploads no muestra un límite configurable de bytes; se necesita definir límites y protección de uso antes de acceso público.
- Deben resolverse HTTPS/WSS, rutas de la SPA, supervisión/reinicio de procesos, almacenamiento persistente, backups y acceso del worker a los archivos.

Primera entrega sugerida: demo con acceso protegido y backend/worker en el equipo que contiene los videos. Elegir proveedor y esquema de conectividad después de definir quién accede y dónde debe seguir ejecutándose el worker. Las opciones concretas de hosting y sus condiciones deben verificarse al elegirlas.

## Próximo paso

Revisar el diseño visual anterior y aprobarlo o ajustar su dirección. Luego implementar en una rama por cambio, conservar los archivos locales ajenos y registrar la verificación y la tarea de Azure Boards relacionada. La preparación operativa de despliegue se separa del rediseño para que tenga sus propios criterios verificables.
