# Contract: Configuración Azure AI Foundry

## Variables de entorno (propuestas)

Nombres ajustables al SDK aprobado; `.env.example` los lista **sin** valores secretos.

| Variable | Obligatoria para validación | Descripción |
|---|---|---|
| `FLOWSIGHT_AZURE_AI_ENDPOINT` | sí | Endpoint del proyecto Foundry (p. ej. `…/api/projects/<proyecto>`) |
| `FLOWSIGHT_AZURE_AI_API_KEY` | sí | API key; solo `.env` local |
| `FLOWSIGHT_AZURE_AI_DEPLOYMENT` | sí | Deployment/modelo (p. ej. `gpt-5-mini`) |
| `FLOWSIGHT_AZURE_AI_API_VERSION` | según SDK | Si el cliente lo requiere (`v1` en Foundry OpenAI-compatible) |
| `FLOWSIGHT_AZURE_AI_REGION` | no | Para evidencia |
| `FLOWSIGHT_AZURE_AI_MODEL` | no | Nombre comercial si difiere del deployment |
| `FLOWSIGHT_AZURE_AI_MODEL_NOTES` | no | Motivo de elección |
| `FLOWSIGHT_AZURE_OPENAI_ENDPOINT` | no | Atajo OpenAI v1 (`…openai.azure.com/openai/v1`) |
| `FLOWSIGHT_AZURE_AI_RESPONSES_URL` | no | URL completa de Responses API (documentación) |

## Reglas

- Auth de esta Feature: **solo API key** (no Entra ID).
- El script falla en seco si faltan obligatorias; mensajes sin eco de secretos.
- API/worker de producto **no** exigen estas variables para arrancar.
- La clave del proyecto compartido se reparte **fuera de Git**.
- No versionar `.env`, capturas con keys ni exports sensibles del portal.
