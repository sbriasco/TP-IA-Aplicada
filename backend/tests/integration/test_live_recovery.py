"""Recovery preserves the durable horizon and breaks spatial continuity."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveCrossingBucket,
    LiveInterruption,
    ProcessingJob,
    SceneVersionShop,
)
from flowsight.worker.lifecycle import claim_next_job, recover_interrupted_jobs


def claim(factory, lease):
    with factory.begin() as database:
        return claim_next_job(
            database,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )


def test_database_outage_closes_capture_and_restart_keeps_last_durable_horizon(live_job):
    import threading
    import time

    import numpy as np
    import pytest
    from sqlalchemy.exc import OperationalError

    from flowsight.capture.contracts import CapturedFrame
    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    claim(factory, lease)
    unavailable, closed = threading.Event(), threading.Event()

    class FaultFactory:
        def __call__(self):
            if unavailable.is_set():
                raise OperationalError("SELECT", {}, RuntimeError("injected outage"))
            return factory()

        def begin(self):
            if unavailable.is_set():
                raise OperationalError("SELECT", {}, RuntimeError("injected outage"))
            return factory.begin()

    class Source:
        sequence = 0

        def start(self):
            pass

        def stop(self, timeout_s=2):
            closed.set()

        def read_latest(self, *_):
            self.sequence += 1
            timestamp = Decimal(self.sequence - 1) / 2
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                self.sequence,
                0,
                1_000_000_000 + int(timestamp * 10**9),
                timestamp,
                320,
                180,
            )

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, sequence, *_):
            if sequence == 2:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    with factory() as database:
                        if database.get(LiveAnalysisState, job_id).last_analyzed_sequence == 1:
                            break
                    time.sleep(0.02)
                else:
                    raise AssertionError("First checkpoint was not committed")
                unavailable.set()
                assert closed.wait(8), "DB outage must release capture independently of inference"
            return []

    with pytest.raises(OperationalError):
        process_live_analysis_job(
            FaultFactory(),
            job_id,
            settings=None,
            now=lambda: datetime.now(UTC),
            source_factory=lambda *_args, **_kwargs: Source(),
            detector_factory=lambda _: Detector(),
            monotonic_ns=lambda: 1_500_000_000,
        )
    unavailable.clear()
    with factory.begin() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert state.last_analyzed_sequence == 1 and state.elapsed_capture_seconds == 0
        recover_interrupted_jobs(
            database, datetime.now(UTC), machine_id="expo-runner", worker_id="replacement-worker"
        )
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert database.get(ProcessingJob, job_id).status == JobStatus.FAILED
        assert state.unknown_tail and not state.coverage_complete
        assert state.last_analyzed_sequence == 1 and state.elapsed_capture_seconds == 0


def test_expired_framing_check_closes_capture_and_waits_for_manual_retry(live_job):
    import threading
    from unittest.mock import Mock

    import numpy as np

    from flowsight.capture.contracts import CapturedFrame, CaptureSettings, CaptureStatus
    from flowsight.worker.live_analysis import LiveStopControl
    from flowsight.worker.live_recovery import recover_capture

    factory, job_id, lease = live_job
    job = claim(factory, lease)
    closed = threading.Event()
    attempts, results = [], []
    control = LiveStopControl(factory, job_id, Mock())

    class Source:
        delivered = False

        def start(self):
            pass

        def stop(self, timeout_s=2):
            closed.set()

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def read_latest(self, *_):
            if self.delivered:
                return None
            self.delivered = True
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8), 1, 1, 1_000_000_000, Decimal(0), 320, 180
            )

    def sources(*_args, **_kwargs):
        source = Source()
        attempts.append(source)
        return source

    thread = threading.Thread(
        target=lambda: results.append(
            recover_capture(
                factory,
                job_id,
                job.session_id,
                CaptureSettings(0, "fake", 320, 180),
                source_factory=sources,
                control=control,
                epoch_ns=1_000_000_000,
                sequence=0,
                segment_index=1,
                emit=None,
                owner_guard=lambda _: True,
                delays=(0, 0, 0),
                confirmation_timeout_s=0.05,
            )
        )
    )
    control.start()
    thread.start()
    try:
        assert closed.wait(2)
        with factory() as database:
            state = database.get(LiveAnalysisState, job_id)
            assert state.resume_confirmed_at is None and state.elapsed_capture_seconds == 0
        assert len(attempts) == 1 and thread.is_alive()
        control.stop_capture()
        thread.join(2)
        assert results == [None] and not thread.is_alive()
    finally:
        control.stop_capture()
        control.close()
        thread.join(2)


def test_stop_while_waiting_for_framing_closes_a_known_missing_interval(live_job):
    from types import SimpleNamespace

    import numpy as np

    from flowsight.capture.contracts import CapturedFrame, CaptureError, CaptureStatus
    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    claim(factory, lease)
    sources = []
    clock = [1_000_000_000]

    class Source:
        def __init__(self, resumed):
            self.resumed = resumed
            self.sequence = 2 if resumed else 0
            self.closed = False

        def start(self):
            pass

        def stop(self, timeout_s=2):
            self.closed = True

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def read_latest(self, *_):
            self.sequence += 1
            if not self.resumed and self.sequence > 2:
                raise CaptureError("capture_read_timeout")
            timestamp = Decimal("2.7") if self.resumed else Decimal(self.sequence - 1) / 2
            clock[0] = 1_000_000_000 + int(timestamp * 10**9)
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                self.sequence,
                int(self.resumed),
                clock[0],
                timestamp,
                320,
                180,
            )

    def source_factory(*_args, **_kwargs):
        source = Source(bool(sources))
        sources.append(source)
        return source

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, *_):
            return []

    def emit(message):
        if message["type"] == "capture.reconnect-check":
            with factory.begin() as database:
                database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)

    process_live_analysis_job(
        factory,
        job_id,
        settings=SimpleNamespace(preview_max_fps=5),
        now=lambda: datetime.now(UTC),
        source_factory=source_factory,
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: clock[0],
        emit=emit,
    )
    assert all(source.closed for source in sources)
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert database.get(ProcessingJob, job_id).status == JobStatus.COMPLETED
        assert state.elapsed_capture_seconds == Decimal("2.7") and state.missing_seconds == Decimal(
            "2.2"
        )
        assert not state.coverage_complete and not state.unknown_tail
        interruption = database.query(LiveInterruption).filter_by(job_id=job_id).one()
        assert interruption.end_known and interruption.end_seconds == Decimal("2.7")
        buckets = database.query(LiveCrossingBucket).filter_by(job_id=job_id).all()
        assert buckets and all(
            not bucket.is_open and bucket.coverage_incomplete for bucket in buckets
        )


def test_three_failed_opens_wait_for_manual_retry_and_stop_releases_neutral_source(live_job):
    import threading
    from unittest.mock import Mock

    import numpy as np

    from flowsight.capture.contracts import (
        CapturedFrame,
        CaptureError,
        CaptureSettings,
        CaptureStatus,
    )
    from flowsight.services.live_jobs import request_live_retry
    from flowsight.worker.live_analysis import LiveStopControl
    from flowsight.worker.live_recovery import recover_capture

    factory, job_id, lease = live_job
    job = claim(factory, lease)
    attempts = []
    failed_three, neutral_ready = threading.Event(), threading.Event()
    results, errors = [], []
    control = LiveStopControl(factory, job_id, Mock())

    class Source:
        closed = False
        delivered = False

        def start(self):
            if len(attempts) <= 3:
                if len(attempts) == 3:
                    failed_three.set()
                raise CaptureError("device_unavailable")

        def stop(self, timeout_s=2):
            self.closed = True

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def read_latest(self, *_):
            if self.delivered:
                return None
            self.delivered = True
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8), 1, 1, 1_000_000_000, Decimal(0), 320, 180
            )

    def sources(*_args, **_kwargs):
        source = Source()
        attempts.append(source)
        return source

    def run():
        try:
            results.append(
                recover_capture(
                    factory,
                    job_id,
                    job.session_id,
                    CaptureSettings(0, "fake", 320, 180),
                    source_factory=sources,
                    control=control,
                    epoch_ns=1_000_000_000,
                    sequence=0,
                    segment_index=1,
                    emit=lambda _: neutral_ready.set(),
                    owner_guard=lambda _: True,
                    delays=(0, 0, 0),
                )
            )
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=run)
    control.start()
    thread.start()
    try:
        assert failed_three.wait(2)
        # The fourth open requires the operator's durable retry request.
        assert not neutral_ready.wait(0.3) and len(attempts) == 3
        with factory.begin() as database:
            request_live_retry(database, job_id, datetime.now(UTC), machine_id="expo-runner")
        assert neutral_ready.wait(2) and len(attempts) == 4
        with factory() as database:
            state = database.get(LiveAnalysisState, job_id)
            assert (
                state.capture_status == "awaiting_confirmation"
                and state.elapsed_capture_seconds == 0
            )
        control.stop_capture()
        thread.join(2)
        assert not thread.is_alive() and not errors and results == [None]
        assert all(source.closed for source in attempts)
    finally:
        control.stop_capture()
        control.close()
        thread.join(2)


def test_runner_reconnects_only_after_confirmation_and_retains_previous_crossings(live_job):
    from types import SimpleNamespace

    import numpy as np

    from flowsight.capture.contracts import CapturedFrame, CaptureError, CaptureStatus
    from flowsight.db.models import LiveCrossing
    from flowsight.vision.detector import Detection
    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    claim(factory, lease)
    clock = [1_000_000_000]
    sources = []
    detector_calls = []

    class Source:
        def __init__(self, resumed):
            self.resumed = resumed
            self.frames = iter(
                [(4, "2.7", 144.0), (5, "3.1", 144.0), (6, "3.5", 36.0), (7, "3.9", 36.0)]
                if resumed
                else [(1, "0", 144.0), (2, ".1", 36.0), (3, ".5", 36.0)]
            )
            self.y = 0
            self.closed = False

        def start(self):
            pass

        def stop(self, timeout_s=2):
            self.closed = True

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def read_latest(self, *_):
            value = next(self.frames, None)
            if value is None:
                if not self.resumed:
                    raise CaptureError("capture_read_timeout")
                with factory.begin() as database:
                    database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                return None
            sequence, timestamp, self.y = value
            clock[0] = 1_000_000_000 + int(Decimal(timestamp) * 10**9)
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                sequence,
                int(self.resumed),
                clock[0],
                Decimal(timestamp),
                320,
                180,
            )

    def source_factory(*_args, **_kwargs):
        source = Source(bool(sources))
        sources.append(source)
        return source

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"
        resets = 0

        def reset_tracking(self):
            self.resets += 1

        def detect(self, sequence, *_):
            detector_calls.append(sequence)
            y = sources[-1].y
            return [Detection(1, (100.0, y - 20, 120.0, y))]

    detector = Detector()
    neutral_seen = []

    def emit(message):
        if message["type"] != "capture.reconnect-check":
            return
        assert detector_calls == [1, 2, 3]
        with factory.begin() as database:
            state = database.get(LiveAnalysisState, job_id)
            assert state.capture_status == "awaiting_confirmation"
            assert state.elapsed_capture_seconds == Decimal(".5")
            assert database.query(LiveCrossing).filter_by(job_id=job_id).count() == 1
            state.resume_confirmed_at = datetime.now(UTC)
        neutral_seen.append(message)

    process_live_analysis_job(
        factory,
        job_id,
        settings=SimpleNamespace(preview_max_fps=5),
        now=lambda: datetime.now(UTC),
        source_factory=source_factory,
        detector_factory=lambda _: detector,
        monotonic_ns=lambda: clock[0],
        emit=emit,
    )
    assert neutral_seen and detector_calls == [1, 2, 3, 5, 6, 7]
    assert detector.resets == 1 and all(source.closed for source in sources)
    with factory() as database:
        assert database.get(ProcessingJob, job_id).status == JobStatus.COMPLETED
        state = database.get(LiveAnalysisState, job_id)
        assert state.current_segment_index == 1 and state.elapsed_capture_seconds == Decimal("3.9")
        assert state.missing_seconds == Decimal("2.6") and state.observed_seconds == Decimal("1.3")
        assert database.query(LiveCrossing).filter_by(job_id=job_id).count() == 2
        segments = (
            database.query(LiveCaptureSegment)
            .filter_by(job_id=job_id)
            .order_by(LiveCaptureSegment.segment_index)
            .all()
        )
        assert len(segments) == 2 and segments[1].reason == "reconnected"
        assert segments[0].ended_capture_seconds == Decimal(".5")
        interruption = database.query(LiveInterruption).filter_by(job_id=job_id).one()
        assert interruption.reason == "capture_lost" and interruption.end_known
        assert interruption.start_seconds == Decimal(".5") and interruption.end_seconds == Decimal(
            "3.1"
        )


def test_retry_and_resume_require_current_owner_segment_and_dimensions(live_job):
    import pytest

    import flowsight.services.live_jobs as service
    from flowsight.services.live_jobs import LiveMachineError
    from flowsight.services.live_sessions import LiveChecks

    factory, job_id, lease = live_job
    job = claim(factory, lease)
    checks = LiveChecks()
    with factory.begin() as database:
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "interrupted"
        service.request_live_retry(database, job_id, datetime.now(UTC))
        assert state.retry_requested_at is not None
        state.capture_status = "awaiting_confirmation"
    token = checks.issue(
        session_id=job.session_id,
        machine_id="expo-runner",
        owner_epoch=lease.owner_epoch,
        device_index=0,
        width=320,
        height=180,
        job_id=job_id,
        segment_index=1,
    )
    with (
        pytest.raises(LiveMachineError, match="encuadre_confirmation_required"),
        factory.begin() as database,
    ):
        service.request_live_resume(
            database,
            job_id,
            datetime.now(UTC),
            machine_id="expo-runner",
            checks=checks,
            check_token=token,
            frame_confirmed=False,
        )
    with factory.begin() as database:
        service.request_live_resume(
            database,
            job_id,
            datetime.now(UTC),
            machine_id="expo-runner",
            checks=checks,
            check_token=token,
            frame_confirmed=True,
        )
        assert database.get(LiveAnalysisState, job_id).resume_confirmed_at is not None
    with pytest.raises(LiveMachineError), factory.begin() as database:
        service.request_live_resume(
            database,
            job_id,
            datetime.now(UTC),
            machine_id="expo-runner",
            checks=checks,
            check_token=token,
            frame_confirmed=True,
        )


def test_changed_capture_dimensions_cannot_resume_the_old_scene(live_job):
    import pytest

    import flowsight.services.live_jobs as service
    from flowsight.services.live_jobs import LiveMachineError
    from flowsight.services.live_sessions import LiveChecks

    factory, job_id, lease = live_job
    job = claim(factory, lease)
    with factory.begin() as database:
        database.get(LiveAnalysisState, job_id).capture_status = "awaiting_confirmation"
    checks = LiveChecks()
    token = checks.issue(
        session_id=job.session_id,
        machine_id="expo-runner",
        owner_epoch=lease.owner_epoch,
        device_index=0,
        width=640,
        height=360,
        job_id=job_id,
        segment_index=1,
    )
    with (
        pytest.raises(LiveMachineError, match="aspect_ratio_mismatch"),
        factory.begin() as database,
    ):
        service.request_live_resume(
            database,
            job_id,
            datetime.now(UTC),
            machine_id="expo-runner",
            checks=checks,
            check_token=token,
            frame_confirmed=True,
        )


def test_worker_restart_marks_unknown_tail_without_inventing_elapsed_time(live_job):
    factory, job_id, lease = live_job
    job = claim(factory, lease)
    with factory.begin() as database:
        shop = database.scalar(
            select(SceneVersionShop).where(
                SceneVersionShop.scene_version_id == job.scene_version_id
            )
        )
        state = database.get(LiveAnalysisState, job_id)
        state.elapsed_capture_seconds = Decimal("15.2")
        state.last_capture_sequence = state.last_analyzed_sequence = 100
        state.capture_started_at = datetime.now(UTC)
        state.capture_status = "connected"
        state.revision = 7
        database.add(
            LiveCaptureSegment(
                id=uuid.uuid4(),
                job_id=job_id,
                session_id=job.session_id,
                segment_index=0,
                started_capture_seconds=0,
                first_sequence=1,
                reason="initial",
            )
        )
        database.add(
            LiveCrossingBucket(
                job_id=job_id,
                session_id=job.session_id,
                shop_id=shop.shop_id,
                bucket_index=0,
                start_seconds=0,
                end_seconds=Decimal("15.2"),
                entries=2,
                exits=1,
                observed_seconds=Decimal("15.2"),
                missing_seconds=0,
                pending_count=1,
                is_open=True,
                coverage_incomplete=False,
                unknown_tail=False,
                revision=7,
            )
        )
    with factory.begin() as database:
        assert (
            recover_interrupted_jobs(
                database, datetime.now(UTC), machine_id="other-team", worker_id="other-worker"
            )
            == 0
        )
    with factory.begin() as database:
        assert (
            recover_interrupted_jobs(
                database, datetime.now(UTC), machine_id="expo-runner", worker_id="worker-runner"
            )
            == 1
        )
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert (
            state.capture_status == "ended" and state.unknown_tail and not state.coverage_complete
        )
        assert state.elapsed_capture_seconds == Decimal("15.2")
        assert state.capture_ended_at is None
        assert database.get(ProcessingJob, job_id).status == JobStatus.FAILED
        gap = database.scalar(select(LiveInterruption).where(LiveInterruption.job_id == job_id))
        assert (
            gap.start_seconds == Decimal("15.2") and gap.end_seconds is None and not gap.end_known
        )
        minute = database.get(LiveCrossingBucket, (job_id, shop.shop_id, 0))
        assert minute.entries == 2 and minute.exits == 1
        assert (
            minute.unknown_tail
            and minute.coverage_incomplete
            and not minute.is_open
            and minute.pending_count == 0
        )
    with factory.begin() as database:
        assert (
            recover_interrupted_jobs(
                database, datetime.now(UTC), machine_id="expo-runner", worker_id="worker-runner"
            )
            == 0
        )
