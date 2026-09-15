# Contrato: manifest de fragmentos

Formato propuesto: CSV o JSON local. Los límites se expresan en segundos del video
original y el intervalo es semiabierto: `[start_video_seconds, end_video_seconds)`.

| Campo | Descripción |
|---|---|
| `video_id` | Identificador local del video seleccionado |
| `fragment_id` | Identificador estable del fragmento |
| `start_video_seconds` | Inicio absoluto en segundos del video original, inclusive |
| `end_video_seconds` | Fin absoluto en segundos del video original, exclusivo |
| `selection_reason` | Motivo de selección |
| `covered_cases` | Circulación, cruces, oclusiones u otros casos observables |
| `coverage_limitations` | Casos ausentes o insuficientes |

## Conversión temporal

Para una observación con timestamp absoluto `video_timestamp_seconds`:

```text
relative_seconds = video_timestamp_seconds - start_video_seconds
```

El valor absoluto y el relativo deben conservarse en los resultados cuando ambos sean
relevantes. Las métricas de comportamiento usan el timestamp absoluto del video; el tiempo
relativo sirve para ubicar la observación dentro del fragmento. La duración del fragmento
se calcula como `end_video_seconds - start_video_seconds` y no se confunde con el tiempo de
procesamiento.

## Validaciones

- `start_video_seconds` debe ser mayor o igual a cero.
- `end_video_seconds` debe ser mayor que `start_video_seconds`.
- Los límites deben estar dentro de la duración conocida del video; si no puede conocerse,
  la limitación debe quedar registrada.
- El fragmento debe conservar el identificador del video y su unidad temporal.
