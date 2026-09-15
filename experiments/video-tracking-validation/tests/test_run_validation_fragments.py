from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from fragment_times import FragmentTimeError, validate_fragment_within_duration
from run_validation import EXAMPLE_FRAGMENTS_PATH, load_experiment_fragments


class RunValidationFragmentTests(unittest.TestCase):
    def test_loads_versioned_example_manifest_without_processing_video(self) -> None:
        fragments = load_experiment_fragments(EXAMPLE_FRAGMENTS_PATH)
        self.assertGreaterEqual(len(fragments), 1)
        for fragment in fragments:
            start = fragment["start_video_seconds"]
            end = fragment["end_video_seconds"]
            self.assertLess(start, end)
            self.assertEqual(fragment["time_unit"], "seconds")

    def test_rejects_interval_beyond_known_video_duration(self) -> None:
        fragment = {
            "start_video_seconds": 0.0,
            "end_video_seconds": 20.0,
            "time_unit": "seconds",
        }
        with self.assertRaises(FragmentTimeError):
            validate_fragment_within_duration(fragment, duration_seconds=15.32)

    def test_accepts_half_open_end_equal_to_duration(self) -> None:
        fragment = {
            "start_video_seconds": 8.0,
            "end_video_seconds": 15.32,
            "time_unit": "seconds",
        }
        validate_fragment_within_duration(fragment, duration_seconds=15.32)

    def test_inventory_durations_are_applied_when_loading_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fragments_path = tmp_path / "fragments.csv"
            inventory_path = tmp_path / "inventory.csv"
            fragments_path.write_text(
                "video_id,fragment_id,start_video_seconds,end_video_seconds,"
                "time_unit,selection_reason,covered_cases,coverage_limitations\n"
                "video-a,frag-a,0.0,10.0,seconds,motivo,casos,limites\n",
                encoding="utf-8",
            )
            with inventory_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["video_id", "duration_seconds"],
                )
                writer.writeheader()
                writer.writerow({"video_id": "video-a", "duration_seconds": "9.0"})
            with self.assertRaises(FragmentTimeError):
                load_experiment_fragments(fragments_path, inventory_path)


if __name__ == "__main__":
    unittest.main()
