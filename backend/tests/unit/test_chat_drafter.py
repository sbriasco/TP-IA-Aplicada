from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from flowsight.services.chat import azure_draft
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
