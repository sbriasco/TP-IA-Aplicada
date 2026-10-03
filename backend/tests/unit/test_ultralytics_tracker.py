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


def test_cuda_inference_requests_half_precision(tmp_path: Path) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    tracker._device = "cuda"
    seen: dict[str, object] = {}

    class Model:
        def track(self, **kwargs: object) -> list[object]:
            seen.update(kwargs)
            return []

    tracker._track(Model(), frame=object())

    assert seen["device"] == "cuda"
    assert seen["quantize"] == 16
    assert "half" not in seen


def test_cpu_inference_stays_in_full_precision(tmp_path: Path) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    tracker._device = "cpu"
    seen: dict[str, object] = {}

    class Model:
        def track(self, **kwargs: object) -> list[object]:
            seen.update(kwargs)
            return []

    tracker._track(Model(), frame=object())

    assert seen["device"] == "cpu"
    assert "quantize" not in seen
    assert "half" not in seen


def test_cuda_failure_retries_on_cpu_in_full_precision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    tracker._device = "cuda"
    tracker.execution_mode = "cuda"
    calls: list[bool] = []

    class Model:
        def track(self, **kwargs: object) -> list[object]:
            calls.append(kwargs.get("quantize"))
            if kwargs.get("quantize") == 16:
                raise RuntimeError("cuda half failed")
            return []

    monkeypatch.setattr(tracker, "_ensure_model", lambda: Model())

    assert tracker.detect(0, 8, 8, frame=object()) == []
    assert calls == [16, None]
    assert tracker._device == "cpu"
    assert tracker.execution_mode == "cpu"


def _weight(directory: Path) -> Path:
    weight = directory / "yolo11m.pt"
    weight.write_bytes(b"placeholder")
    return weight
