"""Trajectory sample contract: header plus one line every fifth frame."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from flowsight.vision.detector import Detection, foot_from_bbox
from flowsight.vision.trajectory import TrajectoryWriter


def test_writer_samples_every_fifth_frame_and_normalizes_the_foot(tmp_path) -> None:
    bbox = (10, 20, 40, 80)
    assert foot_from_bbox(bbox) == (25, 80)

    session_id = uuid4()
    job_id = uuid4()
    path = tmp_path / "trajectory.jsonl"
    writer = TrajectoryWriter(
        path,
        session_id=session_id,
        job_id=job_id,
        detector_name="fake",
        detector_version="fake",
        tracker_name="fake",
        tracker_version="fake",
    )
    width, height = 100, 100
    detection = Detection(track_id=3, bbox=bbox)
    for frame_index in range(13):
        writer.observe(
            frame_index,
            Decimal(frame_index) / Decimal(25),
            [detection],
            width=width,
            height=height,
        )
    writer.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    header = json.loads(lines[0])
    assert header["record"] == "header"
    assert header["sample_every_frames"] == 5
    assert header["session_id"] == str(session_id)
    assert header["detector_name"] == "fake"
    assert header["tracker_name"] == "fake"

    samples = [json.loads(line) for line in lines[1:]]
    assert [sample["frame_index"] for sample in samples] == [0, 5, 10]
    assert samples[2]["bbox"] == [0.1, 0.2, 0.4, 0.8]
    assert samples[2]["foot"] == [0.25, 0.8]
    assert samples[2]["track_id"] == 3
