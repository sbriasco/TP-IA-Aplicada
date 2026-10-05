"""Spawn-isolated capture thread and a single shared raw slot, with bounded reads."""

from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
from decimal import Decimal

import numpy as np

from flowsight.capture.contracts import (
    CapturedFrame,
    CaptureError,
    CaptureSettings,
    CaptureStatus,
)
from flowsight.capture.fake import FakeCapture, FakeCaptureOptions

MAX_BYTES = 1920 * 1080 * 3
_BACKENDS = ("auto", "dshow", "msmf", "fake")
_ERRORS = (
    None,
    "device_unavailable",
    "capture_read_timeout",
    "capture_format_changed",
    "capture_resolution_unsupported",
    "capture_process_failed",
    "capture_open_timeout",
)


def _capture_process(
    settings,
    options,
    raw,
    metadata,
    lock,
    state,
    error,
    stop,
    ready,
    epoch_ns,
    segment_index,
    initial_sequence,
):
    """Importable child entry point. No model, database or disk output in this process."""
    del segment_index

    def failed(code):
        error.value = _ERRORS.index(code)
        state.value = 2
        ready.set()

    def capture_loop():
        capture = None
        try:
            if settings.backend == "fake":
                capture, backend = FakeCapture(settings, options), "fake"
            else:
                from flowsight.capture.webcam import open_webcam

                capture, backend = open_webcam(settings)
            sequence = initial_sequence
            epoch = epoch_ns
            dimensions = None
            while not stop.is_set():
                ok, frame = capture.read()
                received_ns = time.monotonic_ns()
                if not ok or frame is None:
                    failed("device_unavailable")
                    return
                if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                    failed("capture_resolution_unsupported")
                    return
                height, width = frame.shape[:2]
                if not 1 <= width <= 1920 or not 1 <= height <= 1080:
                    failed("capture_resolution_unsupported")
                    return
                if dimensions is not None and dimensions != (width, height):
                    failed("capture_format_changed")
                    return
                dimensions = (width, height)
                if epoch is None:
                    epoch = received_ns
                sequence += 1
                if not lock.acquire(timeout=0.05):
                    continue
                try:
                    target = np.frombuffer(raw, dtype=np.uint8, count=frame.size)
                    np.copyto(target, frame.reshape(-1))
                    metadata[:] = (
                        sequence,
                        received_ns,
                        width,
                        height,
                        epoch,
                        _BACKENDS.index(backend),
                    )
                    state.value = 1
                finally:
                    lock.release()
                ready.set()
        except CaptureError as exc:
            failed(exc.code if exc.code in _ERRORS else "capture_process_failed")
        except Exception:
            failed("capture_process_failed")
        finally:
            if capture is not None:
                capture.release()

    thread = threading.Thread(target=capture_loop, daemon=True)
    thread.start()
    started_ns = time.monotonic_ns()
    while not stop.wait(0.05):
        if state.value == 2:
            return
        last_ns = metadata[1] or started_ns
        if time.monotonic_ns() - last_ns > 3_000_000_000:
            failed("capture_read_timeout")
            return
    thread.join(0.1)


class ProcessFrameSource:
    def __init__(
        self,
        settings: CaptureSettings,
        *,
        epoch_ns: int | None = None,
        segment_index: int = 0,
        initial_sequence: int = 0,
        fake_options: FakeCaptureOptions | None = None,
    ) -> None:
        if settings.backend == "fake" and os.environ.get("FLOWSIGHT_ENV") != "test":
            raise CaptureError("fake_source_forbidden")
        if not 1 <= settings.requested_width <= 1920 or not 1 <= settings.requested_height <= 1080:
            raise CaptureError("capture_resolution_unsupported")
        self.settings = settings
        self.segment_index = segment_index
        self.epoch_ns = epoch_ns
        self._last_delivered = initial_sequence
        self._closed = False
        self._started = False
        self._lifecycle_lock = threading.RLock()
        context = mp.get_context("spawn")
        self._raw = context.RawArray("B", MAX_BYTES)
        self._metadata = context.Array("q", (initial_sequence, 0, 0, 0, 0, 0), lock=False)
        self._lock = context.Lock()
        self._state = context.Value("i", 0, lock=False)
        self._error = context.Value("i", 0, lock=False)
        self._stop = context.Event()
        self._ready = context.Event()
        self._process = context.Process(
            target=_capture_process,
            args=(
                settings,
                fake_options or FakeCaptureOptions(),
                self._raw,
                self._metadata,
                self._lock,
                self._state,
                self._error,
                self._stop,
                self._ready,
                epoch_ns,
                segment_index,
                initial_sequence,
            ),
            daemon=True,
        )

    @property
    def running(self) -> bool:
        with self._lifecycle_lock:
            return self._started and not self._closed and self._process.is_alive()

    @property
    def pending_count(self) -> int:
        return int(not self._closed and self._metadata[0] > self._last_delivered)

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._closed or self._started:
                raise CaptureError("capture_process_failed")
            self._process.start()
            self._started = True
        # Opening budget leaves two seconds for cooperative stop + termination.
        if not self._ready.wait(3):
            self.stop()
            raise CaptureError("capture_open_timeout")
        if self._closed or self._state.value != 1:
            reason = _ERRORS[self._error.value] or "capture_process_failed"
            self.stop()
            raise CaptureError(reason)

    def read_latest(self, after_sequence: int, timeout_s: float) -> CapturedFrame | None:
        if self._closed:
            return None
        deadline = time.monotonic() + max(0, timeout_s)
        while True:
            if not self._lock.acquire(timeout=0.05):
                self.stop()
                raise CaptureError("capture_read_timeout")
            try:
                sequence, received, width, height, epoch, _ = self._metadata[:]
                if sequence > after_sequence and received:
                    image = np.frombuffer(self._raw, dtype=np.uint8, count=width * height * 3)
                    image = image.reshape(height, width, 3).copy()
                    self._last_delivered = sequence
                    self.epoch_ns = epoch
                    return CapturedFrame(
                        image,
                        sequence,
                        self.segment_index,
                        received,
                        Decimal(received - epoch) / Decimal(10**9),
                        width,
                        height,
                    )
            finally:
                self._lock.release()
            if self._state.value == 2 or not self.running:
                raise CaptureError(_ERRORS[self._error.value] or "capture_process_failed")
            if time.monotonic() >= deadline:
                return None
            time.sleep(min(0.005, max(0, deadline - time.monotonic())))

    def status(self) -> CaptureStatus:
        _, _, width, height, _, backend = self._metadata[:]
        state = (
            "closed" if self._closed else "interrupted" if self._state.value == 2 else "connected"
        )
        return CaptureStatus(
            state, _BACKENDS[backend], width or None, height or None, _ERRORS[self._error.value]
        )

    def stop(self, timeout_s: float = 2.0) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            self._ready.set()
            if self._started:
                self._process.join(min(1.0, max(0, timeout_s / 2)))
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(min(1.0, max(0, timeout_s / 2)))
                if self._process.is_alive():
                    self._process.kill()
                    self._process.join(0.1)
                if not self._process.is_alive():
                    self._process.close()
