# Contract: Evidencia de validación

## Ubicación

- Local (puede contener detalle no versionable): `specs/003-validacion-modelo-azure/validation/`
- Resumen anonimizado versionable: `validation/README.md` y/o `summary.json`

## Contenido mínimo del resumen

```json
{
  "checked_at": "ISO-8601",
  "access_status": "available|blocked|not_evaluated",
  "service_kind": "azure_ai_foundry",
  "region": "string|null",
  "deployment_name": "string|null",
  "model_name": "string|null",
  "model_selection_notes": "string|null",
  "auth_method": "api_key",
  "simple_call": { "ok": true, "latency_ms": 0 },
  "tool_calling_status": "demonstrated|not_supported|not_evaluated",
  "runs_policy": "minimal",
  "quotas_costs": "string or not_measured",
  "sc_003_within_5_min": true,
  "limitations": ["..."],
  "commands": ["..."]
}
```

## Prohibido en Git

- API keys, tokens, `.env` real
- Cabeceras `Authorization`
- Prompts/respuestas que filtren secretos
