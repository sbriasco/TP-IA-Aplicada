"""Manual pause freezes observations, not the capture timeline or saved totals."""

import threading
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
from sqlalchemy import select

from flowsight.capture.contracts import CapturedFrame, CaptureError, CaptureStatus
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveCrossing,
    LiveInterruption,
    ProcessingJob,
    SceneVersionShop,
    SceneZone,
    ZoneRole,
)
from flowsight.services.live_jobs import (
    request_live_continue,
    request_live_pause,
    request_live_stop,
)
from flowsight.services.live_results import persist_live_checkpoint
from flowsight.vision.detector import Detection
from flowsight.worker.lifecycle import claim_next_job, recover_interrupted_jobs
from flowsight.worker.live_analysis import process_live_analysis_job


def wait_state(factory, job_id, expected, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with factory() as database:
            state = database.get(LiveAnalysisState, job_id)
            if state.capture_status == expected:
                return state
        time.sleep(0.02)
    raise AssertionError(f"Never reached {expected}")


def run_pause(
    live_job,
    *,
    resume=False,
    pause_boundary=Decimal("0.5"),
    stop_at=Decimal(60),
    measurements=False,
):
    factory, job_id, lease = live_job
    pause_sequence = 4 if measurements else 2
    last_observed = Decimal("1.5") if measurements else Decimal("0.5")
    with factory.begin() as database:
        if measurements:
            version = database.get(ProcessingJob, job_id).scene_version_id
            shop = database.scalar(
                select(SceneVersionShop).where(SceneVersionShop.scene_version_id == version)
            )
            database.add(
                SceneZone(
                    version_shop_id=shop.id,
                    role=ZoneRole.FRONT,
                    polygon=[[0, 0], [1, 0], [1, 1], [0, 1]],
                )
            )
        claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
    sources, detections, publications, resets = [], [], [], []
    clock = [1_000_000_000 + int(pause_boundary * 10**9)]
    inflight = threading.Event()
    allow_return = threading.Event()

    class Source:
        def __init__(self, *, initial_sequence=0, segment_index=0, **_):
            self.sequence = initial_sequence
            self.segment = segment_index
            self.closed = threading.Event()

        def start(self):
            pass

        def stop(self, **_):
            self.closed.set()

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def read_latest(self, *_):
            if self.closed.is_set():
                raise CaptureError("capture_closed")
            if self.segment > 0 and self.sequence >= pause_sequence + 2:
                return None
            self.sequence += 1
            stamp = (
                Decimal(self.sequence - 1) / 2
                if self.segment == 0
                else Decimal(180) + Decimal(self.sequence - 3) / 2
            )
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                self.sequence,
                self.segment,
                1_000_000_000 + int(stamp * 10**9),
                stamp,
                320,
                180,
            )

    def source_factory(_, **options):
        source = Source(**options)
        sources.append(source)
        return source

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, sequence, *_):
            detections.append(sequence)
            if sequence == pause_sequence:
                wait_state(factory, job_id, "connected")
                with factory.begin() as database:
                    request_live_pause(
                        database, job_id, datetime.now(UTC), machine_id="expo-runner"
                    )
                inflight.set()
                assert allow_return.wait(4)
            elif sequence > pause_sequence:
                with factory.begin() as database:
                    request_live_stop(database, job_id, datetime.now(UTC))
                clock[0] = 181_500_000_000
            if measurements:
                foot = 45 if sequence == 1 or sequence > pause_sequence else 135
                return [Detection(1, (100, foot - 30, 140, foot))]
            return []

        def reset_tracking(self):
            resets.append(True)

    def emit(value):
        publications.append(value)
        if value["type"] == "capture.reconnect-check":
            with factory.begin() as database:
                database.get(LiveAnalysisState, job_id).resume_confirmed_at = datetime.now(UTC)

    runner = threading.Thread(
        target=process_live_analysis_job,
        args=(factory, job_id),
        kwargs={
            "settings": SimpleNamespace(preview_max_fps=30),
            "now": lambda: datetime.now(UTC),
            "source_factory": source_factory,
            "detector_factory": lambda _: Detector(),
            "monotonic_ns": lambda: clock[0],
            "emit": emit,
        },
    )
    runner.start()
    try:
        assert inflight.wait(4)
        assert sources[0].closed.wait(3), "Capture must close while inference is blocked"
        with factory() as database:
            assert database.get(LiveAnalysisState, job_id).capture_status == "pausing"
        allow_return.set()
        paused = wait_state(factory, job_id, "paused")
        assert paused.last_analyzed_sequence == pause_sequence
        assert paused.elapsed_capture_seconds == pause_boundary
        assert paused.resume_confirmed_at is None
        time.sleep(0.25)
        assert detections == list(range(1, pause_sequence + 1)) and len(sources) == 1
        with factory() as database:
            assert database.get(ProcessingJob, job_id).status == JobStatus.PROCESSING
            intervals = list(
                database.scalars(select(LiveInterruption).where(LiveInterruption.job_id == job_id))
            )
            assert len(intervals) == 1 and intervals[0].reason == "operator_pause"
        with factory.begin() as database:
            if resume:
                clock[0] = 181_000_000_000
                request_live_continue(database, job_id, datetime.now(UTC), machine_id="expo-runner")
            else:
                clock[0] = 1_000_000_000 + int(stop_at * 10**9)
                request_live_stop(database, job_id, datetime.now(UTC))
        runner.join(8)
        assert not runner.is_alive()
        with factory() as database:
            job = database.get(ProcessingJob, job_id)
            state = database.get(LiveAnalysisState, job_id)
            assert job.status == JobStatus.COMPLETED
            assert state.capture_status == "ended" and not state.coverage_complete
            intervals = list(
                database.scalars(select(LiveInterruption).where(LiveInterruption.job_id == job_id))
            )
            assert len(intervals) == 1 and intervals[0].end_known
            if resume:
                segments = list(
                    database.scalars(
                        select(LiveCaptureSegment)
                        .where(LiveCaptureSegment.job_id == job_id)
                        .order_by(LiveCaptureSegment.segment_index)
                    )
                )
                assert len(segments) == 2 and segments[1].reason == "operator_resume"
                assert intervals[0].end_seconds >= 180
                assert state.missing_seconds >= Decimal("179.5")
                assert resets and len(sources) == 2
            else:
                assert intervals[0].end_seconds == stop_at
                assert state.observed_seconds == last_observed
                assert state.missing_seconds == stop_at - last_observed
                segment = database.scalar(
                    select(LiveCaptureSegment).where(LiveCaptureSegment.job_id == job_id)
                )
                assert segment.ended_capture_seconds == last_observed
            if measurements:
                assert (
                    len(
                        list(
                            database.scalars(
                                select(LiveCrossing).where(LiveCrossing.job_id == job_id)
                            )
                        )
                    )
                    == 1
                )
                item = next(iter(state.zone_dwell.values()))
                assert item["front_average_seconds"] == 1.5
                assert item["front_sample_count"] == 1
                assert publications[-1]["shops"][0]["total_crossings"] == 1
    finally:
        allow_return.set()
        with factory.begin() as database:
            request_live_stop(database, job_id, datetime.now(UTC))
        runner.join(4)


def test_pause_waits_for_inflight_inference_and_stop_keeps_missing_interval(live_job):
    run_pause(live_job)


def test_pause_resume_keeps_job_and_restarts_tracking(live_job):
    run_pause(live_job, resume=True)


def test_pause_120_stop_180_does_not_extend_observed_segment(live_job):
    run_pause(live_job, pause_boundary=Decimal(120), stop_at=Decimal(180))


def test_pause_resume_preserves_positive_crossings_and_dwell_without_linking_tracks(live_job):
    run_pause(live_job, resume=True, measurements=True, pause_boundary=Decimal("1.5"))


def test_checkpoint_does_not_erase_pause_or_stop(live_job):
    factory, job_id, lease = live_job
    with factory.begin() as database:
        job = claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        database.get(LiveAnalysisState, job_id).capture_status = "connected"
        request_live_pause(database, job_id, datetime.now(UTC), machine_id="expo-runner")
        session_id = job.session_id
    segment_id = uuid.uuid4()
    for revision, expected in [(1, "pausing"), (2, "stopping")]:
        with factory.begin() as database:
            if revision == 2:
                request_live_stop(database, job_id, datetime.now(UTC))
            persist_live_checkpoint(
                database,
                job_id,
                session_id,
                segment_id,
                datetime.now(UTC),
                SimpleNamespace(
                    sequence=revision, segment_index=0, timestamp_seconds=Decimal(revision)
                ),
                revision,
                revision,
                Decimal(revision),
                Decimal(0),
                SimpleNamespace(candidates_seen=0),
                SimpleNamespace(discarded_crossings=0),
                [],
                {},
                datetime.now(UTC),
            )
        with factory() as database:
            state = database.get(LiveAnalysisState, job_id)
            assert state.capture_status == expected and state.pause_requested_at is not None


def test_analysis_gap_checkpoint_does_not_erase_pause(live_job):
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
        persist_live_checkpoint(
            database,
            job_id,
            session_id,
            uuid.uuid4(),
            datetime.now(UTC),
            SimpleNamespace(sequence=1, segment_index=0, timestamp_seconds=Decimal(0)),
            1,
            1,
            Decimal(0),
            Decimal(0),
            SimpleNamespace(candidates_seen=0),
            SimpleNamespace(discarded_crossings=0),
            [],
            {},
            datetime.now(UTC),
        )
    with factory.begin() as database:
        request_live_pause(database, job_id, datetime.now(UTC), machine_id="expo-runner")
        persist_live_checkpoint(
            database,
            job_id,
            session_id,
            uuid.uuid4(),
            datetime.now(UTC),
            SimpleNamespace(
                sequence=2,
                segment_index=1,
                timestamp_seconds=Decimal(2),
                segment_start_seconds=Decimal(2),
                segment_reason="analysis_gap",
            ),
            2,
            2,
            Decimal(0),
            Decimal(2),
            SimpleNamespace(candidates_seen=0),
            SimpleNamespace(discarded_crossings=0),
            [],
            {},
            datetime.now(UTC),
        )
    with factory() as database:
        assert database.get(LiveAnalysisState, job_id).capture_status == "pausing"


def test_worker_restart_during_pause_preserves_unknown_tail(live_job):
    factory, job_id, lease = live_job
    with factory.begin() as database:
        claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "paused"
        state.elapsed_capture_seconds = Decimal(120)
        recover_interrupted_jobs(
            database, datetime.now(UTC), machine_id="expo-runner", worker_id="replacement"
        )
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert state.unknown_tail and not state.coverage_complete
        assert state.elapsed_capture_seconds == 120
        assert database.get(ProcessingJob, job_id).status == JobStatus.FAILED
