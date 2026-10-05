"""Ultralytics YOLO11m + ByteTrack. Imported only when the worker selects it."""

from __future__ import annotations

from pathlib import Path

from flowsight.vision.detector import Detection, ModelUnavailable

DETECTOR_VERSION = "8.4.153"
WEIGHT_FILENAME = "yolo11m.pt"


class UltralyticsTracker:
    name = "yolo11m"
    version = DETECTOR_VERSION
    tracker_name = "bytetrack"
    tracker_version = "ultralytics-bytetrack"

    def __init__(self, weights: Path | None) -> None:
        if (
            weights is None
            or Path(weights).name != WEIGHT_FILENAME
            or not Path(weights).is_file()
        ):
            raise ModelUnavailable("model_unavailable")
        self._weights = Path(weights)
        self._model: object | None = None
        self._device = "cpu"
        self.execution_mode: str | None = None
        self.limitations: list[str] = []

    def reset_tracking(self) -> None:
        """Start a new continuity segment while keeping loaded model weights."""
        predictor = getattr(self._model, "predictor", None)
        trackers = getattr(predictor, "trackers", ())
        for tracker in trackers:
            tracker.reset()
        if predictor is not None and hasattr(predictor, "vid_path"):
            predictor.vid_path = [None] * len(trackers)

    def detect(
        self,
        frame_index: int,
        width: int,
        height: int,
        frame: object | None = None,
    ) -> list[Detection]:
        del frame_index, width, height
        if frame is None:
            return []
        model = self._ensure_model()
        try:
            results = self._track(model, frame)
        except Exception:
            if self._device != "cuda":
                raise
            self._device = "cpu"
            self.execution_mode = "cpu"
            self._remember("El procesador gráfico falló al usarse; el análisis siguió en CPU.")
            results = self._track(model, frame)
        if not results:
            return []
        boxes = results[0].boxes
        if boxes is None or boxes.xyxy is None or boxes.id is None:
            return []
        detections: list[Detection] = []
        for index, xyxy in enumerate(boxes.xyxy.tolist()):
            x1, y1, x2, y2 = xyxy
            detections.append(
                Detection(track_id=int(boxes.id[index].item()), bbox=(x1, y1, x2, y2))
            )
        return detections

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

    def _track(self, model: object, frame: object) -> object:
        # Ultralytics 8.4 maps the old `half=True` flag to `quantize=16` and warns on every call.
        kwargs: dict[str, object] = {
            "source": frame,
            "persist": True,
            "tracker": "bytetrack.yaml",
            "device": self._device,
            "verbose": False,
            "classes": [0],
        }
        if self._device == "cuda":
            kwargs["quantize"] = 16
        return model.track(**kwargs)  # type: ignore[attr-defined]

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
