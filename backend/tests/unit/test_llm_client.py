from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from flowsight.llm.client import simple_completion
from flowsight.llm.settings import AzureLlmConfigurationError


class ClientSecretSafetyTests(unittest.TestCase):
    def test_config_error_does_not_echo_api_key(self) -> None:
        secret = "super-secret-should-not-leak"
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "flowsight.llm.client.build_client",
                side_effect=AzureLlmConfigurationError(
                    "Configuración Azure inválida: api_key: missing."
                ),
            ):
                result = simple_completion()

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "config_error")
        self.assertNotIn(secret, result.notes)

    def test_auth_error_message_is_safe(self) -> None:
        from openai import AuthenticationError

        settings = MagicMock()
        settings.deployment = "gpt-5-mini"
        client = MagicMock()
        client.chat.completions.create.side_effect = AuthenticationError(
            message="invalid api key sk-leak",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        with patch("flowsight.llm.client.build_client", return_value=(client, settings)):
            result = simple_completion()

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "auth_error")
        self.assertNotIn("sk-leak", result.notes)
        self.assertNotIn("invalid api key", result.notes.lower())

    def test_empty_chat_then_responses_ok(self) -> None:
        settings = MagicMock()
        settings.deployment = "gpt-5-mini"
        client = MagicMock()
        empty = MagicMock()
        empty.choices = [MagicMock(message=MagicMock(content=""))]
        client.chat.completions.create.return_value = empty
        client.responses.create.return_value = MagicMock(output_text="OK")

        with patch("flowsight.llm.client.build_client", return_value=(client, settings)):
            result = simple_completion()

        self.assertTrue(result.ok)
        self.assertEqual(result.response_text, "OK")
        self.assertEqual(result.notes, "simple_completion_ok_via_responses")

    def test_empty_everywhere_is_empty_response(self) -> None:
        settings = MagicMock()
        settings.deployment = "gpt-5-mini"
        client = MagicMock()
        empty = MagicMock()
        empty.choices = [MagicMock(message=MagicMock(content="  "))]
        client.chat.completions.create.return_value = empty
        client.responses.create.return_value = MagicMock(output_text="")

        with patch("flowsight.llm.client.build_client", return_value=(client, settings)):
            result = simple_completion()

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "empty_response")


if __name__ == "__main__":
    unittest.main()
