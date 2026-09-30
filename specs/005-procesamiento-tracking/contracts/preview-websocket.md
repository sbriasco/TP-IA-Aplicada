# Contrato WebSocket de previsualización (video real)

Extiende [specs/002](../../002-entorno-arquitectura-base/contracts/preview-websocket.md). El endpoint no cambia:

`ws://{host}/ws/jobs/{job_id}/preview`

Un trabajo desconocido cierra con `4404`. Si ya está `completed`, `failed` o `cancelled`, se envía `job.terminal` y no se reconstruyen imágenes.

## Trabajos sintéticos

Siguen el mensaje `preview.update` con `schema_version` `"1"`: JPEG 320×180, hasta 100 KiB. Esta feature no les cambia el formato.

## Mensaje `preview.update` de un `video_analysis`

`schema_version` `"2"`. La imagen es el fotograma analizado, a su resolución, con recuadros, identificadores temporales, zonas y línea de entrada dibujados. `frame_index` y `video_timestamp_seconds` son los de esa imagen (desfase cero). `progress_percent` es `frames_analyzed / frames_total` del video, no el reloj de pared.

```json
{
  "type": "preview.update",
  "schema_version": "2",
  "session_id": "3e7d8d48-d910-47c2-98d2-d80dc90abec4",
  "job_id": "941e21b9-cb8c-45b2-934c-f8d670cf3416",
  "frame_index": 12,
  "video_timestamp_seconds": 0.48,
  "progress_percent": 50.0,
  "image_media_type": "image/jpeg",
  "image_base64": "...",
  "measures": [
    {
      "shop_id": "0b1d5a22-1c3e-4f5a-9d6e-7a8b9c0d1e2f",
      "code": "entries",
      "value": 1,
      "availability": "available",
      "partial": true
    }
  ]
}
```

Si el JPEG supera 200 KiB, se baja la calidad de compresión. No se reduce a 320×180.

## Mensaje `job.terminal`

Igual que specs/002. `status` ahora también puede ser `cancelled`.

## Presión

Se mantienen las reglas de specs/002: un mensaje pendiente por conexión, el nuevo reemplaza al viejo, el productor no espera, y un cliente que llega tarde consulta el estado por `GET /jobs/{job_id}` y `GET /jobs/{job_id}/measures`.
