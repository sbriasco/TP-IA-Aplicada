"""Deterministic detector used by tests and CI. It does not load a model."""

from __future__ import annotations

from flowsight.vision.detector import Detection


class FakeDetector:
    name = "fake"
    version = "fake"
    tracker_name = "fake"
    tracker_version = "fake"

    def detect(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[Detection]:
        del frame_index, width, height, frame
        return [Detection(track_id=1, bbox=(10, 20, 40, 80))]
