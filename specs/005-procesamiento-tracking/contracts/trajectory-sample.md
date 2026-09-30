# Muestra de trayectoria

Archivo JSONL referenciado por `ProcessingJob.trajectory_relative_path`. No es una respuesta HTTP completa: `GET /jobs/{job_id}/trajectory` solo devuelve los metadatos de [openapi.yaml](./openapi.yaml).

## Encabezado (primera línea)

```json
{
  "record": "header",
  "session_id": "uuid",
  "job_id": "uuid",
  "sample_every_frames": 5,
  "detector_name": "yolov8n",
  "detector_version": "8.4.153",
  "tracker_name": "bytetrack",
  "tracker_version": "ultralytics-bytetrack"
}
```

Con el detector de prueba, `detector_name` y `tracker_name` son `fake`.

## Muestra

Una línea por identificador presente en un fotograma elegido (índices 0, 5, 10, …):

```json
{
  "record": "sample",
  "frame_index": 10,
  "video_timestamp_seconds": 0.4,
  "track_id": 3,
  "bbox": [0.1, 0.2, 0.3, 0.8],
  "foot": [0.2, 0.8]
}
```

`bbox` es `[x1, y1, x2, y2]` normalizado. `foot` es el centro inferior del recuadro, también normalizado. No se escribe una línea por cada fotograma.
