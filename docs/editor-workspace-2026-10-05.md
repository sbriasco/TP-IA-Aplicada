# Editor y registro de video · 2026-10-05

Implementados por pedido visual explícito del usuario. El registro conserva las llamadas de subida, selección/creación de cámara y progreso; ofrece un modal de 920 px, dos columnas y selección por explorador o arrastre. La tarjeta de archivo permite quitar/cambiar. El usuario eligió conservar la subida sin anunciar un máximo de 500 MB.

El editor organiza el canvas y panel en proporción 70/30, con herramientas integradas en la cabecera del canvas, capas, visibilidad, propiedades y sentidos de entrada. El guardado queda fijo al pie del panel. La vista limita su altura al viewport y sólo el contenido lateral tiene scroll interno. La selección de zona se realiza desde las capas; se retiró el selector redundante «Zona en edición». En móvil se apilan y los botones del encabezado se distribuyen sin desbordar. El panel tiene scroll independiente.

Se mantienen los roles front/interior/showcase, el agrupamiento shops y las coordenadas normalizadas que recibe FastAPI. Cambiar el selector de tipo elige un área o línea existente, o inicia su dibujo; no convierte ni descarta geometría. «Elemento asociado» mueve la geometría entre zonas compatibles usando la acción ya existente. Ocultar una capa no modifica su persistencia. El título editable es una preferencia local por cámara/versión, porque el contrato de configuración no contiene nombres de versiones.

El historial en memoria conserva hasta 100 operaciones. Cada arrastre y edición de nombre se agrupa; un movimiento de cientos de eventos se deshace completo. Un guardado exitoso establece una nueva base y vacía el historial. Limpiar puntos afecta solo al dibujo en curso. Doble clic y Enter cierran polígonos; se preservan ajuste con flechas, Shift y supresión de vértices.

Tailwind 4.3.3 y su plugin Vite se incorporaron por solicitud explícita, sin preflight global. Se mantuvieron CSS Modules para el contenedor y variables de tema. No se modificaron backend, migraciones o bases por estos cambios.

La verificación incluye pruebas del contrato de guardado, visibilidad, deshacer/rehacer y arrastres largos; Playwright usa datos sintéticos y captura las vistas en ambos temas y a 390 px, sin escribir a una base.

- Suite completa: 331 pruebas aprobadas con dos workers. La primera corrida concurrente tuvo un timeout en un test ajeno al editor; al limitar la concurrencia pasó la suite completa.
- Verificación final del editor: 31 pruebas aprobadas tras los cambios de título y colores.
- Playwright: siete recorridos aprobados, incluyendo título tras recarga, guardado/reapertura, ajuste móvil, visibilidad, reversión de arrastres, modal de video y dashboard.
- Build aprobado. Continúa la advertencia previa del bundle mayor a 500 kB.
- Revisión independiente detectó historial por eventos individuales de arrastre; se agrupó por gesto y se verificó la corrección. Las capturas del editor en ambos temas y celular se inspeccionaron visualmente.

Actualización del refactor viewport (2026-10-05, asistencia de IA): build aprobado, 331/331 pruebas unitarias aprobadas y recorrido Playwright del editor aprobado con Chrome instalado. Se verificó ausencia de scroll de página a 1366×768 y 1920×1080, toolbar fuera del frame, guardado visible, arrastre/deshacer/rehacer, sentidos y payload compatible. Se inspeccionó la captura de escritorio. Continúa la advertencia de tamaño del bundle.

Corrección visual solicitada por el usuario (2026-10-05): se retiraron los botones de la toolbar, el texto Editor del header y los colores particulares del guardado. Volver a la sesión comparte el estilo de Continuar a resultados; el editor utiliza los tokens de la página principal en ambos temas.

Verificación previa al commit del conjunto de cambios del 2026-10-05 (asistencia de IA): build y Ruff aprobados; 331 pruebas frontend y siete recorridos Playwright aprobados. Backend: 57 pruebas relacionadas con webcam, estadías, esquema, worker y resultados aprobaron en ejecución secuencial contra PostgreSQL local. La suite completa de backend se interrumpió por duración; una primera ejecución focalizada tuvo interferencia de dos corridas sobre la misma base y se repitió secuencialmente con éxito. Se recuperó la creación de áreas en un desplegable lateral y la continuación vuelve a preparación según el tipo de fuente, sin toolbar. Se conserva la advertencia de tamaño del bundle.

Actualización de colores (2026-10-06, asistencia de IA): paleta compartida entre lienzo, indicadores de capas y previsualización; externa azul, interior verde, interés naranja y línea violeta. Se conservan los trazos por rol. Build aprobado y recorrido Playwright del editor aprobado (guardado, capas, arrastre, ambos temas y móvil); captura oscura inspeccionada. Continúa la advertencia previa del bundle mayor a 500 kB.

Corrección de navegación (2026-10-06, asistencia de IA): Continuar a resultados consulta /processed-sessions y abre resultados de video completos o el resultado del trabajo webcam finalizado; sin resultados vuelve a preparación. Una consulta fallida permite reintentar y no impide editar. Se mantiene el bloqueo por cambios sin guardar. Verificación: 20 pruebas de SceneEditorPage y recorrido Playwright aprobados (destino con/sin resultados y clic a resultados).

Guardado sin cambios (2026-10-06, asistencia de IA): el editor compara los datos persistibles actuales con el último guardado; deshabilita y protege el guardado sin diferencias, incluso tras restaurar una edición. El título local y la visibilidad no crean versiones. La navegación y el aviso de salida usan la misma comparación. Verificación: 21 pruebas del editor, build y recorrido Playwright aprobados; se comprobó cero guardados al abrir/restaurar el nombre y un único guardado tras cambios reales.

Confirmación de encuadre webcam (2026-10-06, asistencia de IA): fila completa clickeable con checkbox nativo de 20 px, texto de 14 px, borde redondeado, foco visible y fondo de acento al confirmar. Verificación TypeScript y recorrido Playwright de preparación aprobados; captura de escritorio inspeccionada y comprobación móvil sin desborde.

Etiquetas webcam (2026-10-07, asistencia de IA): SceneEditorPage transmite live_source.label_mode al lienzo y a los controles de línea. En access se muestran Entrada/Salida sobre los lados, respetando entry_direction, y un control para invertir ambos sentidos; directions conserva A/B. No se modifican métricas ni contratos. Se constató por lectura de API que la sesión local Conferencia fue persistida como directions. Los resultados y frames ya respetan el modo persistido. Verificación: 59 pruebas frontend, build y dos recorridos Playwright aprobados, incluyendo selección access y payload de preparación, editor, consola y reporte con entrada B a A, eventos y tabla por minuto. Datos sintéticos; no se modificaron sesiones existentes.
