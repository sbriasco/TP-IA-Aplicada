from __future__ import annotations

import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

ALLOWED_STATUSES = {
    "viable",
    "viable con ajustes",
    "no viable con el material o configuración evaluados",
    "no evaluable por falta de evidencia",
}

REQUIRED_SECTIONS = (
    "Identificación",
    "Cobertura",
    "Errores",
    "Rendimiento",
    "Tabla por medición",
    "Decisiones pendientes",
)


def report_matches_contract(text: str) -> list[str]:
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section.lower() not in text.lower():
            missing.append(f"sección {section}")
    found_statuses = {status for status in ALLOWED_STATUSES if status in text}
    if not found_statuses:
        missing.append("ningún estado de viabilidad permitido")
    return missing


class ViabilityReportContractTests(unittest.TestCase):
    def test_local_report_covers_contract_sections_and_allowed_statuses(self) -> None:
        path = EXPERIMENT_ROOT / "outputs" / "viability-report.md"
        if not path.is_file():
            self.skipTest("outputs/viability-report.md es local")
        text = path.read_text(encoding="utf-8")
        missing = report_matches_contract(text)
        self.assertEqual(missing, [])
        for status in ALLOWED_STATUSES:
            self.assertIn(status, text)
        self.assertIn("processing_time_seconds", text)
        self.assertIn("detection_tracking_time_seconds", text)
        self.assertIn("postprocess_time_seconds", text)
        self.assertIn("no sustituye", text.lower())
        self.assertNotRegex(text, r"precisión del \d+")
        self.assertNotIn("99% de acierto", text)


if __name__ == "__main__":
    unittest.main()
