# Evidencia — Feature #5 (Azure AI Foundry)

Resumen anonimizado versionable: [`summary.json`](./summary.json).

## Resultado (2026-09-26)

| Paso | Estado |
|---|---|
| Acceso / inventario | `available` (`gpt-5-mini`, región `brazilsouth`, API key) |
| Llamada simple | `ok` (~4 s; SC-003 cumplido); cliente exige texto no vacío |
| Tool calling | `demonstrated` con `get_session_traffic` / `demo-session-001` |
| Cuotas/costos | `not_measured` |
| SDK | `openai==1.109.1` (OpenAI-compatible contra Foundry) |

## Cómo repetir

1. Completar `FLOWSIGHT_AZURE_AI_*` en `.env` (ver `.env.example`), incluida `FLOWSIGHT_AZURE_AI_REGION=brazilsouth`.
2. `.\scripts\validate-azure-model.ps1 -Step all`
3. Pruebas sin Azure: `pytest -q tests/unit -k llm` desde `backend/`.

No versionar drafts crudos ni `.env`. Plantilla: `summary.template.json`.
