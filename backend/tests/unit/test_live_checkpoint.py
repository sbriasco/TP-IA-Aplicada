"""A slow model cannot delay a checkpoint or grow a failing write buffer."""

import threading
from types import SimpleNamespace

import pytest

from flowsight.capture.contracts import CaptureError
from flowsight.worker.live_checkpoint import LiveCheckpointWriter


def test_owner_loss_stops_writer_without_database_retry_grace():
    stopped = threading.Event()

    def no_longer_owner(_):
        raise CaptureError("worker_owner_lost")

    writer = LiveCheckpointWriter(
        no_longer_owner, interval_s=0.01, on_failure=lambda _: stopped.set()
    )
    writer.start()
    try:
        writer.submit({"revision": 1}, facts=[], slots={}, buckets=[])
        assert stopped.wait(0.5)
        assert writer.error == "worker_owner_lost" and writer.checkpoint_revision == 0
    finally:
        writer.close()


def test_flush_runs_without_a_new_frame_or_inference_return():
    saved = threading.Event()
    writer = LiveCheckpointWriter(lambda snapshot: saved.set(), interval_s=0.05)
    writer.start()
    try:
        writer.submit({"revision": 1}, facts=[], slots={}, buckets=[])
        assert saved.wait(0.5)
        assert writer.checkpoint_revision == 1
        assert writer.pending_counts == (0, 0, 0)
    finally:
        writer.close()


def test_updates_during_write_keep_the_newer_slot_and_bucket():
    entered, release = threading.Event(), threading.Event()
    writes = []

    def persist(snapshot):
        writes.append(snapshot)
        if len(writes) == 1:
            entered.set()
            assert release.wait(1)

    writer = LiveCheckpointWriter(persist, interval_s=0.02)
    writer.start()
    first, second = SimpleNamespace(slot_index=0, value=1), SimpleNamespace(slot_index=0, value=2)
    try:
        writer.submit(
            {"revision": 1},
            facts=[SimpleNamespace(candidate_sequence=1)],
            slots={0: first},
            buckets=[{"shop_id": "shop", "bucket_index": 0, "revision": 1}],
        )
        assert entered.wait(0.5)
        writer.submit(
            {"revision": 2},
            facts=[SimpleNamespace(candidate_sequence=2)],
            slots={0: second},
            buckets=[{"shop_id": "shop", "bucket_index": 0, "revision": 2}],
        )
        release.set()
        writer.flush()
        assert writes[-1].metadata["revision"] == 2
        assert writes[-1].slots[0] is second and writes[-1].buckets[0]["revision"] == 2
        assert writer.pending_counts == (0, 0, 0)
    finally:
        release.set()
        writer.close()


def test_database_outage_preserves_uncommitted_deltas_then_stops_at_deadline():
    stopped = threading.Event()

    def unavailable(_):
        raise RuntimeError("database down")

    writer = LiveCheckpointWriter(
        unavailable, interval_s=0.01, failure_timeout_s=0.08, on_failure=lambda _: stopped.set()
    )
    writer.start()
    try:
        writer.submit(
            {"revision": 1}, facts=[SimpleNamespace(candidate_sequence=1)], slots={}, buckets=[]
        )
        assert stopped.wait(0.5)
        assert writer.error == "database_unavailable" and writer.checkpoint_revision == 0
        assert writer.pending_counts[0] == 1
    finally:
        writer.close()


def test_fact_capacity_fails_without_accepting_an_unbounded_batch():
    writer = LiveCheckpointWriter(lambda _: None, max_facts=2)
    writer.submit(
        {"revision": 1}, facts=[SimpleNamespace(candidate_sequence=1)], slots={}, buckets=[]
    )
    with pytest.raises(CaptureError, match="live_buffer_limit"):
        writer.submit(
            {"revision": 2},
            facts=[SimpleNamespace(candidate_sequence=2), SimpleNamespace(candidate_sequence=3)],
            slots={},
            buckets=[],
        )
    assert writer.pending_counts[0] <= 2
