# Research: Validación del servicio de modelo de Azure

## Servicio y cuenta

### Azure AI Foundry

**Decisión**: usar **Azure AI Foundry** con proyecto/recurso **compartido** del equipo y crédito de suscripción de estudiantes (~100 USD).

**Rationale**: decisión de clarify; evita evaluar Azure OpenAI “clásico” como servicio primario.

**Alternatives considered**: Azure OpenAI standalone (descartado salvo bloqueo documentado de Foundry); una suscripción por integrante (rechazado: dificulta SC-007).

### Modelo habilitado

**Decisión**: usar **`gpt-5-mini`** (deployment habilitado por el proyecto Foundry del equipo). Región del recurso: **`brazilsouth`**. La regla previa “solo modelos antiguos / modernos bloqueados” quedó obsoleta tras la asignación real del equipo.

**Rationale**: credenciales y deployment entregados por el equipo; inventario y corridas mínimas lo confirmaron (tool calling `demonstrated`).

**Alternatives considered**: “solo modelos antiguos” (descartado: el proyecto habilita `gpt-5-mini`); otros deployments no asignados.

## Autenticación

**Decisión**: **API key** (clave de proyecto/recurso Foundry) en variables de entorno locales. Entra ID fuera de alcance de esta Feature.

**Rationale**: clarify; simple para seis integrantes con `.env` propio.

**Alternatives considered**: Entra ID interactivo/app registration (pospuesto).

## Cliente y dependencias

### Ubicación

**Decisión**: `backend/src/flowsight/llm/` + `scripts/validate-azure-model.ps1`. Sin endpoint HTTP.

**Rationale**: clarify (solo script); Feature #16 reutilizará el cliente.

### SDK

**Decisión**: **`openai==1.109.1`** (cliente OpenAI-compatible) contra `…/openai/v1` del proyecto Foundry. Instalado tras inventario y `/speckit-implement`.

**Rationale**: endpoint Foundry OpenAI-compatible; sin frameworks de agentes.

**Alternatives considered**: `azure-ai-inference` (alternativa documentada, no adoptada); LangChain / Semantic Kernel (fuera de MVP).

### Settings

**Decisión**: settings Azure **opcionales**, cargados solo por el módulo/script de validación. API y worker existentes **no** exigen variables Foundry para arrancar.

**Rationale**: FR-014 / CI sin Azure.

## Tool calling

**Decisión**: orquestación propia de 1–2 rondas; única tool `get_session_traffic` según contrato. Datos hardcodeados para `demo-session-001`.

**Rationale**: constitución VI; clarify.

**Alternatives considered**: framework de agentes; tools reales contra PostgreSQL (fuera de alcance).

## Crédito y corridas

**Decisión**: solo corridas mínimas (inventario + 1 simple + 1 tools si aplica). Registrar consumo si es visible; si no, `not_measured`. Sin tope fijo USD.

**Rationale**: clarify B.

## Evidencia

**Decisión**: mismo patrón que Feature #6: carpeta `validation/` local; resumen anonimizado versionable sin keys ni tokens.

## Relación con otras Features

- **#4 / #6**: no modificar.
- **#16**: consumirá conclusiones y, si aplica, `flowsight.llm`.
- **PostgreSQL compartido en Azure**: fuera de alcance.

## Fuentes

- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/)
- [Function calling](https://learn.microsoft.com/azure/ai-services/openai/how-to/function-calling)
- `docs/decisiones-tecnicas.md`, constitución VI, `spec.md` clarifications
