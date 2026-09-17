from __future__ import annotations

import uuid
from copy import deepcopy
from decimal import Decimal

import pytest

from flowsight.synthetic.trace import SyntheticTraceError, generate_synthetic_trace


def valid_payload() -> dict:
    return {
        "schema_version": 1,
        "frames": [
            {
                "key": "frame-0",
                "frame_index": 0,
                "video_timestamp_seconds": 0,
                "observations": [{"key": "person-0", "track_id": 1, "kind": "synthetic_person"}],
                "events": [],
            },
            {
                "key": "frame-1",
                "frame_index": 1,
                "video_timestamp_seconds": 0.5,
                "observations": [{"key": "person-1", "track_id": 1, "kind": "synthetic_person"}],
                "events": [
                    {
                        "key": "entry-1",
                        "event_type": "zone_enter",
                        "observation_key": "person-1",
                    }
                ],
            },
        ],
    }


def test_generates_deterministic_records_with_complete_context() -> None:
    job_id = uuid.UUID("00000000-0000-0000-0000-000000000101")
    session_id = uuid.UUID("00000000-0000-0000-0000-000000000201")

    records = generate_synthetic_trace(
        valid_payload(), job_id=job_id, session_id=session_id, camera_id="camera-a"
    )
    repeated = generate_synthetic_trace(
        valid_payload(), job_id=job_id, session_id=session_id, camera_id="camera-a"
    )

    assert records == repeated
    assert [frame.video_timestamp_seconds for frame in records.frames] == [
        Decimal("0"),
        Decimal("0.5"),
    ]
    assert all(frame.session_id == session_id for frame in records.frames)
    assert all(observation.camera_id == "camera-a" for observation in records.observations)
    assert records.events[0].frame_id == records.frames[1].id
    assert records.events[0].observation_id == records.observations[1].id
    assert records.events[0].video_timestamp_seconds == Decimal("0.5")


@pytest.mark.parametrize("timestamp", [None, -0.1])
def test_rejects_null_or_negative_timestamp(timestamp: float | None) -> None:
    payload = valid_payload()
    payload["frames"][0]["video_timestamp_seconds"] = timestamp

    with pytest.raises(SyntheticTraceError, match="timestamp"):
        generate_synthetic_trace(
            payload, job_id=uuid.uuid4(), session_id=uuid.uuid4(), camera_id="camera-a"
        )


def test_rejects_non_monotonic_timestamps() -> None:
    payload = valid_payload()
    payload["frames"][1]["video_timestamp_seconds"] = 0

    with pytest.raises(SyntheticTraceError, match="monóton"):
        generate_synthetic_trace(
            payload, job_id=uuid.uuid4(), session_id=uuid.uuid4(), camera_id="camera-a"
        )


def test_rejects_event_reference_outside_its_frame() -> None:
    payload = valid_payload()
    payload["frames"][1]["events"][0]["observation_key"] = "person-0"

    with pytest.raises(SyntheticTraceError, match="referencia"):
        generate_synthetic_trace(
            payload, job_id=uuid.uuid4(), session_id=uuid.uuid4(), camera_id="camera-a"
        )


def test_rejects_duplicate_keys_without_mutating_input() -> None:
    payload = valid_payload()
    payload["frames"][1]["key"] = "frame-0"
    original = deepcopy(payload)

    with pytest.raises(SyntheticTraceError, match="duplicada"):
        generate_synthetic_trace(
            payload, job_id=uuid.uuid4(), session_id=uuid.uuid4(), camera_id="camera-a"
        )

    assert payload == original
