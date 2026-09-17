# Contrato WebSocket de previsualización

## Endpoint

`ws://{host}/ws/jobs/{job_id}/preview`

El servidor valida el trabajo. Uno desconocido cierra con `4404`. Esta Feature no agrega autenticación.

## Mensaje `preview.update`

```json
{
  "type": "preview.update",
  "schema_version": "1",
  "session_id": "3e7d8d48-d910-47c2-98d2-d80dc90abec4",
  "job_id": "941e21b9-cb8c-45b2-934c-f8d670cf3416",
  "frame_index": 12,
  "video_timestamp_seconds": 0.48,
  "progress_percent": 60.0,
  "image_media_type": "image/jpeg",
  "image_base64": "..."
}
```

El timestamp proviene del fixture, no del reloj operativo. La imagen es un JPEG sintético de 320×180, de hasta 100 KiB, y es descartable. El valor de configuración de ejemplo limita la publicación a 5 actualizaciones por segundo.

## Mensaje `job.terminal`

```json
{
  "type": "job.terminal",
  "schema_version": "1",
  "session_id": "3e7d8d48-d910-47c2-98d2-d80dc90abec4",
  "job_id": "941e21b9-cb8c-45b2-934c-f8d670cf3416",
  "status": "completed"
}
```

REST conserva la fuente de verdad. Perder el mensaje no altera el trabajo.

## Presión y verificación

- Un slot pendiente por conexión; una actualización nueva reemplaza a la pendiente.
- El productor no espera al cliente; desconectar elimina solo su slot.
- Un cliente tardío o reconectado consulta primero el estado por REST y recibe únicamente actualizaciones futuras.
- Si el trabajo ya terminó, no se reconstruyen previews; REST devuelve el estado terminal y su traza persistida.
- Antes de publicar `job.terminal`, el servidor reemplaza cualquier preview pendiente por la última actualización producida. El consumidor lento debe recibir esa actualización y luego el terminal mientras la conexión permanezca abierta.
- La prueba mide que el máximo pendiente sea uno, que se reciba el último frame publicado antes del terminal y que el trabajo termine.
