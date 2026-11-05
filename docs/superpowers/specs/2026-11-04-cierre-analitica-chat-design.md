# Cierre de analítica y chat conversacional

Pedido del usuario: corregir los hallazgos de la revisión y priorizar un chat ampliado que
responda desde un saludo hasta una consulta completa dentro de FlowSight. Los ensayos físicos
y la demo quedan para después. Este documento concreta ese alcance ya autorizado.

## Diseño

Se conserva React/FastAPI, Azure Foundry y el SDK instalado. No se agregan dependencias.
El asistente puede conversar, explicar el uso y los límites de FlowSight, interpretar los
resultados guardados y comparar sesiones compatibles. El historial orienta las repreguntas;
las cifras se vuelven a leer en cada turno. Las herramientas son de lectura y tienen alcance
acotado: nunca SQL libre, ejecución de acciones, identificación real ni confirmación de ventas.

Se amplía el servicio actual y su contexto de producto. Se descarta un chatbot genérico sin
herramientas porque perdería el respaldo de cifras, y una lista cerrada de frases porque no
cubre lenguaje natural. Un saludo o una explicación no exigen una zona ni métricas completas.
Las preguntas analíticas sin alcance suficiente deben pedir una aclaración útil y mostrar las
opciones existentes. Las respuestas pueden tener el detalle necesario para la pregunta.

Las métricas de archivo y webcam conservan sus fuentes y sus diferencias. Se amplía la lectura
de funnel/flujo y la presentación de porcentajes sin delegar cálculos de métricas al modelo.
Los nombres de escenas/sesiones son datos no confiables, nunca instrucciones. Se conservan
el límite de llamadas al modelo, el timeout, el aislamiento de sesiones y la validación de cifras.

Se corrigen además: interferencia de bolsas con ByteTrack; continuidad de permanencias tras
un hueco mayor a un segundo; truncamiento de grupos a doce candidatos; errores al refrescar
historial de chat; expectativas obsoletas de pruebas; cobertura UI en CI y documentación.

## Aceptación

- Saludos, agradecimientos, ayuda de uso, límites y consultas mixtas reciben respuestas pertinentes.
- Tráfico, ingresos, permanencias, funnel, grupos, posible compra, webcam y comparaciones citan
  datos del alcance correcto; los faltantes no se convierten en cero ni se inventan.
- Repreguntas conservan el contexto del hilo y vuelven a consultar los datos.
- No se rompen los contratos existentes; la UI permite conversar aunque no haya zona elegida.
- Regresiones reproducibles para los defectos de visión y el refresco del historial.
- Build, Ruff, pytest, Vitest y ambos recorridos Playwright pasan.
- Se verifica y actualiza el esquema configurado con el script oficial conservando los datos.

No se promete precisión ni rendimiento físico: esos ensayos continúan pendientes.
