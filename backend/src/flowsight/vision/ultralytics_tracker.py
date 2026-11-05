"""Ultralytics YOLO11m + ByteTrack. Imported only when the worker selects it."""

from __future__ import annotations

from pathlib import Path

from flowsight.vision.detector import BagBox, Detection, ModelUnavailable

DETECTOR_VERSION = "8.4.153"
WEIGHT_FILENAME = "yolo11m.pt"
# COCO: backpack, handbag, suitcase — detect without tracking.
BAG_CLASS_IDS = (24, 26, 28)


class UltralyticsTracker:
    name = "yolo11m"
    version = DETECTOR_VERSION
    tracker_name = "bytetrack"
    tracker_version = "ultralytics-bytetrack"

    def __init__(self, weights: Path | None) -> None:
        if weights is None or Path(weights).name != WEIGHT_FILENAME or not Path(weights).is_file():
            raise ModelUnavailable("model_unavailable")
        self._weights = Path(weights)
        self._model: object | None = None
        self._person_tracker: object | None = None
        self._cached_frame: object | None = None
        self._cached_frame_index: int | None = None
        self._detections: list[Detection] = []
        self._bags: list[BagBox] = []
        self._device = "cpu"
        self.execution_mode: str | None = None
        self.limitations: list[str] = []

    def reset_tracking(self) -> None:
        """Start a new continuity segment while keeping loaded model weights."""
        if self._person_tracker is not None:
            self._person_tracker.reset()  # type: ignore[attr-defined]
        self._cached_frame = None
        self._cached_frame_index = None
        self._detections = []
        self._bags = []

    def detect(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[Detection]:
        del width, height
        if frame is None:
            return []
        if self._cached_frame_index == frame_index and self._cached_frame is frame:
            return list(self._detections)
        model = self._ensure_model()
        try:
            detections, bags = self._track(model, frame)
        except Exception:
            if self._device != "cuda":
                raise
            self._device = "cpu"
            self.execution_mode = "cpu"
            self._remember("El procesador gráfico falló al usarse; el análisis siguió en CPU.")
            detections, bags = self._track(model, frame)
        self._cached_frame = frame
        self._cached_frame_index = frame_index
        self._detections = detections
        self._bags = bags
        return list(detections)

    def detect_bags(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[BagBox]:
        if frame is None:
            return []
        self.detect(frame_index, width, height, frame)
        return list(self._bags)

    def _ensure_model(self) -> object:
        if self._model is not None:
            return self._model
        import torch
        from ultralytics import YOLO

        model = YOLO(str(self._weights))
        cuda_ready = False
        if torch.cuda.is_available():
            try:
                model.to("cuda")
                cuda_ready = True
            except Exception:
                cuda_ready = False
        device, limitation = choose_device(
            cuda_available=torch.cuda.is_available(),
            cuda_ready=cuda_ready,
        )
        self._device = device
        self.execution_mode = device
        if limitation is not None:
            self._remember(limitation)
        self._model = model
        return model

    def _track(self, model: object, frame: object) -> tuple[list[Detection], list[BagBox]]:
        # One inference, one person-only tracker update. YOLO.track() would retain
        # callbacks on predict(), letting a bag pass age/remove person tracks.
        # Ultralytics 8.4 maps the old `half=True` flag to `quantize=16` and warns on every call.
        kwargs: dict[str, object] = {
            "source": frame,
            "device": self._device,
            "verbose": False,
            "classes": [0, *BAG_CLASS_IDS],
            "conf": 0.1,  # ByteTrack needs the same low-confidence input as YOLO.track().
            "batch": 1,
        }
        if self._device == "cuda":
            kwargs["quantize"] = 16
        results = model.predict(**kwargs)  # type: ignore[attr-defined]
        if not results or results[0].boxes is None:
            return [], []
        result = results[0]
        boxes = result.boxes
        bags = [
            BagBox(bbox=tuple(xyxy))
            for xyxy, class_id, confidence in zip(
                boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist(), strict=True
            )
            if int(class_id) in BAG_CLASS_IDS and confidence >= 0.25
        ]
        people = boxes[boxes.cls == 0].cpu().numpy()
        tracker = self._ensure_person_tracker()
        tracks = tracker.update(people, result.orig_img)  # type: ignore[attr-defined]
        detections = [
            Detection(track_id=int(track[4]), bbox=tuple(float(value) for value in track[:4]))
            for track in tracks
        ]
        return detections, bags

    def _ensure_person_tracker(self) -> object:
        if self._person_tracker is None:
            from ultralytics.trackers.byte_tracker import BYTETracker
            from ultralytics.utils import ROOT, YAML, IterableSimpleNamespace

            config = IterableSimpleNamespace(**YAML.load(ROOT / "cfg/trackers/bytetrack.yaml"))
            self._person_tracker = BYTETracker(config)
        return self._person_tracker

    def _remember(self, limitation: str) -> None:
        if limitation not in self.limitations:
            self.limitations.append(limitation)


def choose_device(*, cuda_available: bool, cuda_ready: bool) -> tuple[str, str | None]:
    """Pick cuda only when it is present and usable. Otherwise stay on CPU."""

    if cuda_available and cuda_ready:
        return "cuda", None
    if cuda_available:
        return "cpu", "El procesador gráfico no pudo usarse; el análisis siguió en CPU."
    return "cpu", "No hay procesador gráfico disponible; el análisis corrió en CPU."
