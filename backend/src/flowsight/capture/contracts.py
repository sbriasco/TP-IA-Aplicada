"""A future IP adapter can implement FrameSource without changing analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class CaptureSettings:
    device_index: int
    backend: Literal["auto", "dshow", "msmf", "fake"] = "auto"
    requested_width: int = 1280
    requested_height: int = 720


@dataclass(frozen=True)
class CapturedFrame:
    image: NDArray[np.uint8]
    sequence: int
    segment_index: int
    captured_monotonic_ns: int
    timestamp_seconds: Decimal
    width: int
    height: int


@dataclass(frozen=True)
class CaptureStatus:
    state: Literal["connected", "interrupted", "closed"]
    backend: str
    width: int | None = None
    height: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CaptureProbeResult:
    jpeg: bytes
    width: int
    height: int
    backend: str
    device_index: int
    reported_fps: float | None = None


@dataclass(frozen=True)
class CaptureDiscontinuity:
    reason: str
    last_valid_timestamp: Decimal
    first_resumed_timestamp: Decimal | None = None


class CaptureError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FrameSource(Protocol):
    def start(self) -> None: ...

    def read_latest(self, after_sequence: int, timeout_s: float) -> CapturedFrame | None: ...

    def stop(self, timeout_s: float = 2.0) -> None: ...

    def status(self) -> CaptureStatus: ...


class SourceFactory(Protocol):
    def __call__(
        self,
        settings: CaptureSettings,
        *,
        epoch_ns: int | None = None,
        segment_index: int = 0,
        initial_sequence: int = 0,
    ) -> FrameSource: ...
