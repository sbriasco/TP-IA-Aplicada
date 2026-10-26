# Contrato de pantalla: patrones y grupos en el resultado

Solo la pantalla de resultados de una sesión que no es webcam y cuyo análisis está completado. El modelo está en [data-model.md](../data-model.md) y el pedido en [openapi.yaml](./openapi.yaml).

## Qué se muestra

Un bloque de toda la sesión, aparte de los ocho indicadores y del funnel:

- Transiciones entre áreas, con la cantidad de visitas. El área se lee con el nombre del local y el rol: frente, interior o vidriera. `window` se muestra como vidriera.
- Secuencias, en el orden guardado, con la cantidad de visitas.
- Cambios de local, con la cantidad de visitas. No se rotulan como entradas ni como compras.
- Grupos estimados. Cada uno lista los identificadores de la visita, el inicio y el fin en segundos de video, y el texto de que es una estimación y no afirma una relación real.
- Junto a los grupos, los tres umbrales: ocho centésimas del ancho del encuadre, 45 grados y 2 segundos de video. El corte interno de visita quieta no se muestra.
- Si `precision_uncommitted` es verdadero: «La precisión de los patrones y de los grupos estimados no está comprometida.»

Si `patterns_availability` es `unavailable` y el motivo es `no_areas`: «No hay áreas.» Las transiciones, las secuencias y los cambios de local no se reemplazan por cero. Los grupos siguen en el mismo bloque.

Si `group_count` es cero y los grupos están disponibles: «0 grupos estimados». Eso no se muestra como no disponible.

## Qué no cambia

- Elegir un tramo del video vuelve a pedir hechos y minutos del flujo. No vuelve a pedir este bloque.
- Elegir otro local de la misma sesión no vuelve a pedir este bloque y no lo recorta.
- Los ocho indicadores, la tasa de ingreso, el funnel y el chat mínimo no usan estas cifras.
- Una sesión webcam no muestra el bloque y no se sustituye por el de un archivo.
- Mientras el análisis no terminó, el bloque no aparece.
