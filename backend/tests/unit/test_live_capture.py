"""Spawn-safe capture: only the newest frame, bounded stop even with blocked read."""

import time

import pytest

from flowsight.capture.contracts import CaptureError, CaptureSettings
from flowsight.capture.fake import FakeCaptureOptions
from flowsight.capture.process import ProcessFrameSource


def test_webcam_uses_local_backends_and_never_opens_a_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    from flowsight.capture import webcam

    closed, opened = Mock(), Mock()
    closed.isOpened.return_value = False
    opened.isOpened.return_value = True
    factory = Mock(side_effect=[closed, opened])
    monkeypatch.setattr(webcam.cv2, "VideoCapture", factory)
    monkeypatch.setattr(webcam.sys, "platform", "win32")
    camera, backend = webcam.open_webcam(CaptureSettings(2))
    assert camera is opened
    assert backend == "msmf"
    assert factory.call_args_list[0].args == (2, webcam.cv2.CAP_DSHOW)
    assert factory.call_args_list[1].args == (2, webcam.cv2.CAP_MSMF)
    closed.release.assert_called_once()
    with pytest.raises(CaptureError, match="device_unavailable"):
        webcam.open_webcam(CaptureSettings("rtsp://invalid"))
    assert factory.call_count == 2


@pytest.fixture(autouse=True)
def fake_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")


def test_fast_source_keeps_latest_frame_only() -> None:
    source = ProcessFrameSource(
        CaptureSettings(0, backend="fake", requested_width=64, requested_height=48),
        fake_options=FakeCaptureOptions(frame_rate=200),
    )
    try:
        source.start()
        first = source.read_latest(-1, 0.2)
        assert first is not None
        time.sleep(0.15)
        second = source.read_latest(first.sequence, 0.2)
        assert second is not None
        assert second.sequence > first.sequence + 1
        assert second.timestamp_seconds > first.timestamp_seconds
        assert source.pending_count <= 1
        assert second.image.shape == (48, 64, 3)
    finally:
        source.stop()
    assert not source.running
    assert source.status().state == "closed"


def test_stop_with_blocked_read_releases_process_in_two_seconds() -> None:
    source = ProcessFrameSource(
        CaptureSettings(0, backend="fake", requested_width=64, requested_height=48),
        fake_options=FakeCaptureOptions(block_after=1),
    )
    source.start()
    time.sleep(0.1)
    started = time.monotonic()
    source.stop()
    assert time.monotonic() - started <= 2
    assert not source.running


def test_resolution_change_is_reported_as_discontinuity() -> None:
    source = ProcessFrameSource(
        CaptureSettings(0, backend="fake", requested_width=64, requested_height=48),
        fake_options=FakeCaptureOptions(resize_after=2),
    )
    try:
        source.start()
        deadline = time.monotonic() + 2
        while source.status().state == "connected" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert source.status().state == "interrupted"
        assert source.status().reason == "capture_format_changed"
    finally:
        source.stop()


def test_fake_source_cannot_be_enabled_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOWSIGHT_ENV", "development")
    with pytest.raises(CaptureError, match="fake_source_forbidden"):
        ProcessFrameSource(CaptureSettings(0, backend="fake"))


def test_concurrent_stop_closes_the_process_handle_only_once():
    import threading

    barrier = threading.Barrier(2)
    source = ProcessFrameSource(
        CaptureSettings(0, backend="fake", requested_width=64, requested_height=48)
    )

    class Process:
        closed = False

        def join(self, *_):
            try:
                barrier.wait(0.1)
            except threading.BrokenBarrierError:
                pass

        def is_alive(self):
            return False

        def close(self):
            if self.closed:
                raise ValueError("process object is closed")
            self.closed = True

    process = Process()
    source._process = process
    source._started = True
    errors = []

    def stop():
        try:
            source.stop()
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=stop) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
    assert errors == []
    assert process.closed and source.status().state == "closed"
