# Research: Dashboard e historial

## R1 — De dónde sale cada fila del historial

**Decision**: Un GET nuevo, `GET /processed-sessions`, arma una fila por sesión que ya tiene al menos un análisis. Lee la sesión, el video, el análisis más reciente y el número de la versión de escena usada. No hay tabla nueva y `GET /sessions` no cambia.

**Rationale**: El listado actual tiene nombre, cámara, tipo y fecha de alta. No tiene video, estado, fecha de procesamiento, motivo ni versión usada. Pedir el detalle de cada sesión desde la pantalla haría una consulta por fila. El alta de video sigue en la pantalla que ya existe.

**Alternatives considered**: Embebido en `GET /sessions` (specs/006 dejó ese listado sin métricas y specs/002 fijó su forma). Un cálculo nuevo de métricas para el historial (la fila no las necesita).

## R2 — Qué pantalla abre el historial

**Decision**: La fila abre `/sessions/{id}/results`. La pantalla de la sesión sigue sirviendo para cargar el video, editar la escena e iniciar el análisis.

**Rationale**: La spec pide un paso desde el historial hasta los resultados. Mezclar los gráficos en la pantalla de configuración la vuelve el alta y el tablero a la vez.

**Alternatives considered**: Reemplazar el detalle de la sesión. Poner los gráficos en la vista en vivo del análisis.

## R3 — Parciales y cifras finales no salen del mismo pedido

**Decision**: Si el análisis más reciente no está completado con resultado completo, la pantalla pide `GET /jobs/{id}/measures` y muestra solo entradas, salidas y ocupación visible, marcadas como parciales. Tráfico, pasos, tasa, permanencia y horario pico no se pintan. Si está completado, pide `GET /sessions/{id}/shops/{shop_id}/metrics` y no vuelve a leer las medidas parciales como si fueran otras cifras. Un análisis fallido o cancelado muestra `failure_message` y no los ocho indicadores.

**Rationale**: El pedido de métricas ya responde `409 result_incomplete` cuando el análisis más reciente no cerró bien. Las tres medidas parciales ya existen en el análisis. Inventar las otras cinco a mitad de camino contradice la aclaración del 2026-09-30.

**Alternatives considered**: Tratar el `409` como pantalla de error y ocultar también las tres parciales. Mostrar las ocho con valor vacío mientras corre.

## R4 — El tramo no recalcula los ocho indicadores

**Decision**: Cambiar de local cambia el pedido de métricas. Cambiar el tramo solo filtra, en el navegador, los minutos ya recibidos que se solapan con el tramo, y pide los hechos con `from_seconds` y `to_seconds`. Cada minuto se muestra entero. Los ocho indicadores quedan los del pedido, que ya son los de toda la sesión.

**Rationale**: specs/006 guarda las ocho métricas y el flujo de toda la sesión. El intervalo de esa consulta solo filtra hechos. Un minuto partido sería una cifra que no está guardada.

**Alternatives considered**: Un query `from_seconds` en el pedido de métricas. Recalcular tráfico o tasa en el navegador a partir de los hechos.

## R5 — Mapa de calor

**Decision**: No bloquea el historial ni los indicadores. Si se hace, `GET /jobs/{id}/position-samples` lee el JSONL que specs/005 ya escribió y devuelve solo los pies normalizados. Si el archivo no está en este equipo, responde muestra no disponible y la pantalla explica el vacío. El mapa se dibuja sobre el frame de referencia, que ya se sirve aunque el video falte. No se calculan métricas desde esa muestra.

**Rationale**: El JSONL no sale hoy por la API. El navegador no puede leer el disco del servidor. La spec deja el mapa fuera del camino crítico.

**Alternatives considered**: Mandar el archivo entero al navegador. Dibujar el mapa solo si el video está en este equipo.

## R6 — Gráfico

**Decision**: Instalar Recharts `3.10.1`, ya elegido en las decisiones técnicas y compatible con React 19. Un gráfico de barras para el flujo. El mapa, si entra, es SVG sobre el frame, sin otra librería. Los rótulos van en texto: parcial, estimación de visitas, visible, observable y no disponible.

**Rationale**: El stack ya lo fijó. No está en `package.json`. El color solo no alcanza para distinguir una estimación de una observación.

**Alternatives considered**: Un gráfico dibujado a mano. Otra librería de charts.
