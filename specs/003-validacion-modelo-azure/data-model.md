# Data Model: Validación del servicio de modelo de Azure

Sin tablas PostgreSQL. Artefactos de configuración y evidencia.

## AzureAccessInventory

| Campo | Tipo | Notas |
|---|---|---|
| checked_at | datetime UTC | |
| access_status | enum | `available`, `blocked`, `not_evaluated` |
| block_reason | string nullable | sin secretos |
| service_kind | string | fijo: `azure_ai_foundry` |
| region | string nullable | |
| deployment_name | string nullable | id de deployment en Foundry |
| model_name | string nullable | modelo habilitado (evidencia: `gpt-5-mini`) |
| model_selection_notes | string nullable | motivo (asignación equipo / costo / tools) |
| auth_method | string | fijo en esta Feature: `api_key` |
| tool_calling_status | enum | solo `demonstrated`, `not_supported`, `not_evaluated` |

## ModelCallResult

| Campo | Tipo | Notas |
|---|---|---|
| kind | enum | `simple_completion`, `tool_calling` |
| ok | bool | |
| latency_ms | int nullable | operativo |
| error_code | string nullable | seguro para logs |
| notes | string | |

## FakeSessionTraffic

| Campo | Tipo | Regla |
|---|---|---|
| session_id | string | |
| found | bool | true solo para `demo-session-001` |
| total_entries | int nullable | `42` si found |
| peak_hour | string nullable | `15:00-16:00` si found |

## ValidationEvidenceSummary

Resumen versionable: inventario + resultados + `quotas_costs` o `not_measured` + `runs_policy: minimal` + comandos + limitaciones. Sin API keys.
