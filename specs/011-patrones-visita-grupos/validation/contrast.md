# Contraste manual de patrones de visita y grupos estimados

Estado: no ejecutado.

Este contraste no entra en pytest, Vitest ni Playwright. No afirma precisión ni coincidencia con el conteo manual, y no retira el aviso de la pantalla.

## Conteos manuales

Clip:

| Observación | Conteo manual | Conteo de FlowSight | Diferencia |
|---|---|---|---|
| Transición entre áreas |  |  |  |
| Secuencia de áreas |  |  |  |
| Cambio de local |  |  |  |
| Grupo estimado |  |  |  |

## Clase de cada diferencia

Para cada diferencia, una de: detección faltante, espuria, pérdida de track, oclusión, duplicado, cruce omitido u otro. El protocolo es el de `specs/001-validacion-videos-tracking`: cada ocurrencia observable se compara por separado y la continuidad del track se evalúa aparte.
