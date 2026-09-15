# Contrato: resultados, rendimiento e informe

## Resultados automáticos

Se propone JSONL para detecciones y tracks, con una línea por observación relevante:

```json
{
  "session_id": "run-001",
  "video_id": "video-001",
  "fragment_id": "fragment-001",
  "frame_index": 0,
  "video_timestamp": 0.0,
  "track_id": "person-001",
  "bbox": [120.0, 80.0, 260.0, 420.0],
  "reference_point": [190.0, 420.0],
  "event_type": "zone_enter",
  "target": "front-zone",
  "direction": "unknown",
  "visibility": "visible"
}
```

El `bbox` usa `[x_min, y_min, x_max, y_max]` en píxeles del frame original y
`reference_point` es el punto usado para reglas espaciales, por ejemplo el centro inferior
del bbox. El `track_id` es temporal y pertenece a la sesión/cámara; no es una identidad real.

## Revisión humana asistida

La comparación se realiza revisando una visualización local anotada con bbox o punto de
referencia, `track_id`, zona y eventos. Las correspondencias y errores se guardan en
`outputs/review.csv`. No se construye interfaz web ni algoritmo de asociación. Solo se
clasifican resultados dentro de la muestra manual revisada; la ausencia de anotación fuera
de esa muestra no es evidencia de un espurio.

## Rendimiento por fragmento

Se propone CSV con estas columnas:

`session_id,video_id,fragment_id,device,video_duration_seconds,frames_processed,processing_time_seconds`

La duración y los frames describen el contenido procesado; el tiempo de procesamiento
describe el rendimiento operativo. Ninguno sustituye los timestamps del video usados para
permanencia o intervalos de comportamiento.

Los fragmentos se reciben como `[start_video_seconds, end_video_seconds)`, en segundos del
video original. Para cada observación, `relative_seconds = video_timestamp -
start_video_seconds`; el valor absoluto se conserva también.

## Informe de viabilidad

El informe Markdown debe contener:

1. Identificación de videos, fragmentos, escena, versión candidata y equipo.
2. Cobertura de la referencia manual y casos ausentes.
3. Errores de detección, pérdidas, oclusiones, duplicados y cruces omitidos.
4. Rendimiento por fragmento y resumen global opcional.
5. Tabla por medición con evidencia directa, estado, limitaciones y ajustes.
6. Decisiones pendientes y datos no evaluables.

Estados permitidos:

- `viable`
- `viable con ajustes`
- `no viable con el material o configuración evaluados`
- `no evaluable por falta de evidencia`

Una conclusión negativa respaldada por evidencia completa la validación. No se agregan
umbrales de precisión o velocidad sin una decisión posterior basada en datos.
