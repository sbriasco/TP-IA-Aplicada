"""The real detector is YOLO11 medium. A different weight file is not accepted."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from flowsight.vision.detector import ModelUnavailable
from flowsight.vision.ultralytics_tracker import UltralyticsTracker


def test_tracker_name_is_yolo11m() -> None:
    assert UltralyticsTracker.name == "yolo11m"


@pytest.mark.parametrize("with_bags", [False, True])
def test_bag_inference_keeps_new_person_ids_with_real_tracking_callbacks(
    tmp_path: Path, with_bags: bool
) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    bag = [[12, 12, 30, 30, 0.9, 26]] if with_bags else []
    tracker._model = _callback_model(
        {0: [], **{frame: [[10, 10, 90, 90, 0.9, 0], *bag] for frame in range(1, 6)}}
    )
    observed = []
    for index in range(6):
        image = np.full((100, 100, 3), index, dtype=np.uint8)
        people = tracker.detect(index, 100, 100, image)
        bags = tracker.detect_bags(index, 100, 100, image)
        observed.append([person.track_id for person in people])
        assert len(bags) == (1 if with_bags and index > 0 else 0)
    assert observed == [[], [], [1], [1], [1], [1]]


def test_people_and_bags_share_one_inference_and_keep_bag_confidence(tmp_path: Path) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    model = _callback_model(
        {
            0: [
                [10, 10, 90, 90, 0.9, 0],
                [12, 12, 30, 30, 0.9, 26],
                [40, 40, 50, 50, 0.2, 24],
            ]
        }
    )
    tracker._model = model
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    people = tracker.detect(0, 100, 100, image)
    bags = tracker.detect_bags(0, 100, 100, image)
    assert [person.track_id for person in people] == [1]
    assert [bag.bbox for bag in bags] == [(12, 12, 30, 30)]
    assert model.predict_calls == 1


def _callback_model(rows: dict[int, list[list[float]]]):
    """Replace only neural inference; retain Ultralytics' track method and callbacks."""
    from collections import defaultdict

    import torch
    from ultralytics.engine.model import Model
    from ultralytics.engine.results import Results
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import ROOT, YAML, IterableSimpleNamespace

    class InferenceModel:
        track = Model.track

        def __init__(self) -> None:
            config = IterableSimpleNamespace(**YAML.load(ROOT / "cfg/trackers/bytetrack.yaml"))
            self.callbacks = defaultdict(list)
            self.predict_calls = 0
            self.predictor = SimpleNamespace(
                args=SimpleNamespace(task="detect"),
                dataset=SimpleNamespace(mode="image"),
                trackers=[BYTETracker(config)],
                save_dir=Path("."),
                vid_path=[None],
            )

        def add_callback(self, event, callback) -> None:
            self.callbacks[event].append(callback)

        def predict(self, source, **kwargs):
            self.predict_calls += 1
            for callback in self.callbacks["on_predict_start"]:
                callback(self.predictor)
            boxes = torch.tensor(rows[int(source[0, 0, 0])], dtype=torch.float32).reshape(-1, 6)
            boxes = boxes[boxes[:, 4] >= kwargs.get("conf", 0.25)]
            classes = torch.tensor(kwargs["classes"])
            boxes = boxes[torch.isin(boxes[:, 5], classes)]
            self.predictor.results = [
                Results(
                    source,
                    path="frame.jpg",
                    names={0: "person", 24: "backpack", 26: "handbag"},
                    boxes=boxes,
                )
            ]
            for callback in self.callbacks["on_predict_postprocess_end"]:
                callback(self.predictor)
            return self.predictor.results

    return InferenceModel()


def test_reset_tracking_keeps_loaded_weights_and_clears_trackers(tmp_path: Path) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    left = [10, 10, 30, 90, 0.9, 0]
    right = [60, 10, 90, 90, 0.9, 0]
    model = _callback_model({0: [left], 1: [left, right], 2: [right, left]})
    tracker._model = model
    for index in range(3):
        image = np.full((100, 100, 3), index, dtype=np.uint8)
        people = tracker.detect(index, 100, 100, image)
    assert {person.track_id: person.bbox for person in people} == {
        1: (10, 10, 30, 90),
        2: (60, 10, 90, 90),
    }
    tracker.reset_tracking()
    restarted = tracker.detect(2, 100, 100, image)
    assert {person.track_id: person.bbox for person in restarted} == {
        1: (60, 10, 90, 90),
        2: (10, 10, 30, 90),
    }
    assert tracker._model is model


def test_reset_before_model_load_does_not_load_weights(tmp_path: Path) -> None:
    tracker = UltralyticsTracker(_weight(tmp_path))
    tracker.reset_tracking()
    assert tracker._model is None


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
        def predict(self, **kwargs: object) -> list[object]:
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
        def predict(self, **kwargs: object) -> list[object]:
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
        def predict(self, **kwargs: object) -> list[object]:
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
