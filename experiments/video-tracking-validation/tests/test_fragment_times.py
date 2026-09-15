from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from fragment_times import (
    FragmentTimeError,
    is_timestamp_in_fragment,
    load_fragments_manifest,
    relative_seconds,
    behavior_duration_seconds,
    validate_fragment_interval,
)

FRAGMENTS_EXAMPLE_PATH = EXPERIMENT_ROOT / "references" / "fragments.example.csv"


class FragmentTimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fragments = load_fragments_manifest(FRAGMENTS_EXAMPLE_PATH)

    def test_example_manifest_uses_seconds_and_half_open_intervals(self) -> None:
        self.assertGreaterEqual(len(self.fragments), 1)
        for fragment in self.fragments:
            self.assertEqual(fragment["time_unit"], "seconds")
            validate_fragment_interval(fragment)
            start = fragment["start_video_seconds"]
            end = fragment["end_video_seconds"]
            self.assertTrue(is_timestamp_in_fragment(start, fragment))
            self.assertFalse(is_timestamp_in_fragment(end, fragment))

    def test_relative_seconds_uses_video_timestamps_without_rounding(self) -> None:
        timestamp = 12.345678901
        start = 8.0
        converted = relative_seconds(
            video_timestamp_seconds=timestamp,
            start_video_seconds=start,
            processing_time_seconds=123.0,
        )
        self.assertEqual(converted, timestamp - start)
        self.assertNotEqual(converted, round(timestamp - start, 2))
        self.assertNotEqual(converted, 123.0)

    def test_behavior_duration_uses_video_timestamps_not_processing_time(self) -> None:
        duration = behavior_duration_seconds(
            8.00,
            14.76,
            processing_time_seconds=12.244914000009885,
        )
        self.assertEqual(duration, 6.76)
        self.assertNotEqual(duration, 12.244914000009885)

    def test_interval_rejects_negative_start_or_non_increasing_end(self) -> None:
        with self.assertRaises(FragmentTimeError):
            validate_fragment_interval(
                {
                    "start_video_seconds": -0.1,
                    "end_video_seconds": 10.0,
                    "time_unit": "seconds",
                }
            )
        with self.assertRaises(FragmentTimeError):
            validate_fragment_interval(
                {
                    "start_video_seconds": 8.0,
                    "end_video_seconds": 8.0,
                    "time_unit": "seconds",
                }
            )

    def test_time_unit_must_be_seconds(self) -> None:
        with self.assertRaises(FragmentTimeError):
            validate_fragment_interval(
                {
                    "start_video_seconds": 0.0,
                    "end_video_seconds": 5.0,
                    "time_unit": "frames",
                }
            )


if __name__ == "__main__":
    unittest.main()
