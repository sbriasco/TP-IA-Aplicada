"""Heartbeat stays independent of slow inference and reports loss of ownership."""

import threading
import time
from unittest.mock import Mock

import pytest

from flowsight.worker.live_control import LiveMachineError, MachineHeartbeat


def test_heartbeat_runs_independently_and_stops() -> None:
    lease = Mock()
    heartbeat = MachineHeartbeat(lease, interval_s=0.02)
    heartbeat.start()
    time.sleep(0.1)
    heartbeat.stop()
    assert lease.heartbeat.call_count >= 1
    count = lease.heartbeat.call_count
    time.sleep(0.04)
    assert lease.heartbeat.call_count == count
    heartbeat.raise_if_failed()


def test_lost_ownership_notifies_capture_supervisor() -> None:
    lease = Mock()
    lease.heartbeat.side_effect = LiveMachineError("worker_owner_lost")
    lost = threading.Event()
    heartbeat = MachineHeartbeat(lease, interval_s=0.02, on_lost=lost.set)
    try:
        heartbeat.start()
        assert lost.wait(1)
        with pytest.raises(LiveMachineError, match="worker_owner_lost"):
            heartbeat.raise_if_failed()
    finally:
        heartbeat.stop()


def test_live_supervisor_closes_capture_on_owner_loss_without_database_grace():
    from flowsight.worker.live_analysis import LiveStopControl

    closed = threading.Event()
    source = Mock()
    source.stop.side_effect = closed.set
    factory = Mock()

    def owner_health():
        raise LiveMachineError("worker_owner_lost")

    control = LiveStopControl(factory, "job", source, health=owner_health)
    try:
        control.start()
        assert closed.wait(1)
        assert control.error == "worker_owner_lost" and control.stopping.is_set()
        factory.assert_not_called()
    finally:
        control.close()
