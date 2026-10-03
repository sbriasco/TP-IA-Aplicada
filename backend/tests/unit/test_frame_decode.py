"""Decode the next frame while the caller still holds the current one."""

from __future__ import annotations

import threading

from flowsight.video.decode import iter_video_frames


def test_frames_are_yielded_in_order_including_a_failed_read() -> None:
    class Capture:
        def __init__(self) -> None:
            self.index = 0

        def read(self) -> tuple[bool, int]:
            index = self.index
            self.index += 1
            return index != 1, index

    assert list(iter_video_frames(Capture(), 3)) == [(True, 0), (False, 1), (True, 2)]


def test_the_next_frame_is_decoded_while_the_current_one_is_processed() -> None:
    current = threading.Event()
    decoded_ahead = threading.Event()

    class Capture:
        def __init__(self) -> None:
            self.index = 0

        def read(self) -> tuple[bool, int]:
            index = self.index
            self.index += 1
            if index == 1:
                assert current.wait(timeout=2)
                decoded_ahead.set()
            return True, index

    frames: list[int] = []
    for ok, frame in iter_video_frames(Capture(), 3):
        assert ok is True
        if frame == 0:
            current.set()
            assert decoded_ahead.wait(timeout=2)
        frames.append(frame)

    assert frames == [0, 1, 2]
