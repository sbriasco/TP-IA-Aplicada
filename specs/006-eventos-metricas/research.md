# Research: Eventos espaciales, métricas y persistencia

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`.

## R1 — De dónde salen los hechos

**Decision**: Entrada y salida del local no se vuelven a calcular. Son los `line_crossings` con `disposition=confirmed` del análisis completado. La oscilación ya guardada no se promueve a hecho. Zona (frontal, interior o vidriera), paso frente al local y permanencia de la zona frontal se deciden en el mismo recorrido de fotogramas del worker, con el pie ya usado por specs/005, y se escriben en PostgreSQL solo al pasar el trabajo a `completed`. El JSONL cada 5 fotogramas no es la fuente: esa muestra pierde un paso o una estadía corta.

**Rationale**: La spec pide hechos después de un análisis completado y, a la vez, que entradas y salidas sean los números oficiales. Releer el video volvería a detectar. Releer el JSONL cambiaría el cruce que specs/005 ya cerró a fotograma completo.

**Alternatives considered**: Un segundo pase sobre `trajectory.jsonl`. Se rechaza: el muestreo es cada 5 fotogramas. Reprocesar el video al consultar. Se rechaza: el chat y el tablero no calculan desde el video.

## R2 — Qué se persiste

**Decision**: Migración `0005_scene_metrics`. Tabla `scene_events` (un hecho, no un fotograma) y tabla `shop_metrics` más `traffic_buckets` para el flujo. No se agranda `analysis_measures`: su `value` es entero y sus tres códigos siguen siendo la fuente oficial de entradas, salidas y ocupación visible. `shop_metrics` copia esos tres números al completar; un test exige que coincidan. Trabajos ya `completed` antes de esta feature no se rellenan: las métricas que dependen de hechos nuevos quedan no disponibles con motivo `metrics_not_generated`.

**Rationale**: Mezclar medias en segundos dentro de una columna entera rompe el contrato de specs/005. No reabrir videos viejos evita un segundo análisis.

**Alternatives considered**: Añadir códigos al enum `measure_code` y cambiar `value` a numérico. Se rechaza: altera las filas oficiales ya cerradas. Guardar cada pie. Se rechaza: specs/005 prohíbe una fila por instante.

## R3 — Las ocho métricas y el horario pico

**Decision**: Por local, al completar:

- Tráfico total: identificadores temporales distintos con al menos un pie en la zona frontal. Rótulo de estimación de visitas. No es una persona única.
- Flujo: intervalos de 60 s de video desde el inicio. Cada identificador cuenta una sola vez, en el intervalo de su primer pie en esa zona frontal. La suma de los intervalos es el tráfico. Si el video dura menos de 60 s, hay un solo intervalo.
- Horario pico: el intervalo con mayor tráfico; en empate, el de inicio más temprano. Sin fecha real, es un tramo de la grabación.
- Paso: identificador con pie en la zona frontal y sin entrada confirmada a ese local.
- Entradas, salidas y ocupación visible: copia de `analysis_measures` con `partial=false`.
- Tasa de ingreso: entradas oficiales / pasos. Si los pasos son 0, no disponible. No es entradas por hora.
- Permanencia observable: media y mediana, en segundos de video, de las estadías de zona frontal que se cerraron porque el mismo identificador salió de la zona sin desaparecer. Si no hay ninguna, no disponible. Interior y vidriera no entran.

**Rationale**: La aclaración del 2026-09-30 fija la zona frontal. FR-010 exige que la suma del flujo sea el tráfico, así que el identificador no puede contarse en dos minutos. FR-008 prohíbe otro cálculo de las tres medidas oficiales.

**Alternatives considered**: Tráfico de toda la sesión repetido en cada local. Se rechaza: FR-006 pide la medida por local y un pasillo con dos vidrieras mezclaría visitas. Permanencia en cualquier zona. Se rechaza: la aclaración y specs/004.

## R4 — Consulta

**Decision**: `GET /sessions` no cambia de forma y no embebe métricas de otra sesión. Nuevos: `GET /sessions/{session_id}/shops/{shop_id}/metrics` y `GET /sessions/{session_id}/events` con `shop_id` opcional y `from_seconds` / `to_seconds` sobre el instante del video (intervalo semiabierto). Solo un trabajo `completed` con `result_complete=true` de esa sesión. Si el último análisis no está completado, `409` con `result_incomplete` y sin las ocho cifras como finales. El mismo servicio es el que el chat usará; esta feature no llama al modelo.

**Rationale**: El tablero y el chat tienen que leer lo mismo. El listado de sesiones ya existe en specs/002.

**Alternatives considered**: Devolver métricas parciales con el mismo cuerpo que las finales. Se rechaza: la spec prohíbe presentarlas como resultado completo. Un endpoint distinto para el chat. Se rechaza: FR-012 pide las mismas cifras.

## R5 — Contraste manual

**Decision**: No hay pantalla ni prueba automática que exija un conteo a mano. El contraste de entradas, salidas y pasos de al menos un clip queda en `specs/006-eventos-metricas/validation/` cuando el equipo lo haga, con el protocolo de diferencias del experimento 001. La suite usa un caso sintético con resultado calculado a mano.

**Rationale**: La historia #64 es P2 y la spec dice que el recorrido de prueba no depende de ese clip.

**Alternatives considered**: Bloquear CI hasta tener el conteo manual. Se rechaza: el material real no está en el repositorio y SC-006 lo separa del resto.
