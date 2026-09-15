from __future__ import annotations

import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from spatial_events import (
    events_from_detections,
    line_crossing_sense,
    point_in_polygon,
    segments_intersect,
)

ZONE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
LINE_START = [0.0, 5.0]
LINE_END = [10.0, 5.0]
SCENE = {
    "front_zone": {"name": "front-zone", "polygon": ZONE},
    "entry_line": {
        "name": "entry-line",
        "start": LINE_START,
        "end": LINE_END,
        "directions": {"A_to_B": "entry", "B_to_A": "exit"},
    },
}


def _det(track: str, frame: int, x: float, y: float) -> dict[str, object]:
    return {
        "automatic_observation_id": f"s:f:{frame}:{track}",
        "session_id": "s",
        "fragment_id": "f",
        "frame_index": frame,
        "video_timestamp_seconds": frame / 25.0,
        "relative_seconds": frame / 25.0,
        "track_id": track,
        "reference_point": [x, y],
    }


class SpatialEventTests(unittest.TestCase):
    def test_segment_not_infinite_line(self) -> None:
        self.assertTrue(segments_intersect([2, 0], [2, 10], LINE_START, LINE_END))
        self.assertIsNone(line_crossing_sense([12, 0], [12, 10], LINE_START, LINE_END))
        self.assertIsNone(line_crossing_sense([-1, 0], [-1, 10], LINE_START, LINE_END))

    def test_both_crossing_senses_map_to_scene_directions(self) -> None:
        a_to_b = line_crossing_sense([5, 8], [5, 2], LINE_START, LINE_END)
        b_to_a = line_crossing_sense([5, 2], [5, 8], LINE_START, LINE_END)
        self.assertEqual(a_to_b, "A_to_B")
        self.assertEqual(b_to_a, "B_to_A")
        detections = [_det("1", 1, 5, 8), _det("1", 2, 5, 2)]
        events = events_from_detections(detections, SCENE)
        crosses = [item for item in events if item["event_type"] == "line_cross"]
        self.assertEqual(crosses[0]["direction"], "entry")

    def test_zone_enter_and_exit_use_reference_point(self) -> None:
        detections = [_det("1", 1, 20, 20)]
        detections.extend(_det("1", frame, 5, 5) for frame in range(2, 13))
        detections.append(_det("1", 13, 20, 20))
        events = events_from_detections(detections, SCENE)
        types = [item["event_type"] for item in events if item["event_type"].startswith("zone")]
        self.assertEqual(types, ["zone_enter", "zone_exit"])

    def test_oscillation_is_not_confirmed_entry_exit(self) -> None:
        detections = [_det("1", 1, 5, 8), _det("1", 2, 5, 2), _det("1", 3, 5, 8)]
        events = events_from_detections(detections, SCENE)
        self.assertFalse(any(item["event_type"] == "line_cross" for item in events))
        self.assertTrue(any(item["event_type"] == "line_cross_oscillation" for item in events))

    def test_track_id_change_is_not_duplicate_or_confirmed_exit(self) -> None:
        detections = [
            _det("1", 1, 5, 5),
            _det("1", 2, 5, 5),
            _det("2", 3, 5, 5),
        ]
        events = events_from_detections(detections, SCENE)
        self.assertFalse(any(item["event_type"] == "zone_exit" for item in events))
        self.assertFalse(any("duplicado" in str(item["notes"]).lower() and item["track_id"] == "2" for item in events))

    def test_lost_track_is_not_zone_exit(self) -> None:
        detections = [_det("1", 1, 5, 5), _det("1", 8, 5, 5)]
        events = events_from_detections(detections, SCENE)
        self.assertTrue(any(item["event_type"] == "track_lost" for item in events))
        self.assertTrue(any(item["event_type"] == "track_resumed" for item in events))
        self.assertFalse(any(item["event_type"] == "zone_exit" for item in events))

    def test_point_in_polygon(self) -> None:
        self.assertTrue(point_in_polygon([5, 5], ZONE))
        self.assertFalse(point_in_polygon([20, 20], ZONE))


if __name__ == "__main__":
    unittest.main()
