# Data Model: Patrones de visita y grupos estimados

Extiende el cierre de un análisis de archivo. No se reescriben `scene_events`, `shop_metrics`, `shop_funnels`, `analysis_measures`, `line_crossings` ni `trajectory.jsonl`.

Un área guardada es `(shop_id, zone_role)` con `zone_role` en `front`, `interior` o `window`. Esos valores son los de `scene_zone_role`. El editor sigue llamando `showcase` a la vidriera. Esta feature no agrega un valor a ese enum.

## visit_pattern_reports

Una fila por trabajo de archivo completado. Un trabajo webcam no la tiene.

| Campo | Tipo | Regla |
|---|---|---|
| `job_id`, `session_id` | UUID | único `job_id` |
| `proximity_width_fraction` | decimal | `0.08` |
| `direction_degrees` | decimal | `45` |
| `minimum_seconds` | decimal | `2` |
| `motion_epsilon_width_fraction` | decimal | `0.005`. Corte interno de «casi no se mueve». La pantalla no lo lista entre los tres umbrales. |
| `patterns_availability` | enum `available` \| `unavailable` | `unavailable` solo si la escena no tiene ningún polígono |
| `patterns_unavailable_reason` | string nullable | `no_areas` o null |
| `groups_availability` | enum | `available` si la escena de ese análisis existe |
| `group_count` | integer ≥ 0 | episodios confirmados. Cero es disponible |
| `precision_uncommitted` | boolean | `true` |

## visit_area_transitions

Solo si los patrones están disponibles. Una fila por par ordenado que al menos una visita hizo.

| Campo | Tipo | Regla |
|---|---|---|
| `from_shop_id`, `to_shop_id` | UUID | locales de las dos áreas |
| `from_zone_role`, `to_zone_role` | `scene_zone_role` | |
| `track_count` | integer ≥ 1 | identificadores distintos. Repetir el par no suma otro |

Único `(job_id, from_shop_id, from_zone_role, to_shop_id, to_zone_role)`.

El paso se anota al salir de la primera y quedar en la segunda dentro de 1 segundo de video. Estar en las dos a la vez no inserta fila.

## visit_sequences

Solo si los patrones están disponibles. Una fila por cadena distinta.

| Campo | Tipo | Regla |
|---|---|---|
| `areas` | JSON | lista ordenada de `{shop_id, zone_role}`. Sin el mismo rol del mismo local dos veces seguidas |
| `track_count` | integer ≥ 1 | identificadores distintos que tuvieron esa cadena |

Único `(job_id, areas)`. Una visita con dos cadenas distintas suma en las dos. La misma cadena repetida por la misma visita suma uno.

## visit_shop_transitions

Solo si los patrones están disponibles. Sale de las áreas seguidas de esas cadenas cuando el `shop_id` cambia.

| Campo | Tipo | Regla |
|---|---|---|
| `from_shop_id`, `to_shop_id` | UUID | distintos |
| `track_count` | integer ≥ 1 | identificadores distintos |

Único `(job_id, from_shop_id, to_shop_id)`. No es una entrada oficial y no alimenta el funnel.

## visit_groups

Un episodio confirmado. Puede haber varios con los mismos integrantes si medió una ruptura.

| Campo | Tipo | Regla |
|---|---|---|
| `ordinal` | integer ≥ 1 | orden de inicio, estable en una segunda corrida |
| `started_video_timestamp_seconds` | decimal | inicio del tramo que ya cumple las tres condiciones |
| `ended_video_timestamp_seconds` | decimal | último instante observado del episodio. Posterior o igual al inicio, y el tramo dura al menos 2 segundos de video |
| `label` | enum | `group_estimate` |

Único `(job_id, ordinal)`.

## visit_group_members

| Campo | Tipo | Regla |
|---|---|---|
| `track_id` | integer | identificador temporal de esa sesión y esa cámara |

Único `(group_id, track_id)`. Cada episodio tiene al menos dos filas. En un mismo instante de video, un `track_id` aparece en un solo episodio de ese trabajo.

## Consulta

- Métricas, hechos, funnel y chat: sin cambio de forma.
- `GET /sessions/{session_id}/visit-patterns` lee esta fila y sus hijas. No acepta tramo ni local.
- Webcam y análisis no completado: sin fila consultable. El `409` está en [contracts/openapi.yaml](./contracts/openapi.yaml).
