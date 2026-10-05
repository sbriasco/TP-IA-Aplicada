"""Deterministic camera-like frames; never exposed as an HTTP source option."""

import threading
import time
from dataclasses import dataclass

import numpy as np

from flowsight.capture.contracts import CaptureSettings


@dataclass(frozen=True)
class FakeCaptureOptions:
    frame_rate: float = 30
    fail_after: int | None = None
    block_after: int | None = None
    resize_after: int | None = None


class FakeCapture:
    def __init__(self, settings: CaptureSettings, options: FakeCaptureOptions) -> None:
        self.settings = settings
        self.options = options
        self.index = 0

    def read(self):
        if self.options.block_after is not None and self.index >= self.options.block_after:
            threading.Event().wait()
        time.sleep(1 / self.options.frame_rate)
        if self.options.fail_after is not None and self.index >= self.options.fail_after:
            return False, None
        width, height = self.settings.requested_width, self.settings.requested_height
        if self.options.resize_after is not None and self.index >= self.options.resize_after:
            width += 1
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # A moving marker makes drops and freeze visible without files or a real model.
        position = self.index % width
        frame[:, position : position + 2, 1] = 255
        self.index += 1
        return True, frame

    def release(self) -> None:
        pass
