# Quickstart: Validación Azure AI Foundry

Valida acceso, llamada simple y tool calling ficticio vía **script local**.  
**No** es el chat del producto. **No** requiere PostgreSQL ni frontend.

## Requisitos

- Python 3.11.16 / venv del backend.
- Proyecto Foundry **compartido** del equipo + API key (fuera de Git).
- Modelo: el **habilitado** en Foundry del equipo (evidencia: **`gpt-5-mini`**); región **`brazilsouth`**.
- Red hacia Azure.
- Aprobación antes de instalar SDK nuevo.

## Configuración

1. Copiar variables de `.env.example` (sección Azure) a tu `.env` local.
2. Pedir al equipo la **API key** por canal seguro (host/deployment no secretos están en [docs/acceso-compartido-azure.md](../../docs/acceso-compartido-azure.md)).
3. No subir `.env`.

**Importante:** la API y el worker de producto **no** exigen `FLOWSIGHT_AZURE_AI_*` para arrancar. Solo el script de validación las usa.

## Corridas mínimas

```powershell
.\scripts\validate-azure-model.ps1 -Step all
```

Pasos: `inventory` | `simple` | `tools` | `all` (default).

Orden esperado con `-Step all`:

1. Inventario / acceso Foundry  
2. Una llamada simple  
3. Un ciclo tool calling (`demo-session-001`) si el modelo lo permite  

Evitar corridas exploratorias extras (crédito compartido).

## Pruebas sin Azure (CI / local)

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m pytest -q tests/unit -k llm
Pop-Location
```

Cubren fake tool, config y redaction; **no** sustituyen la evidencia real en Foundry.

## Evidencia

Completar `specs/003-validacion-modelo-azure/validation/` y versionar solo el resumen anonimizado (`contracts/validation-evidence.md`).
