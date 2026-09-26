from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from flowsight.llm.inventory import run_inventory


class InventoryTests(unittest.TestCase):
    def valid_environment(self) -> dict[str, str]:
        return {
            "FLOWSIGHT_AZURE_AI_ENDPOINT": "https://example.services.ai.azure.com",
            "FLOWSIGHT_AZURE_AI_API_KEY": "test-key-not-real",
            "FLOWSIGHT_AZURE_AI_DEPLOYMENT": "gpt-35-turbo",
            "FLOWSIGHT_AZURE_AI_MODEL": "gpt-35-turbo",
            "FLOWSIGHT_AZURE_AI_MODEL_NOTES": "modelo antiguo permitido por la suscripción",
        }

    def test_missing_config_is_not_evaluated(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            inventory = run_inventory(probe=False)

        self.assertEqual(inventory.access_status, "not_evaluated")
        self.assertEqual(inventory.service_kind, "azure_ai_foundry")
        self.assertEqual(inventory.auth_method, "api_key")
        self.assertIsNotNone(inventory.block_reason)
        self.assertNotIn("test-key", inventory.block_reason or "")

    def test_http_error_from_endpoint_counts_as_reachable(self) -> None:
        error = HTTPError(
            url="https://example.services.ai.azure.com/",
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            with patch("flowsight.llm.inventory.urlopen", side_effect=error):
                inventory = run_inventory(probe=True)

        self.assertEqual(inventory.access_status, "available")
        self.assertEqual(inventory.probe_http_status, 401)
        self.assertEqual(inventory.deployment_name, "gpt-35-turbo")
        self.assertIn("antiguo", inventory.model_selection_notes or "")

    def test_network_error_is_blocked(self) -> None:
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            with patch(
                "flowsight.llm.inventory.urlopen",
                side_effect=URLError("timed out"),
            ):
                inventory = run_inventory(probe=True)

        self.assertEqual(inventory.access_status, "blocked")
        self.assertIn("network_error", inventory.block_reason or "")


if __name__ == "__main__":
    unittest.main()
