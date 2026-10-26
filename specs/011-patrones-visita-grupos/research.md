# Research: Patrones de visita y grupos estimados

Decisiones para cerrar el plan. No quedan `NEEDS CLARIFICATION`.

## R1 — Un área es un polígono ya configurado

**Decision**: Un área es un polígono de la escena con la que se analizó la sesión: el par `(shop_id, zone_role)`. El rol guardado usa el vocabulario de los hechos, `front`, `interior` o `window`. En pantalla, `window` se lee «vidriera». No se crea un identificador nuevo de área y no se compara el rol del hecho con `ZoneRole.SHOWCASE` (`showcase`), que es el nombre del editor.

La transición sigue la aclaración del 2026-10-24. Mientras el pie está en dos o más áreas, esa presencia no alarga la secuencia. El paso se anota en el fotograma en que la visita deja un área y, sin una pausa de más de 1 segundo de video, queda en otra. Si al soltar la primera queda en una sola, esa es la siguiente. Si todavía queda en varias, la secuencia espera a que quede una. Volver a la misma área, sin haber quedado en otra, no la repite. Dos áreas seguidas de distinto `shop_id` suman además un cambio de local. Dos áreas del mismo local no lo suman.

Si la visita aparece por primera vez dentro de varias áreas, la secuencia no elige un ganador: empieza cuando el pie queda en una sola.

Una ausencia del identificador de más de 1 segundo de video, o más de 1 segundo fuera de todas las áreas, cierra la secuencia en el último fotograma observado. Una ausencia menor no la cierra y no inventa posiciones en el hueco. El mismo identificador puede abrir otra secuencia después. En el conteo, ese identificador suma una sola vez por cada par ordenado de áreas y una sola vez por cada secuencia, aunque el recorrido se repita.

**Rationale**: La escena ya admite un frente, un interior y una vidriera por local, y specs/004 permite que esos polígonos se superpongan. La aclaración fijó el momento del paso en la salida, no en la entrada simultánea. El corte de 1 segundo es el que ya usa el producto para no unir un identificador que reaparece tarde.

**Alternatives considered**: Tomar la transición en el `zone_enter` de la segunda área aunque el pie siga en la primera. Se rechaza: la aclaración eligió esperar a la salida. Elegir la zona de entrada más reciente cuando hay solape. Se rechaza: inventa un orden que la escena no tiene. Cortar la secuencia en cada fotograma sin detección. Se rechaza: un parpadeo del detector partiría recorridos que el corte de 1 segundo ya conserva.

## R2 — Se cierran en el análisis, con los pies que ya miran los hechos

**Decision**: `vision/visit_patterns.py` recibe, en el mismo recorrido del worker de archivo, el fotograma, el fps y los pies ya normalizados que `SceneEventRecorder.observe` usa para emitir `zone_enter` y `zone_exit`. Al terminar el video arma transiciones, secuencias, cambios de local y episodios de grupo. No lee `trajectory.jsonl`, no llama a `position_samples` y no guarda un pie por visita y por fotograma. `scene_events` no se reescribe. La muestra del mapa de calor sigue escribiéndose cada cinco fotogramas para specs/009 y no entra en este cálculo.

El worker llama a la persistencia en la misma transacción que ya cierra los hechos y el funnel, antes de pasar el trabajo a `completed`. Un trabajo de webcam no entra a ese recorrido y no deja filas.

**Rationale**: La aclaración del 2026-10-26 eligió las observaciones del análisis. specs/005 guarda solo una muestra y prohíbe un archivo permanente por persona y por instante. Con un pie cada cinco fotogramas, a 30 fps, no se pueden reconstruir 2 segundos ni un ángulo de 45 grados.

**Alternatives considered**: Calcular después desde la muestra del mapa. Se rechaza por la aclaración y porque la muestra no es cada instante. Guardar la trayectoria completa para calcular en la consulta. Se rechaza: es el archivo que specs/005 prohíbe, y el tramo del resultado podría volver a calcular.

## R3 — Qué se guarda

**Decision**: Se guarda el resultado, no el recorrido crudo.

- Transiciones de áreas: par ordenado y cantidad de identificadores distintos.
- Secuencias: la cadena ordenada de áreas y la cantidad de identificadores distintos que la tuvieron.
- Cambios de local: par ordenado de locales y cantidad de identificadores distintos.
- Grupos: cada episodio confirmado, con inicio y fin en tiempo de video e identificadores miembros. Un grupo de dos segundos que el video corta al final llega hasta el último fotograma observado.

Si hay al menos un polígono, las tres listas existen aunque estén vacías: cero es un conteo disponible. Si la escena de ese análisis no tiene ningún polígono, las tres quedan no disponibles con motivo `no_areas` y no se inventan filas. Los grupos siguen si esa escena existe: cero grupos es disponible. Quitar o cambiar `trajectory.jsonl` no modifica estas filas.

**Rationale**: La pantalla pide las transiciones, las secuencias, los cambios de local y los grupos de toda la sesión. Guardar episodios de grupo hace comprobable el contraste. Guardar cada pie no hace falta para volver a leer el mismo número.

**Alternatives considered**: Guardar cada secuencia intermedia de cada visita y contar al leer. Se rechaza para las transiciones y las secuencias: el número visible es el de identificadores distintos, y ese ya puede cerrarse al completar. Un grupo sí necesita su intervalo, porque dos episodios de las mismas visitas son dos grupos.

## R4 — Dirección y visita quieta

**Decision**: La dirección es el desplazamiento del pie, en píxeles, desde la observación anterior de ese identificador. No es la mirada ni el vector entre el primer y el último pie del episodio. El ángulo entre dos visitas es el ángulo entre esos dos vectores. Hace falta que los dos tengan dirección en ese paso.

Una visita no tiene dirección cuando ese desplazamiento es menor que 0,005 del ancho del encuadre. Ese corte no se muestra junto a los tres umbrales de la spec. Se guarda en la fila del análisis para que una segunda corrida use el mismo valor. En el fotograma de prueba de 320 píxeles equivale a 1,6 píxeles. Un pie quieto, como el del detector falso cuando no se mueve, queda por debajo. Un paso que cruza el encuadre queda por encima.

Los tres umbrales visibles siguen siendo 0,08 del ancho, 45 grados y 2 segundos de video. La distancia es euclídea, en píxeles, y se compara contra `0,08 × ancho`. El reloj es `(fotograma final − fotograma inicial) / fps` del video.

**Rationale**: La spec deja «casi no se mueve» sin un número. Hace falta uno para que el caso sintético no dependa del ruido del tracker. Mostrar un cuarto umbral agregaría una cifra que FR-011 no pide.

**Alternatives considered**: Cualquier desplazamiento distinto de cero. Se rechaza: un píxel de temblor contaría como compañía. Usar solo el desplazamiento neto de los 2 segundos. Se rechaza: la spec pide que la dirección se mantenga durante ese tramo, no un vector único de punta a punta.

## R5 — Quiénes forman el grupo

**Decision**: En cada observación se arma el grafo de pares que cumplen distancia y ángulo. Un conjunto de dos o más visitas es candidato cuando cada par del conjunto está en ese grafo. El episodio se confirma si ese mismo conjunto se sostiene, sin un hueco de más de 1 segundo entre observaciones y sin un fotograma que rompa una condición, durante al menos 2 segundos de video. Una tercera visita que se acerca a una sola no entra.

Si una visita cumple a la vez dos conjuntos, queda en el que empezó antes. Si empezaron en el mismo fotograma, queda en el de más integrantes. Si también empatan en tamaño, queda en el conjunto cuyo identificador más chico sea menor. El otro conjunto la pierde en ese instante. Si al perderla le quedan menos de dos visitas, ese episodio no sigue con ella. Un conjunto que se desarma y vuelve a cumplir los tres umbrales durante otros 2 segundos es otro episodio.

Si el video termina y el episodio ya llegó a 2 segundos, el fin es el último fotograma en que se los observó juntos. Si no llegó, no se confirma. El rótulo de cada episodio es estimación.

En una escena de pocos locales la cantidad de visitas simultáneas es chica. El módulo enumera esos conjuntos en memoria y no guarda el grafo.

**Rationale**: FR-006 pide que todos los pares cumplan, no una cadena. FR-008 pide un solo grupo por instante y un episodio nuevo después de una ruptura. El desempate por identificador solo cubre el caso que la spec no alcanza a separar, y deja el resultado repetible.

**Alternatives considered**: Unir por proximidad a un solo compañero. Se rechaza: la spec deja afuera a quien queda lejos de alguno. Elegir el grupo al azar en el empate. Se rechaza: la segunda corrida no devolvería los mismos integrantes.

## R6 — Lectura, webcam, tramo y cifras que no se tocan

**Decision**: La lectura es `GET /sessions/{session_id}/visit-patterns`. No lleva `shop_id` ni acepta `from_seconds` o `to_seconds`. Un parámetro extra no cambia el cuerpo. Responde `404` si la sesión no existe. Responde `409` `result_incomplete` si no hay un análisis completado. Responde `409` `live_patterns_unavailable` si el origen es webcam, y en ese caso no hay filas. `synthetic` y `video_file` se leen: el sintético es el sustituto de archivo de la suite.

No se agregan códigos a `shop_metric_code` ni campos al cuerpo de métricas. `get_session_figures` sigue ofreciendo las cinco cifras de specs/008. El funnel de specs/010 no recibe estas secuencias. Estar en el interior o en la vidriera dentro de una secuencia no es exposición, detención, atención ni entrada oficial.

La pantalla de resultados de archivo pide este recurso una vez por sesión. Cambiar de local o de tramo no lo vuelve a pedir. La vista en vivo no lo muestra.

**Rationale**: El patrón es de la cámara y de toda la sesión. Colgarlo del local o del endpoint de métricas lo mezclaría con cifras que esta feature tiene prohibido cambiar. El código de error de la webcam es propio: `live_funnel_unavailable` pertenece al funnel.

**Alternatives considered**: Un endpoint por local. Se rechaza: un cambio de local partiría un recorrido que cruza dos locales. Reutilizar el `409` del funnel. Se rechaza: el cliente no podría distinguir qué bloque falta.

## R7 — Contraste manual

**Decision**: Queda fuera de pytest, Vitest y Playwright, en `validation/` de esta carpeta, con el protocolo de diferencias de specs/001. El estado inicial es «no ejecutado». La suite usa pies sintéticos. Hasta ese informe, el bloque dice que la precisión de los patrones y de los grupos estimados no está comprometida. `precision_uncommitted` queda en `true`.

**Rationale**: FR-012 pide el contraste y permite dar por válidas las otras historias sin el clip. El aviso es una frase de la interfaz, no un interruptor por sesión.

**Alternatives considered**: Exigir el clip real en CI. Se rechaza: el material elegido no está en el repositorio y la spec lo deja fuera del recorrido habitual.
