# Contrato de pantalla: posible compra estimada en el resultado

Solo la pantalla de resultados de una sesión que no es webcam y cuyo análisis está completado. El modelo está en [data-model.md](../data-model.md) y el pedido en [openapi.yaml](./openapi.yaml).

## Qué se muestra

Un bloque de toda la sesión, aparte de los ocho indicadores, del funnel y de los patrones:

- La cantidad de visitas con posible compra estimada.
- El umbral de 1 segundo de video.
- El texto de que es una estimación y que no es una venta confirmada. No atribuye la bolsa a un local ni identifica a la persona.
- Si `precision_uncommitted` es verdadero: «La precisión de la posible compra estimada no está comprometida.»

Si `visit_count` es cero y la cifra está disponible: «0 visitas con posible compra estimada». Eso no se muestra como no disponible.

Los identificadores de visita no son obligatorios en la pantalla del analista; el contrato de API los incluye para contraste y pruebas.

## Qué no cambia

- Elegir un tramo del video vuelve a pedir hechos y minutos del flujo. No vuelve a pedir este bloque.
- Elegir otro local de la misma sesión no vuelve a pedir este bloque y no lo recorta.
- Los ocho indicadores, la tasa de ingreso, el funnel, los patrones y el chat mínimo no usan esta cifra.
- Una sesión webcam no muestra el bloque y no se sustituye por el de un archivo.
- Mientras el análisis no terminó, el bloque no aparece.
