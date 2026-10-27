# Research: Evaluación de posible compra

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`.

## R1 — Qué cuenta como bolsa

**Decision**: Una bolsa observada es un recuadro de una de estas tres clases del detector COCO ya usado por Ultralytics: `backpack`, `handbag` y `suitcase`. No tiene identificador de seguimiento propio. No se inventa una clase nueva ni se pide un peso aparte. El detector falso de la suite emite esos recuadros en los casos de prueba. Otras clases (persona, botella, etc.) no cuentan.

**Rationale**: La Feature #9 pide una bolsa visible, no un producto identificado. Esas tres clases son las que el modelo ya puede marcar como contenedores portátiles. Un peso nuevo rompería el entorno reproducible de la constitución.

**Alternatives considered**: Solo `handbag`. Se rechaza: deja afuera mochilas y valijas visibles en el material comercial. Entrenar un detector de bolsas propio. Se rechaza: fuera de alcance y de las dependencias ya fijadas. Usar el pie de la persona como si llevara bolsa. Se rechaza: la aclaración exige un recuadro de bolsa.

## R2 — Solape exclusivo con exactamente una visita

**Decision**: En cada fotograma, una bolsa se ata a una visita solo si el área de intersección de los dos recuadros axis-aligned es mayor que cero y el recuadro de esa bolsa no se solapa con el de ninguna otra visita. Si se solapa con dos o más, o con ninguna, esa bolsa no suma en ese fotograma. No se elige la más cercana. No se usa el pie ni un umbral de distancia.

El tiempo acumulado de una visita es la duración de video de los fotogramas en los que tuvo al menos un solape exclusivo, unidos si el hueco entre dos tramos útiles es de a lo sumo 1 segundo de video. El reloj es `(fotograma final − fotograma inicial) / fps`. Un hueco mayor, o la pérdida del identificador de la visita, cierra el tramo sin inventar solapes. Si el tramo cerrado dura al menos 1 segundo de video, esa visita cuenta una vez en la sesión. Si el video termina y el tramo ya llevaba 1 segundo, se conserva hasta el último fotograma observado.

**Rationale**: La aclaración del 2026-10-26 eligió el solape exclusivo. El corte de 1 segundo es el mismo que ya usa el producto para no unir un identificador que reaparece tarde.

**Alternatives considered**: Distancia al pie. Se rechaza por la aclaración. Compartir identificador de seguimiento entre bolsa y persona. Se rechaza: el tracker actual no une clases distintas. IoU mínimo de 0,3. Se rechaza: un solape parcial visible ya es evidencia; un umbral extra no está en la spec.

## R3 — Se cierra en el mismo análisis

**Decision**: `vision/possible_purchase.py` recibe, en el mismo recorrido del worker de archivo, el fotograma, el fps, las detecciones de persona (con `track_id` y recuadro) y los recuadros de bolsa del mismo instante. Al terminar el video arma el conjunto de visitas que cumplieron 1 segundo de solape exclusivo. No lee `trajectory.jsonl`, no llama a `position_samples` y no guarda un recuadro por visita y por fotograma. `scene_events`, el funnel y los patrones no se reescriben.

El worker llama a la persistencia en la misma transacción que ya cierra hechos, funnel y patrones, antes de pasar el trabajo a `completed`. Un trabajo de webcam no entra a ese recorrido y no deja filas.

El contrato del detector se amplía solo lo necesario: además de las personas, el mismo fotograma puede aportar recuadros de bolsa sin `track_id`. El detector falso los emite en los tests. Ultralytics filtra las tres clases de R1 sin alterar el seguimiento de personas. No se toca `spatial.py` ni `events.py`.

**Rationale**: La aclaración eligió el mismo análisis. Una segunda pasada reabriría el video solo para esta cifra.

**Alternatives considered**: Calcular después en otra pasada. Se rechaza por la aclaración. Guardar cada solape por fotograma. Se rechaza: es el archivo permanente por instante que specs/005 prohíbe.

## R4 — Qué se guarda

**Decision**: Se guarda el resultado, no el video de bolsas.

- Informe por trabajo: umbral `1` segundo, cantidad de visitas que cumplieron, `precision_uncommitted` en verdadero, disponibilidad siempre `available` cuando el análisis de archivo completó (cero es un conteo).
- Integrantes: cada `track_id` que contó una vez. Sirve al contraste y a una segunda corrida idéntica. No se guarda el recuadro ni el instante de cada solape.

Quitar o cambiar `trajectory.jsonl` no modifica estas filas.

**Rationale**: La pantalla pide la cantidad y el umbral. Guardar los identificadores hace comprobable el contraste sin un archivo por fotograma.

**Alternatives considered**: Solo el número, sin integrantes. Se rechaza: el contraste a mano no podría decir qué visita coincidió. Guardar cada tramo de solape. Se rechaza: la spec cuenta una vez por visita en la sesión.

## R5 — Lectura, webcam, tramo y cifras que no se tocan

**Decision**: La lectura es `GET /sessions/{session_id}/possible-purchases`. No lleva `shop_id` ni acepta `from_seconds` o `to_seconds`. Un parámetro extra no cambia el cuerpo. Responde `404` si la sesión no existe. Responde `409` `result_incomplete` si no hay un análisis completado. Responde `409` `live_purchase_unavailable` si el origen es webcam, y en ese caso no hay filas. `synthetic` y `video_file` se leen.

No se agregan códigos a `shop_metric_code` ni campos al cuerpo de métricas. `get_session_figures` sigue ofreciendo las cinco cifras de specs/008. El funnel de specs/010 y los patrones de specs/011 no reciben esta cifra. Una entrada, una detención o una atención sin solape exclusivo no cuentan.

La pantalla de resultados de archivo pide este recurso una vez por sesión. Cambiar de local o de tramo no lo vuelve a pedir. La vista en vivo no lo muestra.

**Rationale**: La cifra es de toda la sesión y no se atribuye a un local. Colgarla de métricas o del funnel la mezclaría con cifras que esta feature tiene prohibido cambiar. El código de error de la webcam es propio.

**Alternatives considered**: Un endpoint por local. Se rechaza: la bolsa no se atribuye a un local. Reutilizar `live_patterns_unavailable`. Se rechaza: el cliente no podría distinguir qué bloque falta. Agregar una sexta etapa al funnel. Se rechaza por el análisis cruzado y por FR-005.

## R6 — Contraste manual

**Decision**: Queda fuera de pytest, Vitest y Playwright, en `validation/` de esta carpeta, con el protocolo de diferencias de specs/001. El estado inicial es «no ejecutado». La suite usa recuadros sintéticos. Hasta ese informe, el bloque dice que la precisión de la posible compra estimada no está comprometida. `precision_uncommitted` queda en `true`. Si el material no deja marcar bolsas de forma unívoca, el informe lo dice y no afirma una venta.

**Rationale**: FR-009 pide el contraste y permite dar por válidas las otras historias sin el clip.

**Alternatives considered**: Exigir el clip real en CI. Se rechaza: el material elegido no está en el repositorio.
