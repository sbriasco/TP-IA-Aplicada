from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from overlay import render_fragment_overlays
from video_io import write_synthetic_video


class OverlayTests(unittest.TestCase):
    def test_writes_annotated_overlay_for_fragment_frames(self) -> None:
        fragment = {
            "video_id": "synthetic-video-001",
            "fragment_id": "synthetic-fragment-001",
            "start_video_seconds": 0.0,
            "end_video_seconds": 0.12,
            "time_unit": "seconds",
        }
        scene = {
            "front_zone": {"name": "front-zone", "polygon": [[2, 2], [60, 2], [60, 40], [2, 40]]},
            "entry_line": {"start": [8, 24], "end": [50, 24], "directions": {"A_to_B": "entry", "B_to_A": "exit"}},
        }
        detections = [
            {
                "frame_index": 1,
                "track_id": "1",
                "bbox": [10.0, 8.0, 30.0, 28.0],
                "reference_point": [20.0, 28.0],
            }
        ]
        events = [{"frame_index": 1, "event_type": "line_cross", "direction": "entry"}]
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "clip.avi"
            out_dir = Path(tmp) / "overlays"
            write_synthetic_video(video_path, frame_count=4, fps=25.0, size=(64, 48))
            summary = render_fragment_overlays(
                video_path=video_path,
                fragment=fragment,
                scene=scene,
                detections=detections,
                events=events,
                output_dir=out_dir,
                fps=25.0,
            )
            self.assertEqual(summary["overlay_count"], 3)
            overlay = out_dir / "overlay_f000001.jpg"
            self.assertTrue(overlay.is_file())
            image = __import__("cv2").imread(str(overlay))
            self.assertIsNotNone(image)
            self.assertEqual(image.shape[0], 48)


if __name__ == "__main__":
    unittest.main()
