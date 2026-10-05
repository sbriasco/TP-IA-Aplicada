"""Publisher buffering stays at one message even while the API is disconnected."""

from types import SimpleNamespace

import pytest

from flowsight.worker.live_channel import WorkerLiveChannel


def test_publisher_replaces_pending_without_network():
    publisher = WorkerLiveChannel(SimpleNamespace(), None, None)
    for sequence in range(1000):
        publisher.publish({"capture_sequence": sequence})
    assert publisher.pending_count == 1
    assert publisher.pending_message["capture_sequence"] == 999


def test_publisher_drops_stale_frame():
    publisher = WorkerLiveChannel(SimpleNamespace(), None, None, clock=lambda: 100.0)
    publisher.publish({"capture_sequence": 1})
    publisher.clock = lambda: 111.0
    assert publisher.pending_message is None


@pytest.mark.parametrize("source_kind,expected_backend", [("fake", "fake"), ("webcam", "dshow")])
def test_probe_uses_the_actual_capture_constructor_contract(
    monkeypatch, source_kind, expected_backend
):
    import sys
    import uuid
    from datetime import UTC, datetime, timedelta

    import numpy as np

    import flowsight.worker.live_channel as module
    from flowsight.capture.contracts import CaptureStatus

    epoch, reservation = uuid.uuid4(), uuid.uuid4()
    machine = SimpleNamespace(
        owner_epoch=epoch,
        reservation_id=reservation,
        reserved_until=datetime.now(UTC) + timedelta(seconds=10),
    )

    class Database:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get(self, *_):
            return machine

    class Source:
        def __init__(self, settings):
            assert settings.backend == expected_backend

        def start(self):
            pass

        def read_latest(self, *_):
            return SimpleNamespace(
                image=np.zeros((180, 320, 3), dtype=np.uint8), width=320, height=180
            )

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def stop(self):
            pass

    monkeypatch.setattr(module, "ProcessFrameSource", Source)
    monkeypatch.setattr(sys, "platform", "win32")
    publisher = WorkerLiveChannel(
        SimpleNamespace(
            machine_id="expo-test", live_capture_source=source_kind, environment="test"
        ),
        Database,
        SimpleNamespace(owner_epoch=epoch),
    )
    result = publisher._probe({"reservation_id": str(reservation), "device_index": 0})
    assert result["width"] == 320 and result["image_base64"]
