import subprocess
from types import SimpleNamespace

import pytest

from flowsight.capture.contracts import CaptureError
from flowsight.capture.devices import list_webcams


def test_named_devices_keep_native_order_and_duplicate_names(monkeypatch):
    monkeypatch.setattr("flowsight.capture.devices.sys.platform", "win32")
    monkeypatch.setattr(
        "flowsight.capture.devices.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout='["Integrated Camera", "USB Webcam", "USB Webcam"]'
        ),
    )
    assert list_webcams() == [
        {"device_index": 0, "label": "Integrated Camera", "verified": False},
        {"device_index": 1, "label": "USB Webcam", "verified": False},
        {"device_index": 2, "label": "USB Webcam", "verified": False},
    ]


def test_disconnected_machine_has_no_invented_candidates(monkeypatch):
    monkeypatch.setattr("flowsight.capture.devices.sys.platform", "win32")
    monkeypatch.setattr(
        "flowsight.capture.devices.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="[]"),
    )
    assert list_webcams() == []


def test_hung_driver_returns_safe_enumeration_error(monkeypatch):
    monkeypatch.setattr("flowsight.capture.devices.sys.platform", "win32")

    def hung(*args, **kwargs):
        assert kwargs["timeout"] <= 5
        raise subprocess.TimeoutExpired("private-driver", kwargs["timeout"])

    monkeypatch.setattr("flowsight.capture.devices.subprocess.run", hung)
    with pytest.raises(CaptureError, match="device_enumeration_failed"):
        list_webcams()


@pytest.mark.parametrize(
    "payload", ['[" "]', "[123]", '{"private": "driver"}', '["' + "x" * 201 + '"]']
)
def test_invalid_native_response_cannot_reach_selector(monkeypatch, payload):
    monkeypatch.setattr("flowsight.capture.devices.sys.platform", "win32")
    monkeypatch.setattr(
        "flowsight.capture.devices.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=payload),
    )
    with pytest.raises(CaptureError, match="device_enumeration_failed"):
        list_webcams()
