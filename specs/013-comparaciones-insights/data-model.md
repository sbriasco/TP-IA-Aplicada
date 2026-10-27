# Data Model: Comparaciones e insights

No agrega tablas. Reutiliza sesiones, trabajos, `shop_metrics`, flujo/pico, `shop_funnels`, `visit_pattern_reports`, `possible_purchase_reports` y escenas inmutables ya existentes. El resultado de comparación es un documento de lectura armado en memoria.

## ComparisonRequest (entrada)

| Campo | Tipo | Regla |
|---|---|---|
| `session_ids` | lista UUID | ≥ 1 enviados; tras deduplicar y filtrar elegibles MUST quedar ≥ 2 |
| `zone_name` | string | obligatorio en axis `session` (y en ejes que lean métricas de local); nombre visible de zona |
| `axis` | enum | `session` (P1). P2 opcional: `day`, `time_of_day`, `zone` |

## ComparableColumn

Una columna del contraste.

| Campo | Tipo | Regla |
|---|---|---|
| `key` | string | estable en la respuesta (`session:<uuid>` o grupo P2) |
| `label` | string | nombre de sesión o etiqueta de grupo legible |
| `session_ids` | lista UUID | una sesión (P1) o las del grupo (P2) |
| `camera_label` | string \| null | contexto visible de cámara |
| `resolved_shop_id` | UUID \| null | local resuelto por `zone_name` en la escena de esa sesión; null → métricas de local no disponibles |

## ContrastedFigure (fila)

| Campo | Tipo | Regla |
|---|---|---|
| `family` | enum | `shop_metrics` \| `peak` \| `funnel` \| `visit_patterns` \| `possible_purchase` |
| `code` | string | p. ej. `traffic_total`, `entry_rate`, etapa de funnel, `visit_count` |
| `label` | string | rótulo de producto (incluye estimación si aplica) |
| `cells` | lista Cell | una por columna, mismo orden |
| `relation` | enum | `greater` \| `less` \| `equal` \| `unavailable` (respecto de un orden de columnas documentado, p. ej. primera vs segunda en P1 de dos columnas; con >2 columnas la relación puede ser por pares o «highlight» — ver contrato) |

### Cell

| Campo | Tipo | Regla |
|---|---|---|
| `availability` | `available` \| `unavailable` | |
| `value` | number \| null | null iff unavailable |
| `unavailable_reason` | string \| null | motivo de producto si unavailable |
| `display` | object \| null | extras ya conocidos (p. ej. `start_seconds` del pico) |

**Reglas**:

- Diferencia numérica solo si todas las celdas comparadas en ese cálculo están `available`.
- Cero con `available` es cero real.
- Familia opcional ausente en un lado: celda `unavailable`; la fila permanece si otra columna tiene la familia.

## DerivedInsight

| Campo | Tipo | Regla |
|---|---|---|
| `code` | string | identificador estable de regla (`higher_traffic_total`, `no_highlights`, …) |
| `message` | string | texto corto verificable contra las cifras |
| `figure_code` | string \| null | cifra citada |
| `estimation` | boolean | true si menciona tráfico/atención/posible compra u otra estimación |

Lista vacía de hallazgos útiles → un insight `no_highlights` o equivalente, no silencio engañoso.

## Elegibilidad (derivada, no tabla)

Sesión comparable completa sii:

1. `sessions.deleted_at` es null  
2. origen ≠ webcam  
3. trabajo más reciente (o el de resultado) en `completed` con `result_complete = true`

## Relación con entidades existentes

- **Session / ProcessingJob / ProcessedSession**: origen de columnas y elegibilidad (007).  
- **SceneVersion / Shop**: resolución de `zone_name` → `shop_id`.  
- **shop_metrics + peak**: filas obligatorias (006).  
- **shop_funnels, visit_pattern_*, possible_purchase_***: filas opcionales (010–012).  
- **Chat figures**: sin cambio (008).
