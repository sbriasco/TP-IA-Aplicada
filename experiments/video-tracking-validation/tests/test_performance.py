from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from performance import (
    PERFORMANCE_FIELDS,
    build_performance_row,
    build_performance_summary_row,
    write_performance_csv,
)


class PerformanceRecordTests(unittest.TestCase):
    def test_performance_row_keeps_processing_time_separate_from_video_duration(self) -> None:
        row = build_performance_row(
            session_id="session-a",
            video_id="video-a",
            fragment_id="frag-a",
            device="cpu",
            video_duration_seconds=7.32,
            frames_processed=183,
            processing_time_seconds=12.5,
            detection_tracking_time_seconds=11.0,
            postprocess_time_seconds=1.5,
            notes="operativo",
        )
        self.assertNotEqual(row["processing_time_seconds"], row["video_duration_seconds"])
        self.assertEqual(row["processing_time_seconds"], 12.5)
        self.assertEqual(row["detection_tracking_time_seconds"], 11.0)
        self.assertEqual(row["postprocess_time_seconds"], 1.5)
        self.assertIn("cpu", str(row["device"]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.csv"
            write_performance_csv(path, [row])
            with path.open(encoding="utf-8", newline="") as handle:
                loaded = next(csv.DictReader(handle))
        self.assertEqual(list(loaded.keys()), list(PERFORMANCE_FIELDS))
        self.assertEqual(loaded["frames_processed"], "183")

    def test_summary_row_is_traceable_to_fragment_records(self) -> None:
        row = build_performance_row(
            session_id="session-a",
            video_id="video-a",
            fragment_id="frag-a",
            device="cpu",
            video_duration_seconds=7.32,
            frames_processed=183,
            processing_time_seconds=12.24,
            detection_tracking_time_seconds=11.54,
            postprocess_time_seconds=0.70,
            notes="fragmento",
        )
        summary = build_performance_summary_row([row])
        self.assertEqual(summary["fragment_id"], "summary")
        self.assertEqual(summary["processing_time_seconds"], 12.24)
        self.assertEqual(summary["detection_tracking_time_seconds"], 11.54)
        self.assertIn("frag-a", str(summary["notes"]))
        self.assertNotEqual(summary["processing_time_seconds"], row["video_duration_seconds"])


if __name__ == "__main__":
    unittest.main()
