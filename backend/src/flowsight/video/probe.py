"""Probe a local video with OpenCV: frames, fps, duration and reference frame (R3).

Frames are counted with `grab()` instead of trusting `CAP_PROP_FRAME_COUNT`,
which is unreliable for MPEG streams. The header count is still reported as
`declared_frame_count`, only to warn about videos that look incomplete (T051).
No database or HTTP concerns live here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Literal

import cv2

MAX_HEADER_FPS = 240
JPEG_QUALITY = 90

# A video looks incomplete when it decodes fewer frames than its header declares,
# beyond this margin: max(5 frames, 2 % of the declared count).
INCOMPLETE_MIN_MISSING_FRAMES = 5
INCOMPLETE_MISSING_RATIO = Decimal("0.02")

# Precision of `video_sources.fps` and of the numeric(12,6) time columns.
_FPS_STEP = Decimal("0.0001")
_SECONDS_STEP = Decimal("0.000001")

RejectionCode = Literal["unsupported_format", "no_decodable_frames", "fps_unknown"]


class VideoRejected(ValueError):
    """The file cannot be registered as a video; `code` is the API error code."""

    def __init__(self, code: RejectionCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProbeResult:
    width: int
    height: int
    fps: Decimal
    fps_is_estimated: bool
    frame_count: int
    declared_frame_count: int | None
    duration_seconds: Decimal
    reference_frame_index: int
    reference_timestamp_seconds: Decimal
    reference_jpeg: bytes


def probe_video(path: Path) -> ProbeResult:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise VideoRejected("unsupported_format")
        header_fps = capture.get(cv2.CAP_PROP_FPS)
        declared_frame_count = _declared_frame_count(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        frame_count = 0
        last_position_msec = 0.0
        reference_index: int | None = None
        reference_frame = None
        while capture.grab():
            frame_count += 1
            last_position_msec = capture.get(cv2.CAP_PROP_POS_MSEC)
            if reference_frame is None:
                ok, frame = capture.retrieve()
                if ok and frame is not None:
                    reference_index = frame_count - 1
                    reference_frame = frame
    finally:
        capture.release()

    if reference_frame is None or reference_index is None:
        raise VideoRejected("no_decodable_frames")

    fps, fps_is_estimated = _fps(header_fps, frame_count, last_position_msec)
    encoded, jpeg = cv2.imencode(".jpg", reference_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not encoded:
        raise VideoRejected("no_decodable_frames")

    height, width = reference_frame.shape[:2]
    return ProbeResult(
        width=width,
        height=height,
        fps=fps,
        fps_is_estimated=fps_is_estimated,
        frame_count=frame_count,
        declared_frame_count=declared_frame_count,
        duration_seconds=_seconds(Decimal(frame_count) / fps),
        reference_frame_index=reference_index,
        reference_timestamp_seconds=_seconds(Decimal(reference_index) / fps),
        reference_jpeg=jpeg.tobytes(),
    )


def appears_incomplete(frame_count: int, declared_frame_count: int | None) -> bool:
    """True when the header declares clearly more frames than could be decoded."""

    if declared_frame_count is None:
        return False
    margin = max(
        INCOMPLETE_MIN_MISSING_FRAMES,
        math.ceil(INCOMPLETE_MISSING_RATIO * declared_frame_count),
    )
    return declared_frame_count - frame_count > margin


def _declared_frame_count(header_count: float) -> int | None:
    if math.isfinite(header_count) and header_count > 0:
        return int(header_count)
    return None


def _fps(header_fps: float, frame_count: int, last_position_msec: float) -> tuple[Decimal, bool]:
    """Header fps when plausible; otherwise last frame timestamp / (frames - 1)."""

    if _plausible(header_fps):
        return Decimal(repr(header_fps)).quantize(_FPS_STEP, ROUND_HALF_EVEN), False
    if frame_count > 1 and math.isfinite(last_position_msec) and last_position_msec > 0:
        estimated = (Decimal(frame_count - 1) * 1000 / Decimal(repr(last_position_msec))).quantize(
            _FPS_STEP, ROUND_HALF_EVEN
        )
        if _plausible(float(estimated)):
            return estimated, True
    raise VideoRejected("fps_unknown")


def _plausible(fps: float) -> bool:
    return math.isfinite(fps) and 0 < fps <= MAX_HEADER_FPS


def _seconds(value: Decimal) -> Decimal:
    return value.quantize(_SECONDS_STEP, ROUND_HALF_EVEN)
