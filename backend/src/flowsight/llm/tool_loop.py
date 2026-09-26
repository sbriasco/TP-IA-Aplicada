"""Orquestación mínima de tool calling con la tool ficticia de analytics.

El modelo no calcula métricas ni ejecuta SQL: solo puede solicitar herramientas
registradas explícitamente (aquí, get_session_traffic).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from openai import APIError, AuthenticationError, OpenAIError

from flowsight.llm.client import ModelCallResult, build_client
from flowsight.llm.fake_tools import DEMO_SESSION_ID, TOOL_DEFINITIONS, dispatch_tool
from flowsight.llm.settings import AzureLlmConfigurationError, AzureLlmSettings

ToolCallingStatus = Literal["demonstrated", "not_supported", "not_evaluated"]


@dataclass(frozen=True)
class ToolLoopResult:
    status: ToolCallingStatus
    call: ModelCallResult
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    final_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["call"] = self.call.to_dict()
        return payload


def run_tool_loop(
    *,
    session_id: str = DEMO_SESSION_ID,
    settings: AzureLlmSettings | None = None,
    max_rounds: int = 2,
) -> ToolLoopResult:
    """Ciclo usuario → modelo → tool → modelo → respuesta."""

    started = time.perf_counter()
    prompt = (
        f"Necesito el tráfico de la sesión {session_id}. "
        "Usá la herramienta get_session_traffic y respondé en una frase "
        "incluyendo total_entries y peak_hour si hay datos."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    try:
        client, resolved = build_client(settings)
    except AzureLlmConfigurationError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        call = ModelCallResult(
            kind="tool_calling",
            ok=False,
            latency_ms=latency_ms,
            error_code="config_error",
            notes=str(error),
        )
        return ToolLoopResult(status="not_evaluated", call=call)

    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None

    try:
        for _ in range(max_rounds):
            completion = client.chat.completions.create(
                model=resolved.deployment,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_completion_tokens=256,
            )
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []

            if not tool_calls:
                latency_ms = int((time.perf_counter() - started) * 1000)
                text = (message.content or "").strip()
                if tool_result is not None:
                    call = ModelCallResult(
                        kind="tool_calling",
                        ok=True,
                        latency_ms=latency_ms,
                        error_code=None,
                        notes="tool_calling_demonstrated",
                        response_text=text[:800],
                    )
                    return ToolLoopResult(
                        status="demonstrated",
                        call=call,
                        tool_name=tool_name,
                        tool_result=tool_result,
                        final_text=text[:800],
                    )
                call = ModelCallResult(
                    kind="tool_calling",
                    ok=False,
                    latency_ms=latency_ms,
                    error_code="no_tool_call",
                    notes="El modelo no solicitó tools; marcar not_supported si persiste.",
                    response_text=text[:800] or None,
                )
                return ToolLoopResult(
                    status="not_supported",
                    call=call,
                    final_text=text[:800] or None,
                )

            assistant_payload: dict[str, Any] = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_payload)

            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                tool_result = dispatch_tool(tool_name, arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        latency_ms = int((time.perf_counter() - started) * 1000)
        call = ModelCallResult(
            kind="tool_calling",
            ok=False,
            latency_ms=latency_ms,
            error_code="max_rounds",
            notes="Se agotaron las rondas sin respuesta final del modelo.",
            raw_tool_calls=[{"name": tool_name}] if tool_name else None,
        )
        return ToolLoopResult(
            status="not_supported" if tool_result is None else "demonstrated",
            call=call,
            tool_name=tool_name,
            tool_result=tool_result,
        )
    except AuthenticationError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        call = ModelCallResult(
            kind="tool_calling",
            ok=False,
            latency_ms=latency_ms,
            error_code="auth_error",
            notes="Autenticación rechazada. Revisá la API key sin exponerla.",
        )
        return ToolLoopResult(status="not_evaluated", call=call)
    except APIError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        status_code = getattr(error, "status_code", None)
        # Algunos deployments rechazan tools con 400.
        status: ToolCallingStatus = (
            "not_supported" if status_code in {400, 404, 422} else "not_evaluated"
        )
        call = ModelCallResult(
            kind="tool_calling",
            ok=False,
            latency_ms=latency_ms,
            error_code="api_error",
            notes=f"APIError status={status_code} type={type(error).__name__}",
        )
        return ToolLoopResult(status=status, call=call)
    except OpenAIError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        call = ModelCallResult(
            kind="tool_calling",
            ok=False,
            latency_ms=latency_ms,
            error_code="openai_error",
            notes="Fallo de cliente OpenAI (detalle omitido por seguridad).",
        )
        return ToolLoopResult(status="not_evaluated", call=call)
