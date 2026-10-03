"""One-frame lookahead so the next decode overlaps the current analysis."""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from typing import Protocol


class VideoCapture(Protocol):
    def read(self) -> tuple[bool, object]:
        """Return the next decoded frame."""


def iter_video_frames(capture: VideoCapture, frames_total: int) -> Iterator[tuple[bool, object]]:
    """Yield every frame in order. The following read runs while the caller works.

    Stopping early joins the decode thread before the caller releases the capture.
    A read error is raised on the consumer. Frames are never skipped.
    """

    if frames_total <= 0:
        return
    ahead: queue.Queue[tuple[bool, object] | BaseException | None] = queue.Queue(maxsize=1)
    stop = threading.Event()

    def produce() -> None:
        try:
            for _ in range(frames_total):
                if stop.is_set():
                    return
                item = capture.read()
                if not _offer(ahead, item, stop):
                    return
        except Exception as exc:
            _offer(ahead, exc, stop)
        finally:
            _offer(ahead, None, stop)

    thread = threading.Thread(target=produce, name="flowsight-frame-decode", daemon=True)
    thread.start()
    try:
        received = 0
        while received < frames_total:
            item = ahead.get()
            if isinstance(item, Exception):
                raise item
            if item is None:
                return
            received += 1
            yield item
    finally:
        stop.set()
        while True:
            try:
                ahead.get_nowait()
            except queue.Empty:
                break
        thread.join(timeout=5)


def _offer(
    ahead: queue.Queue[tuple[bool, object] | BaseException | None],
    item: tuple[bool, object] | BaseException | None,
    stop: threading.Event,
) -> bool:
    while not stop.is_set():
        try:
            ahead.put(item, timeout=0.05)
            return True
        except queue.Full:
            continue
    return False
