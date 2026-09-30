"""JSONL trajectory sample. One header, then one line per track every fifth frame."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

from flowsight.vision.detector import Detection

SAMPLE_EVERY_FRAMES = 5


def trajectory_relative_path(session_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"derived/{session_id}/{job_id}/trajectory.jsonl"


def _number(value: Decimal | float) -> float:
    return float(Decimal(value).quantize(Decimal("0.000001")))


def _normalized(pixel: float, size: int) -> float:
    return _number(Decimal(pixel) / Decimal(size))


class TrajectoryWriter:
    def __init__(
        self,
        path: Path,
        *,
        session_id: uuid.UUID,
        job_id: uuid.UUID,
        detector_name: str,
        detector_version: str,
        tracker_name: str,
        tracker_version: str,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")
        self._write(
            {
                "record": "header",
                "session_id": str(session_id),
                "job_id": str(job_id),
                "sample_every_frames": SAMPLE_EVERY_FRAMES,
                "detector_name": detector_name,
                "detector_version": detector_version,
                "tracker_name": tracker_name,
                "tracker_version": tracker_version,
            }
        )

    def observe(
        self,
        frame_index: int,
        video_timestamp_seconds: Decimal,
        detections: list[Detection],
        *,
        width: int,
        height: int,
    ) -> None:
        if frame_index % SAMPLE_EVERY_FRAMES != 0:
            return
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            foot_x, foot_y = detection.foot
            self._write(
                {
                    "record": "sample",
                    "frame_index": frame_index,
                    "video_timestamp_seconds": _number(video_timestamp_seconds),
                    "track_id": detection.track_id,
                    "bbox": [
                        _normalized(x1, width),
                        _normalized(y1, height),
                        _normalized(x2, width),
                        _normalized(y2, height),
                    ],
                    "foot": [_normalized(foot_x, width), _normalized(foot_y, height)],
                }
            )

    def close(self) -> None:
        self._file.close()

    def _write(self, record: dict[str, object]) -> None:
        self._file.write(json.dumps(record, ensure_ascii=True) + "\n")
