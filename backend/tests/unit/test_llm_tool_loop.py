from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from flowsight.llm.fake_tools import DEMO_SESSION_ID
from flowsight.llm.tool_loop import run_tool_loop


class _Fn:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.function = _Fn(name, arguments)


class _Msg:
    def __init__(self, content: str | None, tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message: _Msg) -> None:
        self.message = message


class _Completion:
    def __init__(self, message: _Msg) -> None:
        self.choices = [_Choice(message)]


class ToolLoopTests(unittest.TestCase):
    def _settings(self):
        settings = MagicMock()
        settings.deployment = "gpt-5-mini"
        settings.api_key.get_secret_value.return_value = "test-key"
        settings.resolve_openai_base_url.return_value = "https://example.test/openai/v1"
        return settings

    def test_happy_path_demo_session(self) -> None:
        first = _Completion(
            _Msg(
                None,
                tool_calls=[
                    _ToolCall(
                        "call-1",
                        "get_session_traffic",
                        json.dumps({"session_id": DEMO_SESSION_ID}),
                    )
                ],
            )
        )
        second = _Completion(_Msg("Hubo 42 entradas; pico 15:00-16:00."))
        client = MagicMock()
        client.chat.completions.create.side_effect = [first, second]

        with patch("flowsight.llm.tool_loop.build_client", return_value=(client, self._settings())):
            result = run_tool_loop(session_id=DEMO_SESSION_ID)

        self.assertEqual(result.status, "demonstrated")
        self.assertTrue(result.call.ok)
        self.assertEqual(result.tool_result["total_entries"], 42)
        self.assertIn("42", result.final_text or "")

    def test_unknown_session_still_demonstrates_tool(self) -> None:
        first = _Completion(
            _Msg(
                None,
                tool_calls=[
                    _ToolCall(
                        "call-1",
                        "get_session_traffic",
                        json.dumps({"session_id": "unknown-session"}),
                    )
                ],
            )
        )
        second = _Completion(_Msg("No hay datos para esa sesión."))
        client = MagicMock()
        client.chat.completions.create.side_effect = [first, second]

        with patch("flowsight.llm.tool_loop.build_client", return_value=(client, self._settings())):
            result = run_tool_loop(session_id="unknown-session")

        self.assertEqual(result.status, "demonstrated")
        self.assertFalse(result.tool_result["found"])

    def test_no_tool_call_is_not_supported(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = _Completion(_Msg("No uso tools."))

        with patch("flowsight.llm.tool_loop.build_client", return_value=(client, self._settings())):
            result = run_tool_loop()

        self.assertEqual(result.status, "not_supported")
        self.assertFalse(result.call.ok)


if __name__ == "__main__":
    unittest.main()
