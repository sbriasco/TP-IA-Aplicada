from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from run_validation import load_experiment_fragments

INVENTORY_PATH = EXPERIMENT_ROOT / "inputs" / "video-inventory.csv"
FRAGMENTS_PATH = EXPERIMENT_ROOT / "references" / "fragments.csv"
SELECTION_PATH = EXPERIMENT_ROOT / "outputs" / "fragment-selection.csv"
EXAMPLE_PATH = EXPERIMENT_ROOT / "references" / "fragments.example.csv"

CONTRACT_FRAGMENT_FIELDS = (
    "video_id",
    "fragment_id",
    "start_video_seconds",
    "end_video_seconds",
    "time_unit",
    "selection_reason",
    "covered_cases",
    "coverage_limitations",
)


def _local_files_present() -> bool:
    return INVENTORY_PATH.exists() and FRAGMENTS_PATH.exists() and SELECTION_PATH.exists()


class UserStory1CoverageTests(unittest.TestCase):
    def test_example_template_remains_synthetic_and_versioned(self) -> None:
        with EXAMPLE_PATH.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertTrue(all(row["video_id"].startswith("synthetic-") for row in rows))

    @unittest.skipUnless(_local_files_present(), "archivos locales de US1 no generados")
    def test_each_inventoried_video_has_a_documented_fragment(self) -> None:
        with INVENTORY_PATH.open(encoding="utf-8", newline="") as handle:
            inventory = list(csv.DictReader(handle))
        fragments = load_experiment_fragments(FRAGMENTS_PATH, INVENTORY_PATH)
        with SELECTION_PATH.open(encoding="utf-8", newline="") as handle:
            selection = list(csv.DictReader(handle))

        video_ids = {row["video_id"] for row in inventory}
        self.assertEqual(len(video_ids), 4)
        fragment_videos = {row["video_id"] for row in fragments}
        selection_videos = {row["video_id"] for row in selection}
        self.assertEqual(video_ids, fragment_videos)
        self.assertEqual(video_ids, selection_videos)

        for row in fragments:
            for field in CONTRACT_FRAGMENT_FIELDS:
                self.assertIn(field, row)
                self.assertTrue(str(row[field]).strip())
            self.assertEqual(row["time_unit"], "seconds")

        for row in selection:
            self.assertIn(row["evaluation_status"], {"evaluable", "limitado", "no evaluable"})
            self.assertTrue(row["coverage_limitations"].strip())

        self.assertTrue(all(row["evaluation_status"] != "no evaluable" for row in selection))


if __name__ == "__main__":
    unittest.main()
