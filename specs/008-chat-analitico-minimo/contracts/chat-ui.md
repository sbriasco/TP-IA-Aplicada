# Panel de chat

Está en la pantalla de resultados de la sesión abierta. No reemplaza los indicadores ni el historial.

## Envío

- El campo de la pregunta tiene una etiqueta visible. El envío es un botón con nombre accesible.
- Al enviar, el panel muestra espera y no pinta una respuesta vacía como si ya estuviera lista.
- El pedido lleva la sesión de la página y el local elegido. Si no hay local elegido, `shop_id` va vacío.

## Respuesta

| Estado | Qué se ve |
|---|---|
| `answered` | El texto, el local, que es toda la sesión, y los valores usados con su rótulo |
| `refused` | El rechazo. Sin cifras |
| `needs_clarification` | La pregunta del chat. Sin cifras y sin elegir una sesión o un local solo |
| `unavailable` | Que no hay resultado final. Si hay motivo de falla o cancelación, se puede mostrar. Sin las cinco cifras y sin las tres parciales |
| `error` | Un mensaje claro. Los indicadores de la página siguen |

Los rótulos visibles son los del tablero: «estimación de visitas», «visible», «observable» y «no disponible». El pico se lee en segundos del video.

## Sesión

- Mientras la pregunta no nombre otra, las cifras son de la sesión abierta.
- Al abrir otra sesión, el panel queda vacío. No se muestra el hilo anterior.
- «La última» y un nombre se distinguen en el texto de la respuesta por la sesión que quedó elegida, no por cambiar de página.
