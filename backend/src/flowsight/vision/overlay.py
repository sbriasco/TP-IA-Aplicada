"""Draw detections and the configured scene onto a frame and encode a JPEG."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from flowsight.vision.detector import Detection

MAX_JPEG_BYTES = 200 * 1024
_INITIAL_QUALITY = 80
_MIN_QUALITY = 5

Polygon = Sequence[Sequence[float]]
Line = tuple[Sequence[float], Sequence[float]]


def render_overlay_jpeg(
    frame_bgr: np.ndarray,
    detections: Sequence[Detection],
    zones: Sequence[Polygon],
    entry_line: Line | None,
) -> bytes:
    """Return a JPEG of this frame at its own resolution.

    Quality starts at 80 and drops if the file would pass 200 KiB. The image
    size stays the frame size.
    """

    image = frame_bgr.copy()
    height, width = image.shape[:2]
    for polygon in zones:
        points = _pixels(polygon, width, height)
        if len(points) >= 2:
            cv2.polylines(image, [points], isClosed=True, color=(255, 180, 0), thickness=2)
    if entry_line is not None:
        start, end = entry_line
        start_px = _pixels((start,), width, height)[0]
        end_px = _pixels((end,), width, height)[0]
        cv2.line(image, tuple(start_px), tuple(end_px), (0, 0, 255), 2)
    for detection in detections:
        x1, y1, x2, y2 = (int(value) for value in detection.bbox)
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(
            image,
            str(detection.track_id),
            (x1, max(0, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 220, 0),
            1,
            cv2.LINE_AA,
        )
    quality = _INITIAL_QUALITY
    encoded = _encode(image, quality)
    while len(encoded) > MAX_JPEG_BYTES and quality > _MIN_QUALITY:
        quality = max(_MIN_QUALITY, quality - 10)
        encoded = _encode(image, quality)
        if quality == _MIN_QUALITY:
            break
    return encoded


def _pixels(polygon: Sequence[Sequence[float]], width: int, height: int) -> np.ndarray:
    return np.array(
        [[int(point[0] * width), int(point[1] * height)] for point in polygon],
        dtype=np.int32,
    )


def _encode(image: np.ndarray, quality: int) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("jpeg_encode_failed")
    return buffer.tobytes()
