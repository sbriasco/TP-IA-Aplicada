# Atención a la vidriera por permanencia en el frente

Pedido del usuario (2026-11-05): la atención estimada da siempre 0. Eligió
contarla con la permanencia en el frente, con un tiempo más corto, en vez de
exigir el pie dentro del polígono de vidriera. Aprobó la escala de abajo.

## Diseño

El polígono de vidriera deja de decidir exposición, detención y atención. Sigue
haciendo falta que la vidriera esté configurada: sin ese polígono esas tres
etapas y el ingreso vinculado siguen no disponibles. El paso observado no
cambia: es quien entró al frente.

En un análisis nuevo, con vidriera configurada, cada etapa cuenta un `track_id`
una sola vez:

- Exposición: tuvo una permanencia medida en el frente, de cualquier duración.
- Detención: esa permanencia duró al menos 1 segundo.
- Atención estimada: duró al menos 2 segundos.

La permanencia es el hecho `dwell` que se cierra al salir del frente. Si el
seguimiento se pierde antes de salir, ese tramo no se emite y no cuenta. Si un
id tiene varias permanencias, alcanza con que una cumpla el tiempo. El inicio
de la atención es el comienzo de la permanencia que llegó a 2 segundos; si hay
varias, se usa la más temprana. El ingreso vinculado sigue siendo una entrada
al local después de ese inicio.

Los hechos `showcase_stop` no cambian y el funnel nuevo no los usa para estas
etapas. Quienes entraron a la vidriera sin entrar al frente siguen contándose
aparte y no suman atención.

Cada informe guarda los umbrales con los que se calculó. Los análisis ya
guardados siguen en 3 y 8 segundos, calculados con el polígono, y no se
recalculan. Una migración acepta esos valores y también 1 y 2 segundos. La
exposición no tiene umbral propio. El salto de frames y los grupos quedan
fuera de este cambio.

## Aceptación

- Una permanencia en el frente de 2 segundos cuenta exposición, detención y
  atención. Una de 1 segundo cuenta las dos primeras y no la atención. Una más
  corta cuenta solo exposición.
- Una entrada al frente sin permanencia cerrada no cuenta exposición.
- Sin polígono de vidriera, exposición, detención, atención e ingreso vinculado
  siguen no disponibles.
- Un ingreso posterior al inicio de la atención vinculada cuenta. Uno anterior,
  no.
- Un informe viejo conserva 3 y 8. Uno nuevo guarda 1 y 2.
- La migración aplica sobre filas con los umbrales viejos sin modificarlas.
- Ruff y las pruebas del funnel que cubren estos casos pasan.
