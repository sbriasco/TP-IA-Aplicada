from __future__ import annotations

import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from spatial_events import events_from_detections

SCENE = {
    "front_zone": {"name": "front-zone", "polygon": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]},
    "entry_line": {
        "name": "entry-line",
        "start": [0.0, 5.0],
        "end": [10.0, 5.0],
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


class EventDeduplicationTests(unittest.TestCase):
    def test_oscillation_is_recorded_not_confirmed_twice(self) -> None:
        detections = [_det("1", 1, 5, 8), _det("1", 2, 5, 2), _det("1", 3, 5, 8)]
        events = events_from_detections(detections, SCENE)
        self.assertTrue(any(item["event_type"] == "line_cross_oscillation" for item in events))
        self.assertFalse(any(item["event_type"] == "line_cross" for item in events))

    def test_track_id_change_is_not_automatic_duplicate(self) -> None:
        detections = [_det("8", 4, 5, 2), _det("9", 5, 5, 8)]
        events = events_from_detections(detections, SCENE)
        self.assertFalse(any("duplicado" in str(item["notes"]).lower() for item in events))
        self.assertFalse(any(item["event_type"] == "line_cross" for item in events))
        self.assertFalse(any(item["event_type"] == "line_cross_oscillation" for item in events))

    def test_id_change_across_line_does_not_create_duplicate_cross(self) -> None:
        detections = [
            _det("8", 1, 5, 8),
            _det("8", 2, 5, 8),
            _det("9", 3, 5, 2),
            _det("9", 4, 5, 2),
        ]
        events = events_from_detections(detections, SCENE)
        self.assertFalse(any(item["event_type"] == "line_cross" for item in events))
        self.assertFalse(any("duplicado" in str(item["notes"]).lower() for item in events))

    def test_confirmed_cross_is_not_duplicated_by_immediate_return(self) -> None:
        detections = [_det("1", 1, 5, 8), _det("1", 2, 5, 2), _det("1", 3, 5, 8)]
        events = events_from_detections(detections, SCENE)
        crosses = [item for item in events if item["event_type"] == "line_cross"]
        oscillations = [item for item in events if item["event_type"] == "line_cross_oscillation"]
        self.assertEqual(crosses, [])
        self.assertGreaterEqual(len(oscillations), 1)


if __name__ == "__main__":
    unittest.main()
