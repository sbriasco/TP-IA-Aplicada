# Contraste manual: posible compra estimada

**Estado**: no ejecutado

**Material**: clip del corpus elegido por el equipo (no versionado). Si el material no deja marcar bolsas de forma unívoca, el ensayo lo dirá y no se afirmará coincidencia.

## Protocolo

Seguir el protocolo de diferencias de specs/001 (detección faltante, espuria, pérdida de track, oclusión, duplicado u otro). Sobre un clip del material elegido:

1. Anotar a mano las bolsas visibles (backpack, handbag, suitcase) y a qué visita se atarían por solape exclusivo de recuadro (área > 0 con exactamente una persona).
2. Comparar con `visit_count` y los `track_ids` del resultado de esa sesión (`GET /sessions/{id}/possible-purchases`).
3. Clasificar cada diferencia. No afirmar exactitud ni una venta.
4. Si el material no deja marcar bolsas de forma unívoca, dejar escrito que la evidencia no alcanza.

Este contraste no entra en pytest, Vitest ni Playwright ni bloquea el merge de código. Hasta ejecutarlo, la pantalla dice que la precisión no está comprometida. Ejecutarlo (o declarar evidencia insuficiente) es requisito para cerrar Feature #9 en Azure Boards (SC-002 capa 2 / SC-007).
