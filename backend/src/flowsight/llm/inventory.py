"""Inventario de acceso a Azure AI Foundry sin SDK de modelo."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flowsight.llm.evidence import utc_now_iso, write_evidence_json
from flowsight.llm.settings import AzureLlmConfigurationError, load_azure_llm_settings

AccessStatus = Literal["available", "blocked", "not_evaluated"]
ToolCallingStatus = Literal["demonstrated", "not_supported", "not_evaluated"]


@dataclass(frozen=True)
class AzureAccessInventory:
    checked_at: str
    access_status: AccessStatus
    block_reason: str | None
    service_kind: str
    region: str | None
    deployment_name: str | None
    model_name: str | None
    model_selection_notes: str | None
    auth_method: str
    tool_calling_status: ToolCallingStatus
    probe_http_status: int | None = None
    sdk_candidate_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _probe_endpoint(endpoint: str, timeout_sec: float = 10.0) -> tuple[str, int | None, str | None]:
    """Sonda HTTP con stdlib. Cualquier respuesta HTTP implica endpoint alcanzable."""

    url = endpoint.rstrip("/") + "/"
    request = Request(url, method="GET", headers={"User-Agent": "flowsight-azure-inventory/0.1"})
    try:
        with urlopen(request, timeout=timeout_sec) as response:  # noqa: S310 - URL from config
            return "available", int(response.status), None
    except HTTPError as error:
        # 401/403/404 siguen siendo señal de que el host responde.
        return "available", int(error.code), None
    except URLError as error:
        reason = getattr(error, "reason", error)
        return "blocked", None, f"network_error: {type(reason).__name__}"
    except TimeoutError:
        return "blocked", None, "network_error: TimeoutError"
    except OSError as error:
        return "blocked", None, f"network_error: {type(error).__name__}"


def run_inventory(*, probe: bool = True) -> AzureAccessInventory:
    """Construye inventario desde .env y, opcionalmente, sonda el endpoint."""

    try:
        settings = load_azure_llm_settings()
    except AzureLlmConfigurationError as error:
        return AzureAccessInventory(
            checked_at=utc_now_iso(),
            access_status="not_evaluated",
            block_reason=str(error),
            service_kind="azure_ai_foundry",
            region=None,
            deployment_name=None,
            model_name=None,
            model_selection_notes=None,
            auth_method="api_key",
            tool_calling_status="not_evaluated",
            sdk_candidate_notes=(
                "Sin config completa no se propone SDK. Completar .env y reintentar."
            ),
        )

    notes = settings.model_selection_notes or (
        "Modelo antiguo/permitido indicado en .env; confirmar nombre comercial en portal Foundry."
    )
    model_name = settings.model_name or settings.deployment

    if not probe:
        return AzureAccessInventory(
            checked_at=utc_now_iso(),
            access_status="not_evaluated",
            block_reason="probe_skipped",
            service_kind="azure_ai_foundry",
            region=settings.region,
            deployment_name=settings.deployment,
            model_name=model_name,
            model_selection_notes=notes,
            auth_method="api_key",
            tool_calling_status="not_evaluated",
            sdk_candidate_notes=_sdk_candidate_notes(settings.endpoint),
        )

    status, http_status, block_reason = _probe_endpoint(settings.endpoint)
    return AzureAccessInventory(
        checked_at=utc_now_iso(),
        access_status=status,  # type: ignore[arg-type]
        block_reason=block_reason,
        service_kind="azure_ai_foundry",
        region=settings.region,
        deployment_name=settings.deployment,
        model_name=model_name,
        model_selection_notes=notes,
        auth_method="api_key",
        tool_calling_status="not_evaluated",
        probe_http_status=http_status,
        sdk_candidate_notes=_sdk_candidate_notes(settings.endpoint),
    )


def _sdk_candidate_notes(endpoint: str) -> str:
    host = endpoint.lower()
    if "services.ai.azure.com" in host or "cognitiveservices" in host:
        return (
            "Candidato sugerido (pendiente aprobación): openai (cliente OpenAI-compatible) "
            "apuntando al endpoint Foundry con API key y deployment. "
            "Alternativa: azure-ai-inference. No instalar hasta aprobación explícita."
        )
    return (
        "Candidato sugerido (pendiente aprobación): cliente OpenAI-compatible o "
        "azure-ai-inference según documentación del endpoint Foundry. "
        "No instalar hasta aprobación explícita."
    )


def write_inventory_draft(output_dir: Path, inventory: AzureAccessInventory) -> Path:
    path = output_dir / "inventory-draft.json"
    return write_evidence_json(path, inventory.to_dict())


def inventory_cli(output_dir: str) -> int:
    """CLI mínima para el script PowerShell."""

    inventory = run_inventory(probe=True)
    path = write_inventory_draft(Path(output_dir), inventory)
    payload = {
        "ok": inventory.access_status != "blocked",
        "path": str(path),
        **inventory.to_dict(),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if inventory.access_status in {"available", "not_evaluated"} else 1


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "specs/003-validacion-modelo-azure/validation"
    raise SystemExit(inventory_cli(out))
