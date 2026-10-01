# Quickstart: Chat analítico mínimo

Validación de la feature. No incluye la implementación.

## Precondiciones

- Backend y frontend como en el README. PostgreSQL de test, sin la base compartida de Azure.
- Una sesión completada con cifras ya registradas, la misma que usa el tablero. El detector de prueba alcanza. No hace falta GPU.
- La suite no necesita `FLOWSIGHT_AZURE_AI_API_KEY`.

## Qué tiene que quedar verde

Lecturas, sin modelo, contra [contracts/metric-tools.md](./contracts/metric-tools.md):

```powershell
cd backend
.\.venv\Scripts\pytest tests\unit\test_chat_metrics.py
```

Cada cifra coincide con la ya registrada de ese local para toda la sesión. Una no disponible sigue no disponible. Otra sesión no aparece. Un análisis sin `result_complete` no devuelve las cinco.

Pedido de chat, con redactor falso, contra [contracts/openapi.yaml](./contracts/openapi.yaml):

```powershell
cd backend
.\.venv\Scripts\pytest tests\contract\test_chat_api.py
```

- Todo número de una respuesta contestada está en las lecturas de esa pregunta.
- Una pregunta de compra o de identidad vuelve `refused` y `model_calls` en 0.
- Dos sesiones con el mismo nombre vuelven `needs_clarification`.
- «La última» usa la de `finished_at` más reciente.
- Sin configuración, con el tiempo agotado o con texto vacío, el estado es `error` y un pedido de métricas de esa sesión sigue respondiendo.

Panel, junto al recorrido que ya existe:

```powershell
cd frontend
npm test
npm run test:e2e
```

En resultados se envía una pregunta, se ve espera y después el local, el alcance de toda la sesión y los valores. Al abrir otra sesión el panel queda vacío. Un fallo del chat deja los indicadores en la página.

## Corrida manual, no bloquea

Con el `.env` local de Azure AI Foundry ya usado en specs/003, una pregunta por el tráfico de una sesión completada. La respuesta tiene que citar el mismo valor que el tablero, como estimación de visitas, y no el `42` de la herramienta ficticia. Si el crédito no alcanza, se anota el bloqueo y la feature igual puede darse por válida con la suite de arriba.
