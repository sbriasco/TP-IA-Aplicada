"""One checkpoint atomically persists events, minute corrections and sample slots."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from flowsight.capture.contracts import CapturedFrame
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCrossing,
    LiveCrossingBucket,
    LivePositionSample,
    ProcessingJob,
    WorkerMachine,
)
from flowsight.services.live_results import persist_live_checkpoint
from flowsight.vision.detector import Detection
from flowsight.vision.live_buckets import LiveBuckets
from flowsight.vision.live_sampling import LivePositionSampler
from flowsight.vision.live_spatial import LiveSpatialCounter
from flowsight.worker.lifecycle import claim_next_job
from flowsight.worker.video_analysis import _scene_context


def test_checkpoint_from_previous_machine_owner_is_rejected(live_job):
    import uuid
    from types import SimpleNamespace

    from flowsight.capture.contracts import CaptureError

    factory, job_id, lease = live_job
    with factory.begin() as database:
        job = claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        session_id = job.session_id
        database.get(WorkerMachine, "expo-runner").owner_epoch = uuid.uuid4()
    frame = SimpleNamespace(segment_index=0, sequence=1, timestamp_seconds=Decimal("1"))
    with pytest.raises(CaptureError, match="worker_owner_lost"), factory.begin() as database:
        persist_live_checkpoint(
            database,
            job_id,
            session_id,
            uuid.uuid4(),
            datetime.now(UTC),
            frame,
            1,
            1,
            Decimal("1"),
            Decimal(0),
            SimpleNamespace(candidates_seen=0),
            SimpleNamespace(discarded_crossings=0),
            [],
            {},
            datetime.now(UTC),
            owner_epoch=lease.owner_epoch,
            machine_id="expo-runner",
        )
    with factory() as database:
        assert database.get(LiveAnalysisState, job_id).revision == 0


def test_late_checkpoint_cannot_reopen_a_terminal_job(live_job):
    import uuid
    from types import SimpleNamespace

    from flowsight.services.jobs import transition_job

    factory, job_id, lease = live_job
    with factory.begin() as database:
        job = claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        session_id = job.session_id
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "ended"
        state.elapsed_capture_seconds = Decimal("1")
        state.revision = 1
        transition_job(
            database,
            job_id=job_id,
            target=JobStatus.FAILED,
            occurred_at=datetime.now(UTC),
            reason_code="database_unavailable",
            failure_message="Checkpoint conservado.",
        )
    frame = SimpleNamespace(segment_index=0, sequence=2, timestamp_seconds=Decimal("2"))
    with factory.begin() as database:
        persist_live_checkpoint(
            database,
            job_id,
            session_id,
            uuid.uuid4(),
            datetime.now(UTC),
            frame,
            2,
            2,
            Decimal("2"),
            Decimal(0),
            SimpleNamespace(candidates_seen=0),
            SimpleNamespace(discarded_crossings=0),
            [],
            {},
            datetime.now(UTC),
        )
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert state.capture_status == "ended"
        assert state.revision == 1 and state.elapsed_capture_seconds == Decimal("1")
        assert database.get(ProcessingJob, job_id).status == JobStatus.FAILED


def test_atomic_checkpoint_is_idempotent_and_keeps_original_minute(live_job):
    import uuid

    factory, job_id, lease = live_job
    with factory.begin() as database:
        job = claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        session_id = job.session_id
        _, _, shops = _scene_context(database, job.scene_version_id)
    shop_id = shops[0].shop_id
    counter, sampler = LiveSpatialCounter(shops), LivePositionSampler()
    buckets = LiveBuckets([shop_id])
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    previous = None
    all_facts = []
    for sequence, (timestamp, y) in enumerate([("59.7", 144.0), ("59.8", 36.0), ("60.2", 36.0)], 1):
        frame = CapturedFrame(
            image, sequence, 0, int(Decimal(timestamp) * 10**9), Decimal(timestamp), 320, 180
        )
        detection = Detection(1, (100.0, y - 20, 120.0, y))
        facts = counter.observe(frame, [detection])
        all_facts.extend(facts)
        sampler.observe(
            segment_index=0,
            track_id=1,
            sequence=sequence,
            timestamp_s=frame.timestamp_seconds,
            foot=(0.5, y / 180),
        )
        buckets.observe(
            frame.timestamp_seconds,
            facts=facts,
            pending=counter.pending_candidates,
            interval=None if previous is None else (previous, frame.timestamp_seconds, True),
            revision=sequence,
        )
        previous = frame.timestamp_seconds
    slots = {change.slot_index: change for change in sampler.drain_changes()}
    segment = uuid.uuid4()
    checkpoint_args = (
        job_id,
        session_id,
        segment,
        datetime.now(UTC),
        frame,
        3,
        3,
        Decimal(".5"),
        Decimal(0),
        sampler,
        counter,
        all_facts,
        slots,
        datetime.now(UTC),
    )
    invalid_args = list(checkpoint_args)
    invalid_args[12] = {
        slot: replace(change, sample=replace(change.sample, foot=(2.0, 0.5)))
        for slot, change in slots.items()
    }
    with pytest.raises(IntegrityError), factory.begin() as database:
        persist_live_checkpoint(database, *invalid_args, bucket_rows=buckets.dirty_rows())
    with factory() as database:
        assert database.query(LiveCrossing).filter_by(job_id=job_id).count() == 0
        assert database.query(LiveCrossingBucket).filter_by(job_id=job_id).count() == 0
        assert database.get(LiveAnalysisState, job_id).revision == 0
    for _ in range(2):
        with factory.begin() as database:
            persist_live_checkpoint(database, *checkpoint_args, bucket_rows=buckets.dirty_rows())
    with factory() as database:
        event = database.scalar(select(LiveCrossing).where(LiveCrossing.job_id == job_id))
        assert event.capture_timestamp_seconds == Decimal("59.8")
        assert event.confirmed_at_capture_seconds == Decimal("60.2")
        assert database.query(LiveCrossing).filter_by(job_id=job_id).count() == 1
        minute = database.get(LiveCrossingBucket, (job_id, shop_id, 0))
        assert minute.entries == 1 and not minute.is_open and minute.pending_count == 0
        assert database.get(LiveCrossingBucket, (job_id, shop_id, 1)).entries == 0
        assert database.query(LivePositionSample).filter_by(job_id=job_id).count() == 2
        assert database.get(LiveAnalysisState, job_id).revision == 3


def test_published_frame_and_accumulated_counts_share_horizon(live_job):
    from types import SimpleNamespace

    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    with factory.begin() as database:
        claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
    trajectory = [("0", 144.0), (".1", 36.0), (".5", 36.0), (".9", 144.0), ("1.3", 144.0)]
    current = [0]
    clock = [1_000_000_000]

    class Source:
        def start(self):
            pass

        def stop(self, timeout_s=2):
            pass

        def read_latest(self, *_args):
            if current[0] == len(trajectory):
                with factory.begin() as database:
                    database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                return None
            timestamp, _ = trajectory[current[0]]
            current[0] += 1
            clock[0] = 1_000_000_000 + int(Decimal(timestamp) * 10**9)
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                current[0],
                0,
                clock[0],
                Decimal(timestamp),
                320,
                180,
            )

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, *_args):
            _, y = trajectory[current[0] - 1]
            return [Detection(1, (100.0, y - 20, 120.0, y))]

    messages = []
    process_live_analysis_job(
        factory,
        job_id,
        settings=SimpleNamespace(preview_max_fps=5),
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: clock[0],
        emit=messages.append,
    )
    updates = [message for message in messages if message["type"] == "live.update"]
    assert updates and updates[0]["shops"][0]["total_crossings"] == 0
    final = updates[-1]
    assert final["capture_timestamp_seconds"] == 1.3 and final["capture_sequence"] == 5
    assert final["shops"][0]["entry_count"] == 1 and final["shops"][0]["exit_count"] == 1
    assert final["shops"][0]["total_crossings"] == 2
    assert final["shops"][0]["entry_direction"] == "a_to_b"
    assert final["minutes"][0]["entries"] == 1 and final["minutes"][0]["exits"] == 1
    assert final["image_media_type"] == "image/jpeg" and final["image_base64"]
