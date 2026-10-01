# Rediseño de FlowSight

Fecha: 1 de octubre de 2026. Rama: `fix/frontend-redesign`.

## Entrega

Diseño aprobado por el usuario: interfaz clara y sobria con acento azul petróleo. Se mantiene React, TypeScript estricto, CSS Modules, SVG y Recharts, sin dependencias nuevas.

- Cáscara común con marca, navegación a sesiones, etapas de la sesión, acceso al contenido por teclado y estados de foco.
- Carga organizada por archivo, nombre y cámara; tablas con scroll propio en móvil y estados de análisis legibles.
- Detalle con frame amplio, información del video y acciones agrupadas. El inicio de análisis lleva a supervisión y ya no dice que el procesamiento está pendiente de implementar.
- Editor con herramientas agrupadas y frame visible durante el scroll de escritorio. Mantiene geometría, teclado, validaciones, versiones y aviso de cambios sin guardar.
- Supervisión con placeholder, preview adaptable, progreso y acceso a resultados al completar.
- Dashboard con ocho tarjetas, unidades y razones de indisponibilidad, gráfico adaptable, versión de escena utilizada, hechos en español, muestra de posiciones y chat separado.
- Aclaraciones de alcance: los indicadores son de toda la sesión; el gráfico conserva conteos de los intervalos que se superponen al tramo. Los hechos sí se filtran por timestamp. Un track no representa identidad real ni persona única.
- Las sesiones sintéticas completadas sin escena muestran que no tienen indicadores comerciales, evitando una carga indefinida.
- Recharts se carga mediante importación dinámica cuando se necesita el gráfico. Bundle inicial de JavaScript: 260,87 kB / 81,82 kB gzip, frente a 549,43 kB / 169,80 kB gzip antes del rediseño. El chunk de gráficos se descarga por separado (366,27 kB / 107,35 kB gzip); estos tamaños no son una medición de tiempo de carga.

## Verificación

- `npm test`: 281 pruebas aprobadas en 26 archivos.
- `npm run build`: TypeScript y Vite aprobados, sin advertencia de chunk mayor a 500 kB.
- Playwright: los 9 recorridos existentes aprobados usando API, frontend, worker fake y PostgreSQL de pruebas aislados. Incluye carga, dibujo/edición/guardado de escenas, validación, historial/resultados, chat, preview/WebSocket y cancelación. El chat usa redactor de prueba y no llama al modelo real.
- Inspección visual de sesiones y resultados en escritorio; revisión de sesiones, detalle, editor, supervisión y resultados a 390 px, sin desbordamiento horizontal de página. Capturas locales en `.verification/frontend-redesign/` (no versionadas; escenas y datos de pruebas).
- Revisión adicional de código asistida por IA: se corrigieron el texto de intervalos y el estado de resultados sintéticos.
- `ruff check backend`: aprobado; la herramienta emite avisos de acceso denegado a directorios temporales preexistentes.
- Suite completa de backend: 429 aprobadas, 1 omitida por permisos POSIX en Windows, 1 prueba GPU excluida y 1 fallida: `test_reports_ready_environment_without_exposing_database_url`. El script `check-environment.ps1` lee el `.env` del equipo, cuya base no respondió; no adopta la URL temporal exportada para la suite. No se modificó ese archivo ni se oculta el fallo. Contratos, migraciones, aislamiento, worker y pruebas de configuración CORS quedaron aprobados en la base temporal.

Un intento inicial de E2E se interrumpió al detectar puertos ocupados. El runner ahora comprueba la disponibilidad antes de migrar o iniciar y usa `--strictPort`: aborta en lugar de reutilizar servicios existentes. Ese intento no se usa como evidencia de aprobación.

## Pruebas con puertos separados

El runner mantiene 8000/5173 por defecto, pero permite seleccionar puertos libres:

```powershell
$env:FLOWSIGHT_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:PORT/TEST_DB'
$env:FLOWSIGHT_E2E_API_PORT = '18003'
$env:FLOWSIGHT_E2E_FRONTEND_PORT = '15175'
npm run test:e2e
```

Usar una base local exclusiva para tests: la suite puede borrar/recrear tablas. El runner fija el detector fake, redactor ficticio, carpeta temporal de videos, origen CORS y URL de API del frontend. Los valores de ejemplo anteriores requieren una base de pruebas preparada; no crean ni configuran un servicio por sí solos.

## Conexión a un frontend alojado

`FLOWSIGHT_CORS_ORIGINS` admite una lista JSON de orígenes exactos del frontend. Sus valores por defecto siguen siendo los dos orígenes locales de desarrollo. Configurar `VITE_API_BASE_URL` al generar el build y permitir ese origen en la API.

Esto no constituye un despliegue público. Quedan por definir autenticación y autorización, HTTPS/WSS, rutas de SPA, conectividad con el worker local, límites de subida, almacenamiento y operación. No se publicaron servicios ni se contrataron proveedores.

## Trazabilidad

El feedback posterior del usuario se implementó en la [revisión de flujo compacto y agente](frontend-compacto-2026-10-01.md), que documenta la interfaz actual, eliminación lógica, pruebas adicionales y corrección del chat real de Azure. Los conteos anteriores corresponden a esta primera iteración.

Cambio solicitado y diseño aprobado en esta conversación. Se consultó Azure Boards en modo de lectura durante la auditoría; no se crearon ni modificaron tareas. Queda vincular este incremento con la tarea concreta del equipo al preparar el PR. Los archivos locales previos ajenos al cambio se preservaron.
