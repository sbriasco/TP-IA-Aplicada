# Contrato: configuración de escena

Formato propuesto: JSON local, una configuración por escena y video. No es todavía un
schema ejecutable ni un contrato de la aplicación.

El siguiente ejemplo es sintético y válido; no describe ninguno de los videos reales.

```json
{
  "scene_id": "scene-001",
  "video_id": "video-001",
  "time_unit": "seconds",
  "frame_reference": {
    "frame_index": 240,
    "width": 1920,
    "height": 1080,
    "video_timestamp": 8.0
  },
  "front_zone": {
    "name": "front-zone",
    "polygon": [[420, 300], [1280, 300], [1420, 900], [360, 900]],
    "purpose": "zona frontal observable"
  },
  "entry_line": {
    "name": "entry-line",
    "start": [500, 850],
    "end": [1400, 850],
    "directions": {
      "A_to_B": "entry",
      "B_to_A": "exit"
    }
  },
  "notes": "Ejemplo sintético ajeno a los videos reales."
}
```

## Reglas

- Las coordenadas se expresan en el sistema del frame original.
- La zona y línea deben poder identificarse visualmente en el fragmento elegido.
- `A_to_B` y `B_to_A` deben declararse como `entry`, `exit` o `unknown`; representan los
  dos sentidos de cruce de la línea.
- La configuración debe conservar una referencia al frame y sus dimensiones.
- `width` y `height` deben ser mayores que cero.
- Cada punto debe estar dentro de `[0, width] × [0, height]`.
- El polígono debe tener al menos tres puntos distintos y área no nula.
- La línea debe tener exactamente dos puntos distintos y longitud no nula.
- Las validaciones deben fallar antes de procesar si alguna condición geométrica no se cumple.
