import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from flowsight.services.chat import _public_figures, azure_draft
from flowsight.services.chat_metrics import ChatFigure


def test_reasoning_model_can_answer_after_reading_the_metrics_tool() -> None:
    calls: list[dict] = []

    def create(**request):
        calls.append(request)
        if len(calls) == 1:
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(id="call-1", function=SimpleNamespace(
                    name="get_session_figures", arguments="{}"
                ))],
            )
            finish = "tool_calls"
        elif request["max_completion_tokens"] <= 256:
            # Observed with gpt-5-mini: the whole small budget went to reasoning.
            message = SimpleNamespace(content=None, tool_calls=[])
            finish = "length"
        else:
            assert request["messages"][-1]["role"] == "tool"
            assert '"17"' in request["messages"][-1]["content"]
            message = SimpleNamespace(
                content="El tráfico observado es 17, una estimación de visitas.", tool_calls=[]
            )
            finish = "stop"
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = SimpleNamespace(deployment="gpt-5-mini")
    with patch("flowsight.services.chat.load_azure_llm_settings", return_value=settings), patch(
        "flowsight.services.chat.build_client", return_value=(client, settings)
    ):
        result = azure_draft(
            question="¿Cuál es el tráfico?",
            figures=[
                ChatFigure("traffic_total", "visit_estimate", "available", Decimal("17"), None)
            ],
            shop_name="Local",
            timeout_seconds=20,
        )
    assert "17" in result.text
    assert result.model_calls == 2
    assert len(calls) == 2


def test_answer_requires_the_scoped_tool_before_text_generation() -> None:
    def create(**request):
        tool_results = [message for message in request["messages"] if message["role"] == "tool"]
        if not tool_results:
            if request["tool_choice"] == "auto":
                # A provider may answer without looking up the registered data.
                message = SimpleNamespace(content="El tráfico es 123456.", tool_calls=[])
            else:
                message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
                    id="metrics",
                    function=SimpleNamespace(name="get_session_figures", arguments="{}"),
                )])
        elif request["tool_choice"] != "none":
            # Automatic choice can repeat the lookup instead of finishing.
            message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
                id="repeat", function=SimpleNamespace(name="get_session_figures", arguments="{}")
            )])
        else:
            value = json.loads(tool_results[-1]["content"])[0]["value"]
            message = SimpleNamespace(content=f"El tráfico observado es {value}.", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = SimpleNamespace(deployment="gpt-5-mini")
    with patch("flowsight.services.chat.load_azure_llm_settings", return_value=settings), patch(
        "flowsight.services.chat.build_client", return_value=(client, settings)
    ):
        result = azure_draft(
            question="¿Cuál fue el tráfico?",
            figures=[
                ChatFigure("traffic_total", "visit_estimate", "available", Decimal("17"), None)
            ],
            shop_name="Local 1",
            timeout_seconds=20,
        )
    assert result.text == "El tráfico observado es 17."
    assert result.model_calls == 2


def test_provider_cannot_skip_the_required_metrics_lookup() -> None:
    def create(**_request):
        message = SimpleNamespace(content="El tráfico es 123456.", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    settings = SimpleNamespace(deployment="gpt-5-mini")
    with patch("flowsight.services.chat.load_azure_llm_settings", return_value=settings), patch(
        "flowsight.services.chat.build_client", return_value=(client, settings)
    ):
        result = azure_draft(
            question="¿Cuál fue el tráfico?",
            figures=[
                ChatFigure("traffic_total", "visit_estimate", "available", Decimal("17"), None)
            ],
            shop_name="Local 1",
            timeout_seconds=20,
        )
    assert result.text == ""
    assert result.model_calls == 1


def test_tool_values_keep_precision_and_distinguish_zero_from_unavailable() -> None:
    payload = _public_figures([
        ChatFigure("entries", "none", "available", Decimal("0.000000"), None),
        ChatFigure("dwell_mean_seconds", "observable", "available", Decimal("3.125000"), None),
        ChatFigure("dwell_median_seconds", "observable", "unavailable", None, "no_closed_dwells"),
    ])
    assert payload[0]["value"] == "0"
    assert payload[1]["value"] == "3.125"
    assert payload[1]["unit"] == "segundos"
    assert payload[2]["value"] is None
    assert payload[2]["availability"] == "no disponible"
    assert "permanencias completas" in payload[2]["unavailable_reason"]
