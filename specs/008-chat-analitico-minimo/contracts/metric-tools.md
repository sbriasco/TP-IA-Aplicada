# Lecturas que puede usar el chat

No son pedidos HTTP. Las ejecuta el backend. El modelo no las calcula y no puede pedir otras.

Cada lectura recibe la sesión y el local ya resueltos. Ignora un tramo. Si el análisis más reciente no tiene `result_complete`, no devuelve la cifra: devuelve que no hay resultado final.

| Lectura | Cifra | Si no está disponible |
|---|---|---|
| Tráfico | `traffic_total`, rótulo `visit_estimate` | `unavailable` y el motivo ya guardado. No es cero |
| Ingresos | `entries` | Igual |
| Ocupación | `visible_occupancy`, rótulo `visible` | Igual. No es un máximo nuevo ni la ocupación total |
| Permanencia | `dwell_mean_seconds` y `dwell_median_seconds`, rótulo `observable` | Cada una por separado. No se inventa la que falta |
| Pico | `bucket_index`, `start_seconds`, `track_count` del pico ya guardado | Se cita como tramo del video |

El listado de sesiones devuelve `session_id`, `name`, `finished_at` y `result_complete`. No devuelve cifras.

No existen lecturas de salidas, pasos, tasa ni del detalle del flujo.
