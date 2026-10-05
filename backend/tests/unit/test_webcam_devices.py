import subprocess
from types import SimpleNamespace

import pytest

from flowsight.capture.contracts import CaptureError
from flowsight.capture.devices import list_webcams


@pytest.mark.parametrize("has_windows_flag", [False, True])
def test_windows_enumeration_handles_host_without_windows_flag(monkeypatch, has_windows_flag):
    monkeypatch.setattr("flowsight.capture.devices.sys.platform", "win32")
    if has_windows_flag:
        monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    else:
        monkeypatch.delattr(subprocess, "CREATE_NO_WINDOW", raising=False)

    def enumerate_devices(*args, **kwargs):
        assert kwargs["creationflags"] == (0x08000000 if has_windows_flag else 0)
        return SimpleNamespace(returncode=0, stdout='["USB Webcam"]')

    monkeypatch.setattr("flowsight.capture.devices.subprocess.run", enumerate_devices)
    assert list_webcams() == [{"device_index": 0, "label": "USB Webcam", "verified": False}]


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
