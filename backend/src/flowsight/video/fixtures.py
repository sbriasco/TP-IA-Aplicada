"""Deterministic synthetic video clips for tests and E2E runs.

Clips are generated on demand into a caller-provided directory so no video is
ever committed to the repository (R14). Every frame draws its own index, so the
reference frame and frame counts can be asserted against known content.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

Codec = Literal["mjpg", "mp4v", "mpeg1"]

CLIP_FPS = 25
CLIP_SECONDS = 2
CLIP_FRAMES = CLIP_FPS * CLIP_SECONDS
MAX_SIZE = (3840, 2160)

# MPEG-1 only accepts standard frame rates; 25 fps works for every codec.
_CODECS: dict[str, tuple[str, str]] = {
    "mjpg": ("MJPG", ".avi"),
    "mp4v": ("mp4v", ".mp4"),
    "mpeg1": ("PIM1", ".mpg"),
}
STANDARD_SIZES: tuple[tuple[int, int], ...] = ((1280, 720), (1920, 1080), (640, 480))
MPEG_SIZE = (640, 480)


class MpegUnavailable(RuntimeError):
    """The installed OpenCV cannot write a decodable MPEG-1 clip."""


class FixtureWriteError(RuntimeError):
    """OpenCV could not write the requested clip."""


def write_clip(directory: Path, codec: Codec = "mjpg", size: tuple[int, int] = (1280, 720)) -> Path:
    """Write a 2 s clip into `directory` and return its path."""

    if codec not in _CODECS:
        raise ValueError(f"codec must be one of {sorted(_CODECS)}")
    _validate_size(size)
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError("output directory does not exist")

    fourcc, suffix = _CODECS[codec]
    width, height = size
    path = directory / f"clip-{codec}-{width}x{height}{suffix}"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), CLIP_FPS, size)
    if not writer.isOpened():
        path.unlink(missing_ok=True)
        raise FixtureWriteError(f"OpenCV could not open a {fourcc} writer")
    try:
        for index in range(CLIP_FRAMES):
            writer.write(_frame(index, width, height))
    finally:
        writer.release()
    return path


def write_mpeg_clip(directory: Path) -> Path:
    """Write the MPEG-1 clip, or raise `MpegUnavailable` so tests can skip."""

    try:
        path = write_clip(directory, codec="mpeg1", size=MPEG_SIZE)
    except FixtureWriteError as error:
        raise MpegUnavailable(str(error)) from None
    if not _decodes_all_frames(path):
        path.unlink(missing_ok=True)
        raise MpegUnavailable("MPEG-1 clip was written but does not decode")
    return path


def write_standard_clips(directory: Path) -> list[Path]:
    """Write MJPG `.avi` and mp4v `.mp4` clips in every standard size."""

    return [
        write_clip(directory, codec=codec, size=size)
        for codec in ("mjpg", "mp4v")
        for size in STANDARD_SIZES
    ]


def _validate_size(size: tuple[int, int]) -> None:
    width, height = size
    if not (0 < width <= MAX_SIZE[0] and 0 < height <= MAX_SIZE[1]):
        raise ValueError("size is out of range")
    if width % 2 or height % 2:
        raise ValueError("width and height must be even")


def _frame(index: int, width: int, height: int) -> np.ndarray:
    # Horizontal gradient shifted per frame, a moving box and the frame number.
    columns = (np.arange(width, dtype=np.int64) * 255 // max(width - 1, 1)).astype(np.uint8)
    frame = np.empty((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = columns
    frame[:, :, 1] = np.uint8((index * 5) % 256)
    frame[:, :, 2] = 255 - columns

    box = max(height // 6, 8)
    x = (index * (width - box)) // max(CLIP_FRAMES - 1, 1)
    y = (height - box) // 2
    cv2.rectangle(frame, (x, y), (x + box, y + box), (255, 255, 255), thickness=-1)

    scale = height / 240
    cv2.putText(
        frame,
        f"frame {index:03d}",
        (int(10 * scale), int(40 * scale)),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (0, 0, 0),
        thickness=max(int(2 * scale), 1),
        lineType=cv2.LINE_8,
    )
    return frame


def _decodes_all_frames(path: Path) -> bool:
    capture = cv2.VideoCapture(str(path))
    try:
        frames = 0
        while capture.grab():
            frames += 1
        return frames == CLIP_FRAMES
    finally:
        capture.release()


def _parse_size(value: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in value.lower().split("x"))
        size = (width, height)
        _validate_size(size)
    except ValueError as error:
        raise argparse.ArgumentTypeError("size must be WxH with even values") from error
    return size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m flowsight.video.fixtures",
        description="Genera un clip sintético de prueba y muestra su ruta.",
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument("--size", type=_parse_size, default=(1280, 720), metavar="WxH")
    parser.add_argument("--codec", choices=("mjpg", "mp4v"), default="mjpg")
    args = parser.parse_args(argv)

    try:
        path = write_clip(args.directory, codec=args.codec, size=args.size)
    except (FileNotFoundError, FixtureWriteError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
