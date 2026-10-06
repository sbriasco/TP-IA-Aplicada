# Dashboard: temas e historial · 2026-10-05

Por pedido del usuario se aplicó el diseño de referencia a la pantalla inicial: navegación compacta con selector de tema, acciones con iconos, guía de tres pasos en tarjetas y tabla con búsqueda, filtros y estados diferenciados. La guía de estados del pie se retiró por pedido posterior.

El modo oscuro usa fondo `#14181b`, superficies `#1d1e22`, cabecera de tabla `#272b2e` y acción principal `#16686e`, ajustados a muestras de la imagen provista. La versión clara usa superficies blancas y grises neutros. El logo de FlowSight conserva su SVG con las tres barras; los controles y pasos usan Lucide React `1.52.0`, instalado por solicitud explícita y fijado en el lockfile. CSS Modules se mantiene: no se instaló Tailwind ni se agregaron fuentes externas.

El tema se inicia con la preferencia guardada o la del dispositivo y se guarda con la clave `flowsight-theme`. Se aplica antes de montar la app. Si el almacenamiento está bloqueado, el selector sigue funcionando durante la visita. El avatar es neutro: no representa un usuario autenticado.

La búsqueda compara nombres de análisis y cámaras; se combina con filtros Todos, Activos y Completados. Activos incluye trabajos pendientes/procesando; Completados incluye trabajos finalizados, y los resultados incompletos conservan su etiqueta. Los accesos de onboarding abren la carga, el editor de la sesión reciente y los resultados disponibles. La baja lógica requiere la confirmación existente y sigue bloqueada durante trabajos activos.

La duración proviene del tiempo de captura persistido de webcam. El endpoint de historial todavía no informa duración analizada de archivos; se muestra «Sin datos» cuando falta. No se usa duración de procesamiento como duración del análisis ni se realizan consultas adicionales por fila.

## Validación

- Suite completa del frontend: 326 pruebas aprobadas. Las dos nuevas pruebas de tema y búsqueda/filtros fallaron antes de implementarlos y pasaron después.
- Verificación final de header, tema, dashboard y trabajos: 19 pruebas aprobadas. Se ajustaron selectores de pruebas para distinguir controles del trabajo y selector de tema del header.
- Playwright: cinco recorridos aprobados. Incluye temas claro/oscuro, persistencia tras recarga, búsqueda/filtros, estados activos, modales de carga/cámaras y ausencia de desbordamiento de página a 390 px. La tabla móvil permite desplazamiento dentro de su sección.
- Las capturas `dashboard-light.png`, `dashboard-dark.png`, `dashboard-mobile-light.png` y `dashboard-mobile-dark.png` en `frontend/test-results` se inspeccionaron visualmente. Los datos de esas capturas son sintéticos; la app conserva las APIs reales.
- Compilación aprobada. Persiste la advertencia previa de bundle mayor a 500 kB; el cambio no incorpora un refactor de carga ajeno al pedido.
- Revisión independiente detectó bajo contraste de botones claros y fondos blancos en vistas compartidas bajo tema oscuro. Se corrigieron los pares de color y los fondos; los botones oscuros usan un hover más oscuro con texto blanco. La comprobación móvil de Recharts espera a que termine el redimensionamiento antes de medir el ancho.

No se modificaron tablas, migraciones ni datos compartidos por este rediseño.

### Preparación en vivo: layout ajustado al viewport

Se ajustó la preparación de una sesión webcam a la altura disponible bajo la barra de 64 px, con monitor y panel en proporción 65/35 en escritorio. El frame usa object-fit: contain; refrescar reutiliza la comprobación existente y se conserva la confirmación obligatoria y su expiración. La paleta Slate/Teal queda acotada a esta vista. El resumen usa shop_count (zonas de análisis), porque el listado de versiones no informa cantidades de polígonos ni líneas. En pantallas angostas se apilan monitor y controles.

Validación asistida por IA: TypeScript sin errores, cinco pruebas unitarias de preparación y recorrido Playwright en Chrome con modo oscuro, alturas 640/720/768 a 1366 px de ancho, captura/confirmación y vista móvil. No se cambiaron endpoints ni se probó hardware webcam real en esta validación.
