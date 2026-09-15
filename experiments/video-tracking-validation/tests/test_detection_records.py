from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from detection import (
    bbox_and_reference_point,
    build_observation,
    make_automatic_observation_id,
    write_detections_jsonl,
)


class DetectionRecordTests(unittest.TestCase):
    def test_stable_observation_id_and_bottom_center_reference_point(self) -> None:
        observation = build_observation(
            session_id="session-test",
            video_id="synthetic-video-001",
            fragment_id="synthetic-fragment-001",
            frame_index=200,
            video_timestamp_seconds=8.0,
            relative_seconds=0.0,
            track_id="3",
            xyxy=[10.0, 20.0, 40.0, 80.0],
        )
        self.assertEqual(
            observation["automatic_observation_id"],
            make_automatic_observation_id("session-test", "synthetic-fragment-001", 200, "3"),
        )
        self.assertEqual(observation["bbox"], [10.0, 20.0, 40.0, 80.0])
        self.assertEqual(observation["reference_point"], [25.0, 80.0])
        self.assertEqual(observation["track_id"], "3")
        self.assertEqual(observation["session_id"], "session-test")

    def test_bbox_uses_xyxy_order(self) -> None:
        bbox, reference = bbox_and_reference_point((1, 2, 5, 9))
        self.assertEqual(bbox, [1.0, 2.0, 5.0, 9.0])
        self.assertEqual(reference, [3.0, 9.0])

    def test_jsonl_roundtrip_keeps_required_fields(self) -> None:
        observation = build_observation(
            session_id="session-test",
            video_id="synthetic-video-001",
            fragment_id="synthetic-fragment-001",
            frame_index=201,
            video_timestamp_seconds=8.04,
            relative_seconds=0.04,
            track_id="1",
            xyxy=[0.0, 0.0, 2.0, 4.0],
        )
        required = {
            "automatic_observation_id",
            "session_id",
            "fragment_id",
            "frame_index",
            "video_timestamp_seconds",
            "relative_seconds",
            "track_id",
            "bbox",
            "reference_point",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "detections.jsonl"
            write_detections_jsonl(path, [observation])
            loaded = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertTrue(required.issubset(loaded))


if __name__ == "__main__":
    unittest.main()
