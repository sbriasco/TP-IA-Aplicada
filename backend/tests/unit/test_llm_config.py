from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from flowsight.llm.settings import AzureLlmConfigurationError, load_azure_llm_settings


class AzureLlmSettingsTests(unittest.TestCase):
    def valid_environment(self) -> dict[str, str]:
        return {
            "FLOWSIGHT_AZURE_AI_ENDPOINT": "https://example.services.ai.azure.com",
            "FLOWSIGHT_AZURE_AI_API_KEY": "test-key-not-real",
            "FLOWSIGHT_AZURE_AI_DEPLOYMENT": "gpt-35-turbo",
            "FLOWSIGHT_AZURE_AI_REGION": "eastus",
            "FLOWSIGHT_AZURE_AI_MODEL": "gpt-35-turbo",
        }

    def test_loads_valid_azure_settings(self) -> None:
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            settings = load_azure_llm_settings()

        self.assertEqual(settings.deployment, "gpt-35-turbo")
        self.assertEqual(settings.region, "eastus")
        self.assertEqual(settings.api_key.get_secret_value(), "test-key-not-real")

    def test_reports_missing_endpoint_without_exposing_values(self) -> None:
        environment = self.valid_environment()
        del environment["FLOWSIGHT_AZURE_AI_ENDPOINT"]

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(AzureLlmConfigurationError) as raised:
                load_azure_llm_settings()

        message = str(raised.exception)
        self.assertIn("endpoint", message.lower())
        self.assertIn("missing", message)
        self.assertNotIn("test-key-not-real", message)

    def test_reports_empty_api_key_without_echo(self) -> None:
        environment = self.valid_environment()
        secret = "super-secret-azure-key"
        environment["FLOWSIGHT_AZURE_AI_API_KEY"] = "   "

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(AzureLlmConfigurationError) as raised:
                load_azure_llm_settings()

        message = str(raised.exception)
        self.assertIn("empty", message)
        self.assertNotIn(secret, message)

    def test_does_not_echo_api_key_on_other_errors(self) -> None:
        environment = self.valid_environment()
        secret = "super-secret-azure-key-xyz"
        environment["FLOWSIGHT_AZURE_AI_API_KEY"] = secret
        environment["FLOWSIGHT_AZURE_AI_DEPLOYMENT"] = "   "

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(AzureLlmConfigurationError) as raised:
                load_azure_llm_settings()

        self.assertNotIn(secret, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
