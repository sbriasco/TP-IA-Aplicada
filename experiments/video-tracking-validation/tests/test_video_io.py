from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from fragment_times import relative_seconds
from video_io import iter_fragment_frames, summarize_fragment_read, write_synthetic_video


class FragmentVideoReadTests(unittest.TestCase):
    def test_reads_half_open_interval_with_absolute_and_relative_timestamps(self) -> None:
        fps = 25.0
        fragment = {
            "video_id": "synthetic-video-001",
            "fragment_id": "synthetic-fragment-read",
            "start_video_seconds": 0.08,
            "end_video_seconds": 0.24,
            "time_unit": "seconds",
        }
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "synthetic.avi"
            write_synthetic_video(video_path, frame_count=10, fps=fps, size=(64, 48))
            records = [
                {key: value for key, value in item.items() if key != "frame"}
                for item in iter_fragment_frames(video_path, fragment, fps=fps)
            ]
            summary = summarize_fragment_read(video_path, fragment, fps=fps)

        self.assertEqual([item["frame_index"] for item in records], [2, 3, 4, 5])
        self.assertEqual(records[0]["video_timestamp_seconds"], 2 / fps)
        self.assertEqual(records[-1]["video_timestamp_seconds"], 5 / fps)
        self.assertLess(records[-1]["video_timestamp_seconds"], fragment["end_video_seconds"])
        for item in records:
            self.assertEqual(
                item["relative_seconds"],
                relative_seconds(
                    item["video_timestamp_seconds"],
                    fragment["start_video_seconds"],
                ),
            )
            self.assertNotIn("processing_time_seconds", item)
        self.assertEqual(summary["frame_count"], 4)
        self.assertEqual(summary["width"], 64)
        self.assertEqual(summary["height"], 48)
        self.assertEqual(summary["fps"], fps)


if __name__ == "__main__":
    unittest.main()
