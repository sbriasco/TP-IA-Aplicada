from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowsight.llm.evidence import empty_summary_template, redact_value, write_evidence_json


class EvidenceRedactionTests(unittest.TestCase):
    def test_redacts_api_key_fields_and_headers(self) -> None:
        payload = {
            "api_key": "sk-secret",
            "Authorization": "Bearer sk-secret",
            "nested": {"token": "abc", "notes": "ok"},
            "headers": {"authorization": "Bearer xyz"},
        }

        redacted = redact_value(payload)

        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["token"], "[REDACTED]")
        self.assertEqual(redacted["nested"]["notes"], "ok")
        self.assertEqual(redacted["headers"]["authorization"], "[REDACTED]")

    def test_write_evidence_never_persists_raw_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            write_evidence_json(
                path,
                {
                    "api_key": "should-not-appear",
                    "access_status": "available",
                    "notes": "api_key=should-not-appear",
                },
            )
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)

        self.assertNotIn("should-not-appear", text)
        self.assertEqual(data["api_key"], "[REDACTED]")
        self.assertEqual(data["access_status"], "available")

    def test_empty_summary_template_has_required_keys(self) -> None:
        summary = empty_summary_template()
        self.assertEqual(summary["service_kind"], "azure_ai_foundry")
        self.assertEqual(summary["tool_calling_status"], "not_evaluated")
        self.assertEqual(summary["runs_policy"], "minimal")


if __name__ == "__main__":
    unittest.main()
