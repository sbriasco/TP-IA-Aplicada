# Recorridos de interfaz

Un componente por archivo, exports nombrados, TypeScript strict sin any, CSS Modules, HTML semántico y etiquetas accesibles. Rutas nuevas en `frontend/src/navigation.ts`; mantener recorridos de archivos.

## Preparación

En «Nuevo análisis», elegir «Video» (actual) o «Webcam en vivo». `WebcamPreparationForm` elige cámara lógica registrada, candidato de dispositivo local, nombre y etiqueta de sentidos: «Direcciones A/B» o «Entrada/salida de un acceso». Texto: «La webcam debe estar conectada a la PC que ejecuta el procesamiento».

Preparar llama POST live/sessions y navega `/sessions/{id}/live/prepare`. Muestra frame de referencia y acceso al editor existente. Guardar escena conserva versión/locales/validaciones. Si API/worker no están configurados o dispositivo falla, error accionable y ningún job activo. Cambiar candidato exige nueva preparación, no mutar escena guardada.

Antes de empezar, pedir check transitorio, dibujar la configuración seleccionada encima y exigir checkbox «El encuadre coincide con esta configuración». Botón «Iniciar análisis en vivo» habilitado solo con check vigente≤60 s y escena de la misma cámara/proporción válida. Sin confirmar no inferir automáticamente equivalencia de dispositivos. Abandonar libera webcam; sesión queda preparada, sin estadísticas.

## Vivo

`/sessions/{id}/live` resuelve su único live job. `LiveAnalysisPage` usa Split: imagen analizada+recuadros+IDs temporales+zonas/línea a un lado; tarjetas por sentido/total y CrossingChart al costado. Selector de local; total pertenece a la línea seleccionada, no visitantes únicos. «Cruces por minuto», no «Flujo de visitas». Caption: «Resultados parciales del sector observado».

Barra de estado: conectada/interrumpida/requiere confirmación/finalizando, tiempo de captura, antigüedad de imagen y diagnóstico FPS/latencia. No mostrar esos parámetros en el recorrido de configuración como decisiones técnicas del usuario. Imagen y cifras se aplican juntas después de validar el payload y revision; descartar job/session ajenos y revisiones antiguas. No sumar increments por mensajes.

Chart renderiza últimos60 buckets y distingue minuto abierto, cobertura incompleta y candidato pendiente. Minuto previo puede corregirse al confirmar cruce. Sin datos no dibujar valores inventados; gap de cámara no es cero tránsito. Historial permite consultar toda la serie paginada.

«Detener» pide202 y permanece visible durante interrupción; después muestra «Finalizando» y desactiva duplicados. No cambia la sesión a completada optimísticamente ni usa Cancel del archivo. Si demora>10 s, aviso «El análisis está finalizando; todavía no hay resultado final» y posibilidad de consultar estado, sin disparar reinicio. Estado terminal navega resultados.

Perder socket no llama stop; muestra conexión perdida/último instante, intenta1/2/5 s y consulta snapshot. Refrescar o volver a la página retoma observación de mismo job. Tras pérdida de cámara, imagen transitoria recuperada permite confirmar encuadre: «El dispositivo y el encuadre siguen siendo los mismos». Si no coincide, finalizar y preparar nueva sesión; no reusar silenciosamente tracks.

## Historial/resultados

Sesión webcam aparece con origen «Webcam» y «Sin grabación». Activa abre live; preparada abre prepare; terminal abre `/sessions/{id}/results`, cuyo dispatcher de origen carga `LiveResultsPage`. Archivo continúa en SessionResultsPage actual.

Resultados webcam: configuración sobre frame, duración hasta fin/checkpoint, conteos por sentido, total, cruces por minuto, interrupciones/cobertura y hechos confirmados. Mapa de toda la sesión con PositionHeatmap y ≤2000 puntos sobre frame de referencia; texto «Muestra de posiciones observadas», sample_count/capacidad y limitaciones. Si no hay muestra válida, vacío explicado. No reproductor, reupload, reanálisis de archivo, comerciales ni panel de chat webcam.

Una sesión completada con interrupciones muestra cierre correcto y aviso de cobertura incompleta. Fallida conserva valores parciales y unknown_tail; no usar tiempo operativo como duración observada. Frame sigue disponible por reglas de referencia de escena incluso tras retirar sesión. Retiradas no salen en listado público.

## Pruebas de aceptación UI

Playwright con fake: seleccionar → preparar → editor → guardar → check/confirmar → vivo → cruces → desconexión → retry/confirmar → stop → historial/mapa. Usar getByRole/getByLabel, no selectores frágiles. Reload, socket lento, minuto corregido, datos fuera de orden, segundo start en equipo ocupado y dos sesiones aisladas. Mantener recorridos existentes de carga, cancelación, métricas y chat de archivo.
