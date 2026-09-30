"""Detector contract shared by the fake sequence and the real tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from flowsight.core.config import Settings


class ModelUnavailable(RuntimeError):
    """The real detector was requested and its weight file is not on this machine."""


@dataclass(frozen=True)
class Detection:
    track_id: int
    bbox: tuple[float, float, float, float]

    @property
    def foot(self) -> tuple[float, float]:
        return foot_from_bbox(self.bbox)


def foot_from_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """Bottom-center of an xyxy box, in the same pixel space as the box."""

    x1, _y1, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


class Detector(Protocol):
    name: str
    version: str
    tracker_name: str
    tracker_version: str

    def detect(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[Detection]:
        """Return this frame's detections. `frame` is ignored by the fake detector."""


def build_detector(settings: Settings) -> Detector:
    """Return the configured detector. `fake` never opens a weight file."""

    if settings.detector != "ultralytics":
        from flowsight.vision.fake import FakeDetector

        return FakeDetector()
    from flowsight.vision.ultralytics_tracker import UltralyticsTracker

    return UltralyticsTracker(settings.yolo_weights)
