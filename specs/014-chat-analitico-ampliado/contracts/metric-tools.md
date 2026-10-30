# Lecturas que puede usar el chat ampliado

No son pedidos HTTP públicos aparte de `POST /chat`. Las ejecuta el backend. El modelo no las calcula y no puede pedir otras.

Si el análisis más reciente no tiene `result_complete`, o la sesión es webcam, no se entregan cifras comerciales como resultado final.

## Tool: cifras de la sesión (`get_session_figures` o equivalente ampliado)

Recibe sesión y local/zona ya resueltos. Alcance: toda la sesión (ignora tramo pedido en el texto).

| Lectura | Código(s) | Notas |
|---|---|---|
| Tráfico | `traffic_total` | rótulo estimación de visitas |
| Entradas | `entries` | |
| Salidas | `exits` | |
| Pasos | `store_pass` | |
| Tasa de ingreso | `entry_rate` | no es aditiva en grupos P2 (el contraste ya lo marca) |
| Ocupación | `visible_occupancy` | visible ≠ total |
| Permanencia | `dwell_mean_seconds`, `dwell_median_seconds` | observable |
| Pico | `peak_track_count` + `start_seconds` | tramo de video |
| Funnel | etapa de entradas vinculadas del producto | opcional; si falta → unavailable |
| Patrones / grupos | `group_count` | estimación; opcional |
| Posible compra | `visit_count` | estimación; nunca venta |

Listado auxiliar de sesiones (nombres / última): `session_id`, `name`, `finished_at`, `result_complete`, origen archivo vs vivo. Sin cifras.

## Tool: contraste (`compare_sessions` o equivalente)

Args: `session_ids` (≥2 elegibles), `zone_name`, `axis` ∈ {`session`, `day`, `time_of_day`, `zone`}.

Comportamiento: delega en el ensamblado de comparaciones (013). Devuelve columnas, celdas, relation/delta e insights deterministas. Errores estructurados: insuficiente elegibles, eje no disponible, zona inválida — el chat los traduce a aclaración o mensaje claro, sin inventar columnas.

## Prohibido

- SQL libre, lectura de video/frames, RAG sobre documentos como fuente de cifras.
- Tools fuera de esta lista.
- Confirmar compras, identidades o seguimiento entre cámaras (ni siquiera leyendo `visit_count`).
