# Research: Exposición, detención, atención estimada y funnel comercial

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`.

## R1 — La exposición no es un hecho nuevo

**Decision**: La etapa de exposición lee las filas `scene_events` ya definidas por specs/006 con `kind=zone_enter` y `zone_role=window`. En el modelo, la vidriera del editor se persiste como `window`. No se agrega un `kind` de exposición ni se borra ni se reescribe ninguna entrada de zona. Si el pie oscila en el borde y quedan varias entradas, el funnel cuenta el `track_id` una sola vez. La ventana de oscilación de `vision/spatial.py` sigue aplicando solo a la línea de entrada.

**Rationale**: La aclaración del 2026-10-23 eligió la entrada de zona existente. specs/006 ya emite `zone_enter` de vidriera en el mismo recorrido del worker y prohíbe que esa zona genere permanencia u ocupación.

**Alternatives considered**: Un segundo hecho de exposición. Se rechaza: duplica el ingreso en la lista de hechos. Reemplazar `zone_enter` de vidriera. Se rechaza: cambia el contrato de specs/006.

## R2 — La detención es un hecho nuevo; la atención no

**Decision**: Al salir de la vidriera sin perder el identificador, si la estadía dura al menos 3 segundos de video, se inserta `scene_events.kind=showcase_stop`, `zone_role=window` y `duration_seconds`. Menos de 3 segundos no inserta detención. Si el video termina con el pie adentro, o el identificador desaparece adentro, no se inserta. La atención estimada no tiene hecho propio: es una detención cuya `duration_seconds` es de al menos 8 segundos. Varias detenciones del mismo identificador se guardan; el funnel lo cuenta una vez en detención si alguna cumple 3 segundos y una vez en atención si alguna cumple 8.

**Rationale**: specs/006 reserva `dwell` para la zona frontal (`ck_scene_events_dwell_front`). Reusar `dwell` en la vidriera mezclaría la permanencia observable. La atención es un umbral sobre la misma estadía, no otra visita.

**Alternatives considered**: Guardar la atención como otra fila. Se rechaza: es el mismo hecho con otro corte. Calcular la detención solo en la consulta. Se rechaza: FR-001 pide un hecho de la sesión, con instante de video, generado al completar.

## R3 — Reloj de la estadía

**Decision**: La duración es `(fotograma de salida − fotograma de entrada) / fps` del video, igual que el `dwell` frontal de specs/006. El instante guardado es el de la salida. El inicio de la atención es ese instante menos la duración. No se usa el reloj de la computadora ni el tiempo de procesamiento.

**Rationale**: El worker ya mide la permanencia frontal así. Un segundo reloj haría que 3 y 8 segundos no coincidan con el video que ve el analista.

**Alternatives considered**: Diferencia de `video_timestamp_seconds` de las dos entradas de zona. Se rechaza en este incremento: el `dwell` actual no hace eso y conviene un solo criterio.

## R4 — Conteos del funnel, aparte de las ocho métricas

**Decision**: Migración `0014_shop_funnel`. Tablas `shop_funnels`, `shop_funnel_stages` y `shop_funnel_rates`. No se agregan códigos a `shop_metric_code`. `GET /sessions/{id}/shops/{shop_id}/metrics` no cambia de forma. El chat sigue llamando a `get_session_figures` con las cinco cifras de specs/008.

Al completar un análisis que no es webcam:

- Paso observado: `track_id` distintos con al menos un `zone_enter` de `front`. Incluye a quienes después entraron. No es `store_pass`.
- Exposición: de esos, los que además tienen al menos un `zone_enter` de `window`.
- Detención: de la exposición, los que tienen al menos un `showcase_stop`.
- Atención estimada: de la detención, los que tienen un `showcase_stop` de al menos 8 segundos. Rótulo de estimación.
- Ingreso vinculado: de la atención, los que tienen un `store_enter` del mismo local cuyo instante es posterior al inicio de la atención. Si hay varias detenciones de 8 segundos o más, el inicio es el de la más temprana. Las entradas oficiales de `analysis_measures` no se tocan.
- Excluidas: `track_id` con `zone_enter` de `window` y sin `zone_enter` de `front`. No entran en la exposición. El número se muestra aparte.
- Tasas, en este orden y con estos códigos: `observed_pass_to_exposure`, `exposure_to_stop`, `stop_to_attention`, `attention_to_linked_entry`. Ninguna se llama `entry_rate`. Si la etapa anterior es 0, la tasa queda no disponible con motivo `no_previous_stage`.
- Sin polígono de vidriera: exposición, detención, atención e ingreso vinculado quedan no disponibles con motivo `no_showcase`. El paso observado se calcula igual. Las tasas que salen de una etapa no disponible también quedan no disponibles.

Los umbrales 3 y 8 se guardan en `shop_funnels` para que la pantalla muestre los que se usaron. El aviso de precisión no comprometida es fijo en esta feature: el contraste manual no enciende ni apaga una fila.

**Rationale**: Meter las etapas en `shop_metrics` las entregaría a la misma consulta que el tablero y el chat. specs/008 solo admite cinco cifras y la aclaración prohíbe reutilizar el nombre tasa de ingreso.

**Alternatives considered**: Ampliar `ShopMetricCode`. Se rechaza por el aislamiento de la consulta. Recalcular el funnel al elegir un tramo. Se rechaza: la aclaración lo fija a toda la sesión.

## R5 — Cuándo se calcula y quién lo lee

**Decision**: `vision/funnel.py` es una función pura sobre los hechos ya armados en memoria al completar. No lee SQL ni el video. El worker la llama en la misma transacción que pasa el trabajo a `completed`, junto con specs/006. `services/funnel.py` persiste y lee. La API solo lee.

`GET /sessions/{session_id}/shops/{shop_id}/funnel` exige un trabajo `completed` con `result_complete=true` y `source_kind` distinto de `webcam`. Si el análisis no está completado, `409` `result_incomplete`. Si la sesión es webcam, `409` `live_funnel_unavailable` y no se calculan filas. `synthetic` entra: es el sustituto de archivo que ya usa la suite. El pedido no acepta `from_seconds` ni `to_seconds`.

La pantalla de resultados de archivo pide el funnel una vez por local. Cambiar el tramo no vuelve a pedirlo. La pantalla de webcam y la vista mientras el análisis corre no lo muestran. El chat no gana una herramienta.

**Rationale**: specs/009 prohíbe métricas comerciales en vivo. specs/007 fija los ocho indicadores al recortar el tramo. Un parámetro de tramo en este endpoint invitaría a recalcular.

**Alternatives considered**: Calcular el funnel en el navegador con la lista de hechos. Se rechaza: el tramo filtra esa lista y el funnel dejaría de ser el de toda la sesión. Reusar el endpoint de métricas con un campo opcional. Se rechaza: el chat y el tablero leen ese cuerpo.

## R6 — Contraste manual

**Decision**: Queda fuera de pytest, Vitest y Playwright, en `validation/` de esta carpeta, con el protocolo de diferencias de specs/001. La suite usa hechos sintéticos. Hasta ese informe, el panel dice que la precisión no está comprometida. Completar el informe no borra el aviso por sí solo.

**Rationale**: FR-015 pide el contraste y a la vez permite validar el resto sin el clip. El aviso es una frase de la interfaz, no un estado de base.

**Alternatives considered**: Un flag por sesión que oculte el aviso. Se rechaza: el contraste es del equipo sobre un clip, no una propiedad de cada análisis.
