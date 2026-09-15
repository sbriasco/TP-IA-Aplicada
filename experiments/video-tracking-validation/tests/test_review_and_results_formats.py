from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from detection import build_observation, write_detections_jsonl
from spatial_events import EVENT_FIELDS, write_events_csv

REVIEW_STATUSES = {
    "coincidencia",
    "omisión",
    "duplicado",
    "no comparable",
    "espurio",
}

REVIEW_FIELDS = (
    "fragment_id",
    "manual_observation_id",
    "automatic_observation_id",
    "match_status",
    "error_category",
    "track_continuity_status",
    "reviewer_notes",
)

CONTINUITY_STATUSES = {
    "continua",
    "posible pérdida",
    "cambio de ID",
    "no evaluable",
}

EXAMPLE_REVIEW = EXPERIMENT_ROOT / "references" / "review.example.csv"


def is_spurious_within_reviewed_sample(
    automatic_observation_id: str,
    reviewed_automatic_ids: set[str],
    has_manual_match: bool,
) -> bool:
    if automatic_observation_id not in reviewed_automatic_ids:
        return False
    return not has_manual_match


class ResultsFormatTests(unittest.TestCase):
    def test_detection_jsonl_keeps_stable_ids_bbox_and_reference_point(self) -> None:
        observation = build_observation(
            session_id="session-a",
            video_id="video-a",
            fragment_id="frag-a",
            frame_index=10,
            video_timestamp_seconds=8.4,
            relative_seconds=0.4,
            track_id="7",
            xyxy=[1.0, 2.0, 5.0, 8.0],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "detections.jsonl"
            write_detections_jsonl(path, [observation])
            loaded = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(loaded["automatic_observation_id"], "session-a:frag-a:10:7")
        self.assertEqual(loaded["bbox"], [1.0, 2.0, 5.0, 8.0])
        self.assertEqual(loaded["reference_point"], [3.0, 8.0])
        self.assertEqual(loaded["video_timestamp_seconds"], 8.4)
        self.assertEqual(loaded["relative_seconds"], 0.4)

    def test_events_csv_has_required_identity_and_time_fields(self) -> None:
        event = {field: "x" for field in EVENT_FIELDS}
        event.update(
            {
                "frame_index": 10,
                "video_timestamp_seconds": 8.4,
                "relative_seconds": 0.4,
                "event_type": "line_cross",
                "automatic_observation_id": "session-a:frag-a:10:7",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            write_events_csv(path, [event])
            with path.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
        self.assertEqual(row["automatic_observation_id"], "session-a:frag-a:10:7")
        self.assertEqual(row["relative_seconds"], "0.4")

    def test_absence_outside_manual_sample_is_not_spurious(self) -> None:
        reviewed_ids = {"session-a:frag-a:10:7"}
        self.assertFalse(
            is_spurious_within_reviewed_sample(
                "session-a:frag-a:99:99",
                reviewed_ids,
                has_manual_match=False,
            )
        )
        self.assertTrue(
            is_spurious_within_reviewed_sample(
                "session-a:frag-a:10:7",
                reviewed_ids,
                has_manual_match=False,
            )
        )
        self.assertIn("espurio", REVIEW_STATUSES)
        self.assertIn("omisión", REVIEW_STATUSES)

    def test_review_example_csv_has_minimum_fields_and_status_values(self) -> None:
        self.assertTrue(EXAMPLE_REVIEW.is_file())
        with EXAMPLE_REVIEW.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 5)
        self.assertEqual(tuple(rows[0].keys()), REVIEW_FIELDS)
        statuses = {row["match_status"] for row in rows}
        self.assertEqual(statuses, REVIEW_STATUSES)
        continuities = {row["track_continuity_status"] for row in rows}
        self.assertTrue(continuities <= CONTINUITY_STATUSES)
        self.assertIn("cambio de ID", continuities)
        id_change_rows = [row for row in rows if row["track_continuity_status"] == "cambio de ID"]
        self.assertTrue(id_change_rows)
        self.assertNotEqual(id_change_rows[0]["match_status"], "duplicado")
        notes = " ".join(row["reviewer_notes"] for row in rows)
        self.assertTrue(notes.strip())

    def test_local_review_csv_distinguishes_statuses_when_present(self) -> None:
        path = EXPERIMENT_ROOT / "outputs" / "review.csv"
        if not path.is_file():
            self.skipTest("outputs/review.csv es local y puede no existir en CI")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(rows[0].keys()), REVIEW_FIELDS)
        self.assertEqual({row["match_status"] for row in rows}, REVIEW_STATUSES)
        self.assertTrue({row["track_continuity_status"] for row in rows} <= CONTINUITY_STATUSES)
        self.assertTrue(any(row["track_continuity_status"] == "cambio de ID" for row in rows))
        id_change = next(row for row in rows if row["track_continuity_status"] == "cambio de ID")
        self.assertNotEqual(id_change["match_status"], "duplicado")
        self.assertTrue(all(row["reviewer_notes"].strip() for row in rows))
