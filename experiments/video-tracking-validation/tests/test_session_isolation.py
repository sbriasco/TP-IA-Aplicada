from __future__ import annotations

import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from detection import build_observation
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


class SessionIsolationTests(unittest.TestCase):
    def test_two_sessions_do_not_share_session_tracks_or_fragment_refs(self) -> None:
        first = build_observation(
            session_id="session-cam-a",
            video_id="video-a",
            fragment_id="frag-a",
            frame_index=1,
            video_timestamp_seconds=1.0,
            relative_seconds=0.0,
            track_id="1",
            xyxy=[0, 0, 2, 2],
        )
        second = build_observation(
            session_id="session-cam-b",
            video_id="video-b",
            fragment_id="frag-b",
            frame_index=1,
            video_timestamp_seconds=1.0,
            relative_seconds=0.0,
            track_id="1",
            xyxy=[0, 0, 2, 2],
        )
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertNotEqual(first["fragment_id"], second["fragment_id"])
        self.assertNotEqual(first["automatic_observation_id"], second["automatic_observation_id"])
        self.assertEqual(first["track_id"], second["track_id"])
        self.assertTrue(first["automatic_observation_id"].startswith(first["session_id"]))
        self.assertTrue(second["automatic_observation_id"].startswith(second["session_id"]))
        self.assertNotEqual(first["video_id"], second["video_id"])

    def test_same_track_id_in_two_sessions_does_not_mix_trajectories(self) -> None:
        first = build_observation(
            session_id="session-cam-a",
            video_id="video-a",
            fragment_id="frag-a",
            frame_index=1,
            video_timestamp_seconds=1.0,
            relative_seconds=0.0,
            track_id="1",
            xyxy=[4.0, 6.0, 6.0, 8.0],
        )
        second = build_observation(
            session_id="session-cam-b",
            video_id="video-b",
            fragment_id="frag-b",
            frame_index=2,
            video_timestamp_seconds=2.0,
            relative_seconds=0.0,
            track_id="1",
            xyxy=[4.0, 0.0, 6.0, 2.0],
        )
        events = events_from_detections([first, second], SCENE)
        self.assertFalse(any(item["event_type"] == "line_cross" for item in events))
        session_ids = {item["session_id"] for item in events}
        self.assertTrue(session_ids <= {"session-cam-a", "session-cam-b"})
        for item in events:
            self.assertTrue(str(item["automatic_observation_id"]).startswith(str(item["session_id"])))
            self.assertEqual(item["track_id"], "1")
