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


@dataclass(frozen=True)
class BagBox:
    """Bag AABB without a track. COCO backpack, handbag or suitcase."""

    bbox: tuple[float, float, float, float]


def foot_from_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """Bottom-center of an xyxy box, in the same pixel space as the box."""

    x1, _y1, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


def boxes_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    """True when two xyxy boxes share a positive area."""

    lx1, ly1, lx2, ly2 = left
    rx1, ry1, rx2, ry2 = right
    width = min(lx2, rx2) - max(lx1, rx1)
    height = min(ly2, ry2) - max(ly1, ry1)
    return width > 0 and height > 0


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
        """Return this frame's person detections. `frame` is ignored by the fake detector."""

    def detect_bags(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[BagBox]:
        """Return bag boxes for this frame. No track_id."""


def build_detector(settings: Settings) -> Detector:
    """Return the configured detector. `fake` never opens a weight file."""

    if settings.detector != "ultralytics":
        from flowsight.vision.fake import FakeDetector

        return FakeDetector()
    from flowsight.vision.ultralytics_tracker import UltralyticsTracker

    return UltralyticsTracker(settings.yolo_weights)
