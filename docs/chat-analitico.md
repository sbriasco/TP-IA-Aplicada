# Chat de FlowSight

Esta guía describe el asistente actualizado el 5 de noviembre de 2026. La evidencia de la versión anterior está en la [validación del 1 de octubre](chat-validacion-2026-10-01.md).

El asistente conversa sobre FlowSight, explica cómo usar la aplicación e interpreta resultados guardados. Se puede saludar o pedir ayuda sin elegir una zona de análisis ni disponer de métricas. Para consultar cifras necesita resolver la sesión y la zona; si la pregunta resulta ambigua, solicita una aclaración con el contexto disponible.

## Datos y alcance

| Fuente | Datos disponibles para el chat |
| --- | --- |
| Archivo completado | Métricas de la zona, flujo temporal y pico, etapas y conversiones del funnel; patrones, grupos y posible compra estimados de toda la sesión. Solo se citan los informes que estén guardados. |
| Comparación de archivos | Cifras y diferencias calculadas por el backend entre sesiones elegibles, con insights deterministas. Los valores faltantes no producen diferencias ficticias. |
| Webcam con trabajo terminado | Reporte guardado de cruces, entradas/salidas, estadía por zona, duración de captura, minutos e interrupciones/cobertura. No incluye funnel, grupos ni posible compra. |

Los indicadores corresponden a toda la sesión. Cambiar el tramo de un gráfico no recalcula las métricas del chat. Los patrones, grupos y posible compra son de toda la sesión y no se atribuyen exclusivamente a la zona seleccionada. Un informe ausente se explica como no disponible; no se sustituye por cero ni se inventa el motivo de su ausencia.

El contexto enviado al modelo contiene como máximo cien elementos por lista, por ejemplo intervalos, secuencias, grupos o interrupciones. Conserva los totales conocidos y señala el recorte. En listas paginadas puede desconocerse el total. La respuesta debe avisar cuando usa una lista parcial.

## Conversación e historial

Las conversaciones y sus mensajes se guardan en PostgreSQL, vinculados a la sesión. Se pueden abrir hilos anteriores o iniciar uno nuevo. Hasta veinte mensajes recientes orientan las repreguntas. Cada consulta analítica vuelve a leer los datos de la sesión y zona resueltas. Al repreguntar sobre un contraste se conservan las sesiones y el eje que se usaron en el turno anterior.

Al cambiar de sesión o zona, el panel conserva el aislamiento de sus conversaciones. La respuesta identifica su contexto para permitir contrastarla con Resultados. Si falla la actualización del listado de hilos después de responder, la respuesta sigue visible y se informa el problema de historial.

Ejemplos de consultas:

- `Hola, ¿qué puedo consultar acá?`
- `¿Cómo preparo un análisis de webcam?`
- `¿Por qué la ocupación es visible y no total?`
- `¿Cuál fue el tráfico y cuántos ingresos hubo en esta zona?`
- `¿Y la permanencia media?`
- `Resumí el funnel y explicá sus conversiones disponibles.`
- `¿Qué patrones y grupos estimados quedaron guardados en esta sesión?`
- `¿Qué significa posible compra? ¿Por qué no confirma una venta?`
- `Compará esta sesión con [nombre de otra sesión completada] para [zona].`
- En un reporte de webcam: `¿Cuántos cruces hubo y qué cobertura tuvo el análisis?`

Los nombres corresponden a sesiones y zonas existentes. Si varias coinciden o faltan datos para comparar, el asistente debe pedir precisión o explicar qué falta.

## Herramientas y límites

Credenciales y llamadas a Azure AI Foundry permanecen en el backend. Se mantiene el deployment configurado, el cliente `openai==1.109.1`, un máximo de dos llamadas al modelo por turno, `max_completion_tokens=2048` y `reasoning_effort=low`. Un saludo o ayuda puede terminar en una llamada. Para responder con cifras, la primera llamada debe consultar la herramienta acotada de analytics; la segunda finaliza sin nuevas herramientas.

El modelo interpreta los resultados que el backend entrega. No analiza el video, ejecuta SQL libre ni realiza acciones sobre cámaras, configuraciones, sesiones o trabajos. Puede explicar estas operaciones para que el usuario las realice. Pedir una explicación de los límites no equivale a pedir identificación de personas o confirmación de compras.

Un `track_id` representa seguimiento temporal de una sesión/cámara, no identidad real ni persona única. La ocupación es visible; la permanencia es observable y pierde continuidad ante los cortes definidos por el análisis. La cobertura incompleta de webcam no equivale a cero personas. Atención, grupos y posible compra son estimaciones, y una bolsa no demuestra una venta. No hay seguimiento entre cámaras ni reconocimiento facial.

Las guardas verifican el alcance y las cifras admitidas, incluidos decimales y porcentajes respaldados. No prueban que toda frase del modelo interprete correctamente una métrica. Ante una respuesta dudosa, contrastar las cifras y el contexto con el dashboard.

## Verificación y pendientes

La suite automática usa un redactor de prueba o respuestas simuladas para verificar herramientas, límites de llamadas, errores, contexto, datos incompletos y navegación. Los recorridos Playwright integrados y de UI se ejecutan en CI. Esa cobertura no acredita calidad sostenida, cuotas ni disponibilidad de Azure.

El 5 de noviembre se probaron conversaciones reales con Foundry y resultados sintéticos en PostgreSQL local. El asistente saludó, explicó cómo configurar zonas y distinguió tráfico de entradas. Citó el tráfico guardado, explicó que la permanencia faltaba e interpretó el horario pico en una repregunta. También explicó los límites de posible compra y redirigió un pedido ajeno a FlowSight. Las respuestas usaron una o dos llamadas por turno.

Los ensayos físicos de webcam y los contrastes manuales con videos continúan pendientes.

El cierre se realizó con asistencia de IA. La base compartida se actualizó de `0013_scene_display_name` a `0017_chat_threads_v2`. Se comprobó la conservación de los conteos de cámaras, sesiones, configuraciones, trabajos, métricas y eventos.
