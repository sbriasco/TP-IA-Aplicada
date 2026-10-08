# Preparación de análisis de video — 2026-10-06

Refactorización visual solicitada por el usuario, realizada con asistencia de IA: grid responsive 7/5, preview con configuración activa y una consola única. Selector de configuraciones sincronizado con polígonos, resumen de zonas, CTA teal y metadatos cerrados por defecto. La re-vinculación abre el selector nativo y carga el archivo conservando el endpoint y la validación del hash. La eliminación de la configuración seleccionada conserva su confirmación y endpoint.

El resumen muestra Worker local: la API de esta pantalla no informa el dispositivo efectivo y no se presume GPU. Los contratos y la arquitectura del worker no cambian. No se agregan dependencias.

Verificación: pruebas de sesión y errores de API, Playwright con respuestas sintéticas para selección, filechooser, creación del trabajo y geometría en escritorio/móvil, y build de producción. Estas pruebas no miden rendimiento ni ejecutan inferencia real.

Resultados: 332 pruebas en 36 archivos aprobadas con `npm --prefix frontend test -- --maxWorkers=2`; recorrido Playwright aprobado en 390, 1024, 1280, 1440 y 1920 px; build aprobado (advertencia de chunk mayor a 500 kB). La ejecución inicial con concurrencia por defecto tuvo un timeout en la prueba de SessionResultsPage «el panel viaja con la sesión y el local, y se vacía al cambiar de sesión»; pasó aislada y en la suite con dos workers.
Corrección de paleta solicitada por el usuario: se retiraron los colores Slate/Teal fijos y la sobrescritura de tokens sobre body. La pantalla usa los tokens globales de FlowSight, incluido el CTA y los estados. Playwright verifica colores del tema oscuro original y cambio a tema claro, además del recorrido existente.

Mejora del selector solicitada por el usuario: desplegable propio con filas de dos líneas, badge Más reciente, selección marcada y tokens globales. Lista en portal para evitar recortes de la consola, con posicionamiento adaptado al espacio disponible; soporte de flechas, Home/End, Enter/Espacio, Escape, Tab y cierre al pulsar fuera. Verificado mediante 333 pruebas y Playwright en ambos temas y móvil, incluyendo selección por teclado y recuperación ante error de zonas.
