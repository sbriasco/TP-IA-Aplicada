from __future__ import annotations

import unittest

from flowsight.llm.fake_tools import DEMO_SESSION_ID, dispatch_tool, get_session_traffic


class FakeToolTests(unittest.TestCase):
    def test_demo_session_returns_hardcoded_traffic(self) -> None:
        result = get_session_traffic(DEMO_SESSION_ID)

        self.assertTrue(result["found"])
        self.assertEqual(result["total_entries"], 42)
        self.assertEqual(result["peak_hour"], "15:00-16:00")

    def test_unknown_session_returns_controlled_empty(self) -> None:
        result = get_session_traffic("unknown-session")

        self.assertFalse(result["found"])
        self.assertIsNone(result["total_entries"])
        self.assertIsNone(result["peak_hour"])

    def test_dispatch_unknown_tool(self) -> None:
        result = dispatch_tool("other_tool", {"session_id": DEMO_SESSION_ID})

        self.assertEqual(result["error"], "unknown_tool")


if __name__ == "__main__":
    unittest.main()
