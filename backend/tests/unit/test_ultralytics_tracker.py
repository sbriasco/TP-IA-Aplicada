"""The real detector is YOLO11 medium. A different weight file is not accepted."""

from __future__ import annotations

from pathlib import Path

import pytest

from flowsight.vision.detector import ModelUnavailable
from flowsight.vision.ultralytics_tracker import UltralyticsTracker


def test_tracker_name_is_yolo11m() -> None:
    assert UltralyticsTracker.name == "yolo11m"


def test_yolo11m_file_is_accepted_without_loading_the_model(tmp_path: Path) -> None:
    weight = tmp_path / "yolo11m.pt"
    weight.write_bytes(b"placeholder")

    tracker = UltralyticsTracker(weight)

    assert tracker.name == "yolo11m"


def test_another_weight_filename_is_unavailable(tmp_path: Path) -> None:
    weight = tmp_path / "yolov8s.pt"
    weight.write_bytes(b"placeholder")

    with pytest.raises(ModelUnavailable):
        UltralyticsTracker(weight)
