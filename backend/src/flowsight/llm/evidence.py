"""Serialización segura de evidencia de validación Azure."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|authorization|secret|password|token|bearer)",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)\S+")
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|secret|password|token)\s*[:=]\s*\S+"
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_value(value: Any) -> Any:
    """Elimina o enmascara secretos en estructuras anidadas."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY_PATTERN.search(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        text = _BEARER_PATTERN.sub(r"\1[REDACTED]", value)
        text = _KEY_VALUE_PATTERN.sub(
            lambda match: f"{match.group(1)}=[REDACTED]", text
        )
        return text
    return value


def write_evidence_json(path: Path, payload: dict[str, Any]) -> Path:
    """Escribe JSON redactado; nunca serializa keys ni headers sensibles."""

    safe = redact_value(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def empty_summary_template() -> dict[str, Any]:
    return {
        "checked_at": utc_now_iso(),
        "access_status": "not_evaluated",
        "service_kind": "azure_ai_foundry",
        "region": None,
        "deployment_name": None,
        "model_name": None,
        "model_selection_notes": None,
        "auth_method": "api_key",
        "simple_call": {"ok": False, "latency_ms": None},
        "tool_calling_status": "not_evaluated",
        "runs_policy": "minimal",
        "quotas_costs": "not_measured",
        "sc_003_within_5_min": None,
        "limitations": [],
        "commands": [
            ".\\scripts\\validate-azure-model.ps1",
            "Push-Location backend; .\\.venv\\Scripts\\python.exe -m pytest -q tests/unit -k llm; Pop-Location",
        ],
    }
