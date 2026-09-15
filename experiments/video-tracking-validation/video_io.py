from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from fragment_times import relative_seconds, validate_fragment_interval


class VideoReadError(ValueError):
    """Raised when a fragment cannot be read from the video file."""


def iter_fragment_frames(
    video_path: str | Path,
    fragment: Mapping[str, Any],
    fps: float | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield frames in [start_video_seconds, end_video_seconds) with video timestamps."""
    validate_fragment_interval(fragment)
    path = Path(video_path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoReadError(f"No se pudo abrir el video: {path}")

    measured_fps = float(fps) if fps else float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    if measured_fps <= 0:
        capture.release()
        raise VideoReadError("El FPS del video debe ser mayor que cero.")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start = fragment["start_video_seconds"]
    end = fragment["end_video_seconds"]
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            video_timestamp = frame_index / measured_fps
            if start <= video_timestamp < end:
                yield {
                    "frame_index": frame_index,
                    "video_timestamp_seconds": video_timestamp,
                    "relative_seconds": relative_seconds(video_timestamp, start),
                    "width": width,
                    "height": height,
                    "fps": measured_fps,
                    "frame": frame,
                }
            if video_timestamp >= end:
                break
            frame_index += 1
    finally:
        capture.release()


def summarize_fragment_read(
    video_path: str | Path,
    fragment: Mapping[str, Any],
    fps: float | None = None,
) -> dict[str, Any]:
    frames = list(iter_fragment_frames(video_path, fragment, fps=fps))
    if not frames:
        raise VideoReadError("El fragmento no contiene frames en el intervalo semiabierto.")
    first = frames[0]
    last = frames[-1]
    return {
        "fragment_id": fragment.get("fragment_id"),
        "video_id": fragment.get("video_id"),
        "frame_count": len(frames),
        "width": first["width"],
        "height": first["height"],
        "fps": first["fps"],
        "first_frame_index": first["frame_index"],
        "last_frame_index": last["frame_index"],
        "first_video_timestamp_seconds": first["video_timestamp_seconds"],
        "last_video_timestamp_seconds": last["video_timestamp_seconds"],
        "first_relative_seconds": first["relative_seconds"],
        "last_relative_seconds": last["relative_seconds"],
        "interval": [fragment["start_video_seconds"], fragment["end_video_seconds"]],
    }


def write_synthetic_video(path: str | Path, frame_count: int, fps: float, size: tuple[int, int]) -> None:
    width, height = size
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise VideoReadError(f"No se pudo crear el video sintético: {path}")
    try:
        for index in range(frame_count):
            frame = np.full((height, width, 3), index, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()
