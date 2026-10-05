"""Open a local integer device, with DirectShow then Media Foundation on Windows."""

import sys

import cv2

from flowsight.capture.contracts import CaptureError, CaptureSettings


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
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.requested_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.requested_height)
            return capture, backend
        capture.release()
    raise CaptureError("device_unavailable")
