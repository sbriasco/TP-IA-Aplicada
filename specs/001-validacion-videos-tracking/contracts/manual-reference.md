# Contrato: referencia manual

Formato propuesto: CSV o JSON local. Debe registrar observaciones acotadas, no una
anotación exhaustiva de todos los videos.

## Campos mínimos

| Campo | Descripción |
|---|---|
| `video_id` | Video observado |
| `fragment_id` | Fragmento e intervalo del video |
| `observation_id` | Identificador local de la ocurrencia |
| `relative_start` | Inicio relativo al fragmento |
| `relative_end` | Fin relativo cuando corresponda |
| `video_timestamp_start` | Inicio absoluto en segundos del video original |
| `video_timestamp_end` | Fin absoluto en segundos del video original |
| `observation_type` | Persona, cruce, permanencia, oclusión u otro |
| `target` | Zona o línea observada |
| `direction` | Entrada, salida, desconocida o no aplicable |
| `covered_cases` | Casos cubiertos por la muestra |
| `notes` | Criterio, limitación o evidencia |

## Archivo de revisión asistida

Las correspondencias y errores se registran en `outputs/review.csv` durante una revisión
humana de la visualización local anotada. Campos mínimos:

| Campo | Descripción |
|---|---|
| `fragment_id` | Fragmento revisado |
| `manual_observation_id` | Observación manual |
| `automatic_observation_id` | Resultado automático revisado, si existe |
| `match_status` | Coincidencia, omisión, duplicado, no comparable o espurio dentro de la muestra |
| `error_category` | Detección, oclusión, pérdida, cruce u otra categoría |
| `reviewer_notes` | Evidencia observada en la visualización |

No se usa un algoritmo de asociación. Solo se comparan las observaciones dentro de la
muestra manual revisada; la ausencia de una anotación fuera de esa muestra no es un espurio.

## Comparación

- Una coincidencia se basa en la misma ocurrencia observable, intervalo, zona o línea y
dirección cuando estén disponibles, según revisión humana de la visualización.
- Una omisión es una observación manual sin resultado automático comparable.
- Un espurio es un resultado automático revisado dentro de la muestra que no tiene
observación manual correspondiente; no se extrapola fuera de la muestra.
- Un duplicado requiere varios resultados automáticos para una misma ocurrencia observable;
un cambio de `track_id` aislado no basta.
- La continuidad del track se registra por separado como continua, posible pérdida, cambio
de ID o no evaluable.
- Si la muestra no cubre cruces u oclusiones, se amplía antes de concluir sobre esos casos.
