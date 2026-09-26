# Contract: Herramienta ficticia `get_session_traffic`

## Propósito

Validar tool/function calling sin métricas reales ni PostgreSQL.

## Firma

- **Nombre**: `get_session_traffic`
- **Parámetros**: `session_id` (string, requerido)

## Comportamiento

| `session_id` | Resultado |
|---|---|
| `demo-session-001` | `{ "found": true, "session_id": "demo-session-001", "total_entries": 42, "peak_hour": "15:00-16:00" }` |
| otro | `{ "found": false, "session_id": "<id>", "total_entries": null, "peak_hour": null }` |

## Ciclo esperado (script local)

1. Prompt de prueba pide tráfico de `demo-session-001`.
2. Modelo solicita `get_session_traffic`.
3. Backend ejecuta la función hardcodeada.
4. Backend reenvía el resultado al modelo.
5. Modelo responde usando esos datos.

## Fuera de contrato

- PostgreSQL, APIs de analytics del producto, SQL del modelo.
- Endpoint HTTP que exponga la tool.
- Más de las corridas mínimas de evidencia.
