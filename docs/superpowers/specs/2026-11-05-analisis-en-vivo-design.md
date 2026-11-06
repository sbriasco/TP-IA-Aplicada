# Análisis de video dentro de la cámara en vivo

Pedido del usuario (2026-11-05): usar en la cámara en vivo todo el análisis
que ya se hace sobre un video, verlo mientras corre y, al terminar, abrir la
misma pantalla de resultados. Aprobó reutilizar los calculadores del video.

## Diseño

Cada frame analizado de la cámara entra a los mismos contadores que un video:
indicadores, funnel, grupos y posible compra. La cámara sigue confirmando los
cruces como hoy. Esos cruces confirmados son las entradas y las salidas. La
posible compra también detecta bolsas en esos frames.

El reloj es el tiempo de captura desde el inicio analítico. Un segundo de
captura equivale a un segundo de esos contadores. Descartar un frame no
comprime el tiempo. El salto de un frame del análisis de archivo no se aplica
a la cámara.

Mientras la cámara corre, la vista en vivo muestra el avance de los
indicadores, el funnel, la cantidad de grupos y la posible compra, junto con
lo que ya muestra. Alguien que sigue en el frente no es paso ni entrada hasta
que sale o cruza. La tasa de ingreso usa solo esos desenlaces cerrados.

Una pausa manual, o un hueco de más de un segundo, descarta la visita abierta.
No se inventa una permanencia ni se une un grupo a través de ese corte. Al
retomar, el seguimiento empieza de nuevo y no reutiliza los tracks anteriores.

Al detener la cámara se cierra el cálculo una sola vez, con la misma regla
final que un video: quien estuvo en el frente y no entró cuenta como paso,
incluido quien seguía ahí al detener. Se guardan las mismas tablas del video.
La pantalla de resultados de una sesión de cámara ya terminada muestra el
funnel, los grupos y la posible compra. Las sesiones en vivo ya cerradas no se
recalculan: sus frames no quedaron guardados.

## Aceptación

- La misma secuencia de pies y cruces, medida en tiempo de captura, produce los
  mismos indicadores, el mismo funnel, los mismos grupos y la misma posible
  compra que el cálculo de video.
- Mientras alguien sigue en el frente, no suma un paso ni una entrada. Si sale
  sin cruzar, suma un paso. Si cruza, suma una entrada.
- Un hueco mayor a un segundo, o una pausa, no confirma una permanencia abierta
  ni une un grupo con el tramo siguiente.
- Al terminar, la pantalla de resultados de esa sesión de cámara muestra funnel,
  grupos y posible compra.
- Una sesión en vivo ya guardada conserva sus cifras actuales.
- Ruff y las pruebas que cubren estos casos pasan.
