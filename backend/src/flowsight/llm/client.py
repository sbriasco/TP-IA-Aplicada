"""Cliente mínimo OpenAI-compatible contra Azure AI Foundry."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from openai import APIError, AuthenticationError, OpenAI, OpenAIError

from flowsight.llm.settings import AzureLlmConfigurationError, AzureLlmSettings, load_azure_llm_settings

CallKind = Literal["simple_completion", "tool_calling"]


@dataclass(frozen=True)
class ModelCallResult:
    kind: CallKind
    ok: bool
    latency_ms: int | None
    error_code: str | None
    notes: str
    response_text: str | None = None
    raw_tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_client(settings: AzureLlmSettings | None = None) -> tuple[OpenAI, AzureLlmSettings]:
    """Construye el cliente OpenAI apuntando al endpoint Foundry."""

    resolved = settings or load_azure_llm_settings()
    client = OpenAI(
        api_key=resolved.api_key.get_secret_value(),
        base_url=resolved.resolve_openai_base_url(),
    )
    return client, resolved


def _chat_text(client: OpenAI, model: str, prompt: str) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=64,
    )
    return (completion.choices[0].message.content or "").strip()


def _responses_text(client: OpenAI, model: str, prompt: str) -> str:
    response = client.responses.create(model=model, input=prompt)
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def simple_completion(
    *,
    prompt: str = "Respondé solo con la palabra OK.",
    settings: AzureLlmSettings | None = None,
) -> ModelCallResult:
    """Una completion mínima con texto no vacío; no imprime secretos."""

    started = time.perf_counter()
    try:
        client, resolved = build_client(settings)
        prompts = [prompt, "Reply with exactly the word OK and nothing else."]
        last_path = "chat.completions"
        for attempt_prompt in prompts:
            text = _chat_text(client, resolved.deployment, attempt_prompt)
            if text:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return ModelCallResult(
                    kind="simple_completion",
                    ok=True,
                    latency_ms=latency_ms,
                    error_code=None,
                    notes="simple_completion_ok",
                    response_text=text[:500],
                )

        last_path = "responses.create"
        try:
            text = _responses_text(client, resolved.deployment, prompt)
        except OpenAIError:
            text = ""
        if text:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ModelCallResult(
                kind="simple_completion",
                ok=True,
                latency_ms=latency_ms,
                error_code=None,
                notes="simple_completion_ok_via_responses",
                response_text=text[:500],
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            kind="simple_completion",
            ok=False,
            latency_ms=latency_ms,
            error_code="empty_response",
            notes=(
                f"Completion sin texto usable tras reintento y {last_path}. "
                "Revisá deployment/modelo o límites de tokens."
            ),
            response_text=None,
        )
    except AzureLlmConfigurationError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            kind="simple_completion",
            ok=False,
            latency_ms=latency_ms,
            error_code="config_error",
            notes=str(error),
        )
    except AuthenticationError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            kind="simple_completion",
            ok=False,
            latency_ms=latency_ms,
            error_code="auth_error",
            notes="Autenticación rechazada. Revisá FLOWSIGHT_AZURE_AI_API_KEY sin pegar la clave.",
        )
    except APIError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            kind="simple_completion",
            ok=False,
            latency_ms=latency_ms,
            error_code="api_error",
            notes=f"APIError status={getattr(error, 'status_code', None)} type={type(error).__name__}",
        )
    except OpenAIError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelCallResult(
            kind="simple_completion",
            ok=False,
            latency_ms=latency_ms,
            error_code="openai_error",
            notes=f"{type(error).__name__}: fallo de cliente (detalle omitido por seguridad)",
        )
