# Research: Comparaciones e insights

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`. Clarificaciones de spec (2026-10-27) ya fijaron ejes P1/P2, familias, filas opcionales, reloj de horario y emparejamiento de zona.

## R1 — Solo lectura de cifras guardadas

**Decision**: La comparación se arma al consultar. No hay migración ni tablas nuevas. Un servicio de backend lee, por cada sesión elegible, las cifras ya persistidas (métricas de local, pico, funnel, patrones, posible compra) y ensambla filas/columnas e insights. MUST NOT reabrir el video, MUST NOT recalcular desde eventos ni `trajectory.jsonl`, MUST NOT llamar al modelo.

**Rationale**: FR-001/FR-010 y constitución II/III/VI. Misma entrada → mismo resultado sin estado derivado.

**Alternatives considered**: Persistencia de «comparaciones guardadas». Se rechaza: añade ciclo de vida sin valor para el MVP. Recalcular métricas al comparar. Se rechaza por FR-001.

## R2 — Elegibilidad de columna

**Decision**: Una sesión entra como columna completa solo si: no está dada de baja (`deleted_at` nulo), origen de archivo (`video_file` o `synthetic`, no webcam), y tiene análisis `completed` con `result_complete`. Duplicar el mismo `session_id` en la petición cuenta una sola vez. Menos de dos sesiones elegibles tras filtrar → error de negocio (no se inventa comparación). Webcam / incompleta / fallida / cancelada → rechazo con código propio o exclusión explícita en el cuerpo de error.

**Rationale**: FR-002, SC-005, alineación con 009.

**Alternatives considered**: Incluir webcam con etiqueta parcial. Se rechaza: la spec exige no presentarla como columna completa.

## R3 — Alineación de zona para las ocho métricas

**Decision**: Las ocho métricas, la tasa de ingreso y el horario pico viven por local (`shop_id`). La petición de comparación P1 exige un `zone_name` (nombre visible de zona). En cada sesión se resuelve el local de su escena inmutable cuyo nombre coincide (igualdad de texto ya usada en producto). Si una sesión no tiene esa zona, las filas de métricas/pico de esa columna quedan no disponibles con motivo. Sesiones de cámaras distintas pueden contrastarse si el analista las eligió; no se unifican tracks. El eje P2 por zona reutiliza la misma regla y, además, solo empareja dentro de la misma cámara (FR-004).

**Rationale**: Clarificación de zona (cámara + nombre) y contrato actual de `GET .../shops/{shop_id}/metrics`.

**Alternatives considered**: Emparejar solo por `shop_id`. Se rechaza: rompe historial tras nueva versión de escena. Agregar métricas «de sesión» sin local. Se rechaza: no existen en 006.

## R4 — Familias, diferencias e insights

**Decision**:

- Filas obligatorias: códigos de `ShopMetricCode` (ocho, incluida `entry_rate`) + pico (`peak` con `start_seconds` / `track_count` como en 006/007).
- Filas opcionales: funnel (etapas/tasas ya guardadas), patrones/grupos, posible compra (`visit_count` + rótulos de estimación). Se incluyen si al menos una columna tiene datos; el lado sin fila/API disponible → no disponible; la fila no se omite.
- Diferencia o relación solo si ambos lados están `available` y tienen valor; si no, `relation = unavailable` y sin delta numérico. Cero real disponible no se trata como no disponible.
- Insights: reglas deterministas en backend (p. ej. «sesión A tiene mayor `traffic_total` que B»). Sin LLM. Si no hay diferencias útiles → mensaje de «sin diferencias destacables» / faltan datos. Conservar rótulos de estimación.

**Rationale**: FR-003/005/006/007/009 y clarificaciones.

**Alternatives considered**: Insights vía Azure. Se rechaza: FR-006 y Feature #11. Omitir filas opcionales ausentes. Se rechaza por clarificación.

## R5 — Contrato HTTP y UI

**Decision**: `POST /comparisons` con cuerpo `{ session_ids, zone_name, axis }` donde `axis` en P1 es `session`. Respuesta: columnas (id, nombre, cámara, contexto visible), filas de cifras contrastadas, insights. No modifica `GET /sessions/{id}/shops/{shop_id}/metrics`, funnel, visit-patterns, possible-purchases ni chat. Pantalla/flujo aparte del resultado individual (entrada desde historial eligiendo N sesiones). El chat mínimo no gana herramientas nuevas.

**Rationale**: Varios UUID no caben limpios en GET; aislamiento de 007/008.

**Alternatives considered**: GET con query repetida. Se tolera peor con muchos ids. Embebido en `SessionResultsPage` como «otro resultado». Se rechaza: confunde con una sola sesión.

## R6 — Ejes P2 (día / horario / zona)

**Decision**: Fuera del camino crítico de merge de P1. Si el tiempo alcanza en la misma feature:

- **Día**: agrupar sesiones elegibles por fecha de calendario UTC de `finished_at` del trabajo completado (metadato ya visible en historial). No inventar calendario de local comercial. Limitación documentada: no es el día civil del local si el video no trae reloj de pared.
- **Horario**: franjas a partir del tiempo del video (buckets/`start_seconds` ya usados en flujo/pico), nunca `created_at`/`finished_at` de procesamiento.
- **Zona**: columnas = nombre de zona dentro de la misma `registered_camera_id`; contraste de cifras de ese local entre sesiones de esa cámara.

Si un eje no tiene ≥2 grupos/sesiones comparables → no disponible, sin ranking inventado.

**Rationale**: FR-004 y clarificaciones de horario/zona.

**Alternatives considered**: Exigir wall-clock en el archivo para «día». Se rechaza: el producto no lo garantiza.

## R7 — Pruebas

**Decision**: pytest unitario del ensamblado (disponibilidad, diferencias, insights, elegibilidad). Contrato API del `POST`. Vitest del selector/pantalla de comparación. Regresión: métricas/funnel/patrones/possible-purchases/chat sin cambio de cuerpo. Sin GPU ni video real.

**Rationale**: Constitución VII; SC-001–007.
