from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import pytest

from flowsight.video.fixtures import (
    CLIP_FPS,
    CLIP_FRAMES,
    STANDARD_SIZES,
    MpegUnavailable,
    write_clip,
    write_mpeg_clip,
)
from flowsight.video.probe import VideoRejected, appears_incomplete, probe_video

MSEC_PER_FRAME = 1000 / CLIP_FPS
_REAL_VIDEO_CAPTURE = cv2.VideoCapture


@pytest.fixture(scope="module")
def clips_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("probe-clips")


@pytest.fixture(scope="module")
def mjpg_clip(clips_dir: Path) -> Path:
    return write_clip(clips_dir, codec="mjpg", size=(640, 480))


@pytest.fixture(scope="module")
def mpeg_clip(clips_dir: Path) -> Path:
    try:
        return write_mpeg_clip(clips_dir)
    except MpegUnavailable as error:
        pytest.skip(f"el OpenCV instalado no escribe MPEG-1 decodificable: {error}")


class _HeaderOverride:
    """Real capture whose fps header and position clock are replaced."""

    def __init__(self, path: str, *args: object, fps: float, msec_per_frame: float) -> None:
        self._capture = _REAL_VIDEO_CAPTURE(path, *args)
        self._fps = fps
        self._msec_per_frame = msec_per_frame
        self._grabbed = 0

    def grab(self) -> bool:
        ok = self._capture.grab()
        if ok:
            self._grabbed += 1
        return ok

    def read(self) -> tuple[bool, np.ndarray | None]:
        ok, frame = self._capture.read()
        if ok:
            self._grabbed += 1
        return ok, frame

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_FPS:
            return self._fps
        if prop == cv2.CAP_PROP_POS_MSEC:
            # Timestamp of the last grabbed frame, independent of the backend.
            return max(self._grabbed - 1, 0) * self._msec_per_frame
        return self._capture.get(prop)

    def __getattr__(self, name: str) -> object:
        return getattr(self._capture, name)


def _override_header(monkeypatch: pytest.MonkeyPatch, fps: float, msec_per_frame: float) -> None:
    def factory(path: str, *args: object) -> _HeaderOverride:
        return _HeaderOverride(path, *args, fps=fps, msec_per_frame=msec_per_frame)

    monkeypatch.setattr(cv2, "VideoCapture", factory)


def _decode_jpeg(data: bytes) -> np.ndarray:
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame


@pytest.mark.parametrize("codec", ["mjpg", "mp4v"])
@pytest.mark.parametrize("size", STANDARD_SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
def test_probe_reports_counted_frames_header_fps_and_reference_frame(
    clips_dir: Path, codec: str, size: tuple[int, int]
) -> None:
    path = write_clip(clips_dir, codec=codec, size=size)

    result = probe_video(path)

    width, height = size
    assert (result.width, result.height) == (width, height)
    assert result.frame_count == CLIP_FRAMES
    assert result.declared_frame_count == CLIP_FRAMES
    assert result.fps == Decimal(CLIP_FPS)
    assert result.fps_is_estimated is False
    assert result.duration_seconds == Decimal(CLIP_FRAMES) / result.fps
    assert result.reference_frame_index == 0
    assert result.reference_timestamp_seconds == Decimal(0)
    assert result.reference_jpeg[:2] == b"\xff\xd8"
    assert _decode_jpeg(result.reference_jpeg).shape[:2] == (height, width)


def test_probe_counts_frames_with_grab_not_the_header(
    monkeypatch: pytest.MonkeyPatch, mjpg_clip: Path
) -> None:
    class WrongFrameCount(_HeaderOverride):
        def get(self, prop: int) -> float:
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return CLIP_FRAMES * 3
            return super().get(prop)

    monkeypatch.setattr(
        cv2,
        "VideoCapture",
        lambda path, *args: WrongFrameCount(
            path, *args, fps=CLIP_FPS, msec_per_frame=MSEC_PER_FRAME
        ),
    )

    result = probe_video(mjpg_clip)

    assert result.frame_count == CLIP_FRAMES
    assert result.duration_seconds == Decimal(CLIP_FRAMES) / Decimal(CLIP_FPS)


@pytest.mark.parametrize("header_fps", [0.0, -25.0, 240.5, 1000.0, math.nan])
def test_probe_estimates_fps_when_header_is_out_of_range(
    monkeypatch: pytest.MonkeyPatch, mjpg_clip: Path, header_fps: float
) -> None:
    _override_header(monkeypatch, fps=header_fps, msec_per_frame=MSEC_PER_FRAME)

    result = probe_video(mjpg_clip)

    assert result.fps_is_estimated is True
    assert result.fps == Decimal(CLIP_FPS)
    assert result.frame_count == CLIP_FRAMES
    assert result.duration_seconds == Decimal(CLIP_FRAMES) / result.fps


def test_probe_accepts_header_fps_at_upper_bound(
    monkeypatch: pytest.MonkeyPatch, mjpg_clip: Path
) -> None:
    _override_header(monkeypatch, fps=240.0, msec_per_frame=MSEC_PER_FRAME)

    result = probe_video(mjpg_clip)

    assert result.fps == Decimal(240)
    assert result.fps_is_estimated is False


def test_probe_rejects_video_without_measurable_fps(
    monkeypatch: pytest.MonkeyPatch, mjpg_clip: Path
) -> None:
    _override_header(monkeypatch, fps=0.0, msec_per_frame=0.0)

    with pytest.raises(VideoRejected) as excinfo:
        probe_video(mjpg_clip)

    assert excinfo.value.code == "fps_unknown"


def test_probe_rejects_renamed_text_as_unsupported_format(tmp_path: Path) -> None:
    path = tmp_path / "notas.mp4"
    path.write_text("esto no es un video\n" * 100, encoding="utf-8")

    with pytest.raises(VideoRejected) as excinfo:
        probe_video(path)

    assert excinfo.value.code == "unsupported_format"


def test_probe_rejects_truncated_video_without_decodable_frames(
    tmp_path: Path, mjpg_clip: Path
) -> None:
    data = mjpg_clip.read_bytes()
    # Keep the AVI headers and cut inside the first frame: OpenCV opens the file
    # but cannot decode any frame.
    path = tmp_path / "truncado.avi"
    path.write_bytes(data[: data.index(b"movi") + 64])
    capture = cv2.VideoCapture(str(path))
    try:
        assert capture.isOpened(), "el fixture truncado debe abrir para probar este caso"
    finally:
        capture.release()

    with pytest.raises(VideoRejected) as excinfo:
        probe_video(path)

    assert excinfo.value.code == "no_decodable_frames"


def test_probe_counts_mpeg_frames_and_derives_duration_from_the_count(mpeg_clip: Path) -> None:
    result = probe_video(mpeg_clip)

    assert result.frame_count == CLIP_FRAMES
    assert result.duration_seconds == Decimal(result.frame_count) / result.fps
    assert result.reference_frame_index == 0
    assert result.reference_jpeg[:2] == b"\xff\xd8"
    assert _decode_jpeg(result.reference_jpeg).shape[:2] == (480, 640)


def test_probe_reports_declared_frame_count_of_a_video_cut_in_half(
    tmp_path: Path, clips_dir: Path
) -> None:
    source = write_clip(clips_dir, codec="mjpg", size=(1280, 720))
    data = source.read_bytes()
    # Same cut as the manual validation of T049 (scenario 1.4): the AVI header still
    # declares every frame, but only about half of them can be decoded.
    path = tmp_path / "mitad.avi"
    path.write_bytes(data[: len(data) // 2])

    result = probe_video(path)

    assert result.declared_frame_count == CLIP_FRAMES
    assert 0 < result.frame_count < CLIP_FRAMES
    assert appears_incomplete(result.frame_count, result.declared_frame_count) is True


@pytest.mark.parametrize("header_count", [0.0, -1.0, math.nan, math.inf])
def test_probe_ignores_header_frame_count_that_is_not_finite_and_positive(
    monkeypatch: pytest.MonkeyPatch, mjpg_clip: Path, header_count: float
) -> None:
    class HeaderFrameCount(_HeaderOverride):
        def get(self, prop: int) -> float:
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return header_count
            return super().get(prop)

    monkeypatch.setattr(
        cv2,
        "VideoCapture",
        lambda path, *args: HeaderFrameCount(
            path, *args, fps=CLIP_FPS, msec_per_frame=MSEC_PER_FRAME
        ),
    )

    result = probe_video(mjpg_clip)

    assert result.declared_frame_count is None
    assert result.frame_count == CLIP_FRAMES


@pytest.mark.parametrize(
    ("frame_count", "declared_frame_count", "expected"),
    [
        # Below 250 declared frames the margin is 5 frames.
        (45, 50, False),
        (44, 50, True),
        (50, 50, False),
        (60, 50, False),
        # ceil(0.02 * 251) = 6.
        (245, 251, False),
        (244, 251, True),
        # 2 % of 1000 = 20.
        (980, 1000, False),
        (979, 1000, True),
        (26, 50, True),
        (1, None, False),
    ],
)
def test_appears_incomplete_uses_the_larger_of_5_frames_and_2_percent(
    frame_count: int, declared_frame_count: int | None, expected: bool
) -> None:
    assert appears_incomplete(frame_count, declared_frame_count) is expected
