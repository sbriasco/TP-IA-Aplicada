from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import cv2

from flowsight.video.fixtures import (
    CLIP_FPS,
    CLIP_FRAMES,
    MpegUnavailable,
    write_clip,
    write_mpeg_clip,
    write_standard_clips,
)


def count_frames(path: Path) -> tuple[int, int, int, float]:
    capture = cv2.VideoCapture(str(path))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        ok, frame = capture.read()
        if not ok:
            return 0, 0, 0, fps
        height, width = frame.shape[:2]
        frames = 1
        while capture.grab():
            frames += 1
        return frames, width, height, fps
    finally:
        capture.release()


def read_frame(path: Path, index: int):
    capture = cv2.VideoCapture(str(path))
    try:
        for _ in range(index):
            capture.grab()
        ok, frame = capture.read()
        assert ok
        return frame
    finally:
        capture.release()


class VideoFixturesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_standard_clips_cover_codecs_and_aspect_ratios(self) -> None:
        clips = write_standard_clips(self.directory)

        found = set()
        for clip in clips:
            self.assertEqual(clip.parent, self.directory)
            frames, width, height, fps = count_frames(clip)
            self.assertEqual(frames, CLIP_FRAMES, clip.name)
            self.assertEqual(fps, CLIP_FPS, clip.name)
            found.add((clip.suffix, width, height))

        expected = {
            (suffix, width, height)
            for suffix in (".avi", ".mp4")
            for width, height in ((1280, 720), (1920, 1080), (640, 480))
        }
        self.assertEqual(found, expected)

    def test_frames_differ_so_reference_frame_is_not_trivial(self) -> None:
        clip = write_clip(self.directory, codec="mjpg", size=(640, 480))

        first = read_frame(clip, 0)
        last = read_frame(clip, CLIP_FRAMES - 1)

        self.assertGreater(cv2.absdiff(first, last).mean(), 5)

    def test_clips_are_deterministic(self) -> None:
        other = Path(self._tmp.name) / "other"
        other.mkdir()

        first = write_clip(self.directory, codec="mjpg", size=(640, 480))
        second = write_clip(other, codec="mjpg", size=(640, 480))

        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_mpeg_clip_is_written_or_reported_unavailable(self) -> None:
        try:
            clip = write_mpeg_clip(self.directory)
        except MpegUnavailable as error:
            self.skipTest(f"MPEG-1 no disponible con este OpenCV: {error}")

        frames, width, height, _ = count_frames(clip)
        self.assertEqual(clip.suffix, ".mpg")
        self.assertEqual((width, height), (640, 480))
        self.assertEqual(frames, CLIP_FRAMES)

    def test_rejects_unknown_codec_and_invalid_size(self) -> None:
        with self.assertRaises(ValueError):
            write_clip(self.directory, codec="h264", size=(640, 480))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            write_clip(self.directory, codec="mjpg", size=(641, 480))

    def test_rejects_missing_directory(self) -> None:
        with self.assertRaises(FileNotFoundError):
            write_clip(self.directory / "missing", codec="mjpg", size=(640, 480))

    def test_cli_prints_generated_path(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "flowsight.video.fixtures",
                str(self.directory),
                "--size",
                "640x480",
                "--codec",
                "mp4v",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        clip = Path(result.stdout.strip())
        self.assertEqual(clip.parent, self.directory)
        self.assertEqual(clip.suffix, ".mp4")
        self.assertEqual(count_frames(clip)[1:3], (640, 480))

    def test_cli_rejects_invalid_size(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "flowsight.video.fixtures", str(self.directory), "--size", "x"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
