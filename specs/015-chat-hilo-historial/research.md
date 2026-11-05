# Research: Hilo de chat e historial

## R1 — Persistencia PostgreSQL vs solo localStorage

**Decision**: Tablas en PostgreSQL.  
**Rationale**: Sobrevive recarga; alineado al stack; historial pedible desde cualquier cliente del mismo entorno.  
**Alternatives**: Solo localStorage (se pierde entre máquinas; no cumple “historial” de producto).

## R2 — Alcance del historial

**Decision**: Lista por `session_id` en el panel de resultados (opción C acotada).  
**Rationale**: Encaja el flujo de FlowSight; evita app global sin auth.  
**Alternatives**: Página global tipo ChatGPT (más UI, menos anclaje a la sesión).

## R3 — Historial al modelo

**Decision**: Enviar últimos 20 mensajes de texto al drafter; figures solo del turno.  
**Rationale**: Seguimientos NL; post-filtro rechaza números no respaldados.  
**Alternatives**: Reenviar todas las figures históricas (riesgo de citar cifras viejas como actuales).

## R4 — Zona al cambiar

**Decision**: Hilo lleva `shop_id`; si el panel cambia de zona y el hilo activo es de otra, se deselecciona (no se usa como contexto).  
**Rationale**: Spec US2 AC5 / aislamiento.
