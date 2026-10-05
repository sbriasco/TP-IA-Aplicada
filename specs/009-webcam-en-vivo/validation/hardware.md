# Aceptación física pendiente · 2026-10-05

No se ejecutó un ensayo con webcam física/personas. Esta PC tiene PyTorch CPU. No se midió CUDA, encuadre, precisión, concurrencia visible ni latencia física. Las fuentes sintéticas no reemplazan estos datos.

| Ensayo | Estado | Evidencia necesaria |
|---|---|---|
| Webcam real ≥10 minutos | No evaluado | Dispositivo, resolución, equipo y encuadre |
| ≥40 cruces manuales | No evaluado | Real/automático, omisiones y espurios por sentido; personas simultáneas |
| p95 captura-pantalla ≤2 segundos | No evaluado | Muestras calibradas con incertidumbre |
| Sobrecarga completa 600 segundos | No evaluado | Captura/worker/API/pantalla, pendientes y recuperación |
| Estabilidad completa 7200 segundos | No evaluado | RSS/VRAM tras warmup, crecimiento y archivos |
| Reconexión física | No evaluado | Nueva confirmación, hueco y ausencia de cruces entre segmentos |

No guardar videos ni secuencias de imágenes. Anotar tiempos/sentidos sin identidad. Si un sentido no tiene cruces reales, exigir cero falsas detecciones; no calcular porcentaje en ese caso.
