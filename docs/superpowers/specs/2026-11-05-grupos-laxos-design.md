# Grupos estimados más laxos

Pedido del usuario (2026-11-05): la detección de grupos debe costar menos.
Prefiere más falsos positivos que falsos negativos. Aprobó aflojar los tres
umbrales visibles y, además, dejar entrar a quien casi no se mueve.

## Diseño

Los análisis nuevos confirman un grupo estimado cuando, durante al menos 1
segundo de video, cada par está a no más de 0,16 del ancho del encuadre. Si
los dos tienen dirección, el ángulo entre esas direcciones no supera 90 grados.
Si uno o los dos no tienen dirección, la cercanía alcanza: no hace falta un
desplazamiento mínimo. Sigue siendo una estimación y no afirma una relación real.

Quien se desplaza al menos 0,005 del ancho sigue teniendo dirección, con el
mismo corte de hoy. Un desplazamiento menor no crea dirección y tampoco excluye.
Un hueco de más de 1 segundo de video cierra el grupo; uno de hasta 1 segundo
lo conserva y no inventa posiciones. El resto del algoritmo (un grupo por
visita en cada instante, cliques, etiquetas) no cambia. El salto de un frame
del análisis de video queda fuera de este cambio.

Cada informe guarda los umbrales con los que se calculó. Los análisis ya
guardados siguen en 0,08, 45 grados, 2 segundos y 0,005. No se recalculan.
Una migración nueva acepta esos valores y también 0,16, 90 grados y 1 segundo.
El corte de movimiento sigue fijo en 0,005. Las restricciones de SQLAlchemy
quedan alineadas con esa migración.

Resultados deja de mostrar el texto fijo de ocho centésimas, 45 grados y 2
segundos. Muestra los tres umbrales que ya devuelve el informe
(`proximity_width_fraction`, `direction_degrees`, `minimum_seconds`). El corte
interno de 0,005 no se muestra.

## Aceptación

- Dos visitas quietas, a no más de 0,16 del ancho y durante al menos 1 segundo,
  forman un grupo en un análisis nuevo.
- Dos visitas con dirección y un ángulo de hasta 90 grados también, si cumplen
  distancia y tiempo. Más de 90 grados no.
- Menos de 1 segundo no confirma. Un hueco mayor a 1 segundo cierra el episodio.
- Un informe viejo conserva 0,08, 45 y 2, y la pantalla los muestra así.
- Un informe nuevo guarda 0,16, 90 y 1, y la pantalla los muestra así.
- La migración aplica sobre una base que ya tiene filas con los umbrales viejos
  sin modificarlas.
- Ruff y las pruebas de patrones de visita que cubren estos casos pasan.
