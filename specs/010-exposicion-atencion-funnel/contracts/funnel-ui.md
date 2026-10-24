# Contrato de pantalla: funnel en el resultado

Solo la pantalla de resultados de una sesión que no es webcam y cuyo análisis está completado. El modelo está en [data-model.md](../data-model.md) y el pedido en [openapi.yaml](./openapi.yaml).

## Qué se muestra

Por local, un bloque aparte de los ocho indicadores:

| Etapa | Nombre visible | Nota |
|---|---|---|
| `observed_pass` | Paso observado | Incluye a quienes después entraron. No es «paso frente al local». |
| `exposure` | Exposición a la vidriera | |
| `stop` | Detención frente a la vidriera | Junto al umbral de 3 segundos de video. |
| `attention` | Atención estimada | Junto al umbral de 8 segundos. Texto: estimación, no afirma que haya mirado la vidriera. |
| `linked_entry` | Ingreso vinculado | No es el total de entradas ni una compra. |

Las entradas ya cerradas siguen en el indicador existente. Si el número difiere del ingreso vinculado, los dos quedan visibles.

| Tasa | Nombre visible |
|---|---|
| `observed_pass_to_exposure` | De paso observado a exposición |
| `exposure_to_stop` | De exposición a detención |
| `stop_to_attention` | De detención a atención estimada |
| `attention_to_linked_entry` | De atención estimada a ingreso vinculado |

Una tasa no disponible se muestra como no disponible, no como cero. Ninguna se rotula «tasa de ingreso».

Si `excluded_window_only` es mayor que cero: «N visitas estuvieron en la vidriera y no pasaron por el frente. Quedan fuera del funnel.»

Si `precision_uncommitted` es verdadero: «La precisión de estas etapas no está comprometida.»

Sin vidriera, exposición, detención, atención e ingreso vinculado dicen que no hay zona de vidriera. El paso observado sigue.

## Qué no cambia

- Elegir un tramo del video vuelve a pedir hechos y minutos del flujo. No vuelve a pedir el funnel.
- Los ocho indicadores, la tasa de ingreso y el chat mínimo no usan este bloque.
- Una sesión webcam no muestra el bloque y no se sustituye por el de un archivo.
- Mientras el análisis no terminó, el bloque no aparece.
