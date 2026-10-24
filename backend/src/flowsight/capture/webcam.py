"""Open a local integer device, with DirectShow then Media Foundation on Windows."""

import math
import sys

import cv2

from flowsight.capture.contracts import CaptureError, CaptureSettings

# Prefer compressed USB modes. On many UVC devices OpenCV's default is YUY2;
# at 1280×720 that often collapses to a few FPS on USB 2.0. MJPEG is widely
# supported and is what virtual cameras (e.g. OBS) typically deliver already.
# CAP_PROP_FPS is a request: the driver may clamp to 30/60/other supported rates.
_DEFAULT_TARGET_FPS = 60


def device_reported_fps(capture) -> float | None:
    """Read CAP_PROP_FPS after open. Often 0 or unreliable on Windows."""
    try:
        value = float(capture.get(cv2.CAP_PROP_FPS))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value


def _configure_capture(capture, settings: CaptureSettings) -> None:
    """Best-effort stream negotiation; drivers may ignore unsupported props."""
    target_fps = settings.requested_fps if settings.requested_fps > 0 else _DEFAULT_TARGET_FPS
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.requested_width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.requested_height)
    capture.set(cv2.CAP_PROP_FPS, target_fps)
    # Keep the shared latest-frame slot fresh when the driver queues frames.
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def open_webcam(settings: CaptureSettings):
    if not isinstance(settings.device_index, int) or not 0 <= settings.device_index <= 32:
        raise CaptureError("device_unavailable")
    if settings.backend == "auto":
        backends = (
            [("dshow", cv2.CAP_DSHOW), ("msmf", cv2.CAP_MSMF)]
            if sys.platform == "win32"
            else [("auto", cv2.CAP_ANY)]
        )
    else:
        backends = [
            (settings.backend, {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}[settings.backend])
        ]
    for backend, code in backends:
        capture = cv2.VideoCapture(settings.device_index, code)
        if capture.isOpened():
            _configure_capture(capture, settings)
            return capture, backend
        capture.release()
    raise CaptureError("device_unavailable")
