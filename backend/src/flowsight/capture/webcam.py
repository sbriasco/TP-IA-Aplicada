"""Open a local integer device, with DirectShow then Media Foundation on Windows."""

import sys

import cv2

from flowsight.capture.contracts import CaptureError, CaptureSettings

# Prefer compressed USB modes. On many UVC devices OpenCV's default is YUY2;
# at 1280×720 that often collapses to a few FPS on USB 2.0. MJPEG is widely
# supported and is what virtual cameras (e.g. OBS) typically deliver already.
_TARGET_FPS = 30


def _configure_capture(capture, settings: CaptureSettings) -> None:
    """Best-effort stream negotiation; drivers may ignore unsupported props."""
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.requested_width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.requested_height)
    capture.set(cv2.CAP_PROP_FPS, _TARGET_FPS)
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
