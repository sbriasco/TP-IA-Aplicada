"""The live worker uses capture time and closes without creating video artifacts."""

from datetime import UTC, datetime
from decimal import Decimal

import numpy as np
import pytest

from flowsight.capture.contracts import CapturedFrame, CaptureStatus
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveCrossing,
    LiveInterruption,
    LivePositionSample,
    ProcessingJob,
)
from flowsight.worker.lifecycle import claim_next_job


def test_analysis_gap_creates_a_new_segment_without_cross_gap_events(live_job):
    from flowsight.vision.detector import Detection
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
    trajectory = [("0", 144.0), (".1", 36.0), (".5", 36.0), ("2.7", 144.0), ("3.1", 144.0)]
    cursor = [0]
    clock = [1_000_000_000]

    class Source:
        def start(self):
            pass

        def stop(self, timeout_s=2):
            pass

        def read_latest(self, *_):
            if cursor[0] == len(trajectory):
                with factory.begin() as database:
                    database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                return None
            timestamp, _ = trajectory[cursor[0]]
            cursor[0] += 1
            clock[0] = 1_000_000_000 + int(Decimal(timestamp) * 10**9)
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                cursor[0],
                0,
                clock[0],
                Decimal(timestamp),
                320,
                180,
            )

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"
        resets = 0

        def reset_tracking(self):
            self.resets += 1

        def detect(self, *_):
            _, y = trajectory[cursor[0] - 1]
            return [Detection(1, (100.0, y - 20, 120.0, y))]

    detector = Detector()
    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: detector,
        monotonic_ns=lambda: clock[0],
    )
    with factory() as database:
        assert database.get(ProcessingJob, job_id).status == JobStatus.COMPLETED
        segments = (
            database.query(LiveCaptureSegment)
            .filter_by(job_id=job_id)
            .order_by(LiveCaptureSegment.segment_index)
            .all()
        )
        assert len(segments) == 2
        assert segments[0].ended_capture_seconds == Decimal(".5")
        assert segments[1].started_capture_seconds == Decimal("2.7")
        assert segments[1].first_sequence == 4 and segments[1].reason == "analysis_gap"
        assert segments[1].ended_capture_seconds == Decimal("3.1")
        events = database.query(LiveCrossing).filter_by(job_id=job_id).all()
        assert len(events) == 1 and events[0].segment_id == segments[0].id
        samples = database.query(LivePositionSample).filter_by(job_id=job_id).all()
        assert {sample.segment_id for sample in samples} == {segment.id for segment in segments}
        interruption = database.query(LiveInterruption).filter_by(job_id=job_id).one()
        assert interruption.start_seconds == Decimal(".5") and interruption.end_seconds == Decimal(
            "2.7"
        )
        state = database.get(LiveAnalysisState, job_id)
        assert state.current_segment_index == 1 and state.missing_seconds == Decimal("2.2")
        assert state.observed_seconds == Decimal(".9") and not state.coverage_complete
    assert detector.resets == 1


def test_stop_during_camera_start_finishes_without_loading_model(live_job):
    import threading

    from flowsight.capture.contracts import CaptureError
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
    stopped = threading.Event()

    class Source:
        def start(self):
            with factory.begin() as database:
                database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
            assert stopped.wait(2)
            raise CaptureError("capture_closed")

        def stop(self, timeout_s=2):
            stopped.set()

    def forbidden(_):
        pytest.fail("A stop during camera startup must not load model weights")

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=forbidden,
    )
    with factory() as database:
        job = database.get(ProcessingJob, job_id)
        state = database.get(LiveAnalysisState, job_id)
        assert job.status == JobStatus.COMPLETED and job.result_complete
        assert state.capture_status == "ended" and state.elapsed_capture_seconds == 0
        assert state.capture_started_at is None and state.coverage_complete


def test_analysis_clock_excludes_capture_before_model_ready(live_job):
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

    class Source:
        sequence = 40

        def start(self):
            pass

        def stop(self, timeout_s=2):
            pass

        def read_latest(self, *_):
            self.sequence += 1
            if self.sequence > 42:
                with factory.begin() as database:
                    database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                return None
            timestamp = Decimal("5") + Decimal(self.sequence - 41) / 2
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                self.sequence,
                0,
                100_000_000_000 + int((timestamp - 5) * 10**9),
                timestamp,
                320,
                180,
            )

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, *_):
            return []

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: 100_500_000_000,
    )
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        segment = database.query(LiveCaptureSegment).filter_by(job_id=job_id).one()
        assert state.elapsed_capture_seconds == Decimal(".5") and state.observed_seconds == Decimal(
            ".5"
        )
        assert segment.first_sequence == 41 and segment.started_capture_seconds == 0


def test_live_claim_requires_correct_machine(live_job):
    factory, job_id, lease = live_job
    with factory.begin() as db:
        assert (
            claim_next_job(db, "other-worker", datetime.now(UTC), machine_id="other-team") is None
        )
        claimed = claim_next_job(
            db,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
        assert claimed is not None and claimed.id == job_id


def test_stop_before_first_frame_does_not_open_camera_or_model(live_job):
    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    with factory.begin() as db:
        db.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
        assert (
            claim_next_job(
                db,
                "worker-runner",
                datetime.now(UTC),
                machine_id="expo-runner",
                owner_epoch=lease.owner_epoch,
            )
            is not None
        )

    def forbidden(*_args, **_kwargs):
        pytest.fail("A pending stop must not open capture or load weights")

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=forbidden,
        detector_factory=forbidden,
    )
    with factory() as db:
        job, state = db.get(ProcessingJob, job_id), db.get(LiveAnalysisState, job_id)
        assert job.status == JobStatus.COMPLETED and job.result_complete
        assert state.elapsed_capture_seconds == 0 and state.capture_started_at is None
        assert state.capture_status == "ended" and state.coverage_complete


def test_capture_timestamps_checkpoint_and_normal_stop(live_job, tmp_path):
    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    with factory.begin() as db:
        assert (
            claim_next_job(
                db,
                "worker-runner",
                datetime.now(UTC),
                machine_id="expo-runner",
                owner_epoch=lease.owner_epoch,
            )
            is not None
        )

    class Source:
        stopped = False
        sequence = 0

        def start(self):
            pass

        def read_latest(self, after_sequence, timeout_s):
            self.sequence += 1
            if self.sequence > 3:
                with factory.begin() as db:
                    db.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                return None
            timestamp = Decimal(self.sequence - 1) / 2
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8),
                self.sequence,
                0,
                1_000_000_000 + int(timestamp * 1_000_000_000),
                timestamp,
                320,
                180,
            )

        def status(self):
            return CaptureStatus("connected", "fake", 320, 180)

        def stop(self, timeout_s=2):
            self.stopped = True

    class Detector:
        name = "fake"
        version = "test"
        tracker_name = "fake"
        tracker_version = "test"

        def detect(self, *_args):
            return []

    source = Source()
    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: source,
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: 2_000_000_000,
    )
    assert source.stopped
    with factory() as db:
        job, state = db.get(ProcessingJob, job_id), db.get(LiveAnalysisState, job_id)
        assert job.status == JobStatus.COMPLETED and job.result_complete
        assert job.frames_total is None and job.frames_analyzed == 3
        assert job.analyzed_video_timestamp_seconds is None
        assert job.trajectory_relative_path is None
        assert state.last_analyzed_sequence == 3 and state.elapsed_capture_seconds == 1
        assert state.observed_seconds == 1 and state.coverage_complete
        assert db.query(LiveCaptureSegment).filter_by(job_id=job_id).count() == 1
    assert list(tmp_path.iterdir()) == []


def test_stop_closes_capture_while_inference_is_waiting(live_job):
    import threading

    from flowsight.worker.live_analysis import process_live_analysis_job

    factory, job_id, lease = live_job
    with factory.begin() as db:
        claim_next_job(
            db,
            "worker-runner",
            datetime.now(UTC),
            machine_id="expo-runner",
            owner_epoch=lease.owner_epoch,
        )
    capture_closed = threading.Event()

    class Source:
        def start(self):
            pass

        def read_latest(self, *_args):
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8), 1, 0, 1_000_000_000, Decimal(0), 320, 180
            )

        def stop(self, timeout_s=2):
            capture_closed.set()

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, *_args):
            with factory.begin() as db:
                db.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
            assert capture_closed.wait(1), "Stop must release capture before inference returns"
            return []

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: 1_000_000_000,
    )
    with factory() as db:
        assert db.get(ProcessingJob, job_id).status == JobStatus.COMPLETED


def test_stop_duration_does_not_include_time_waiting_for_inference(live_job):
    import threading

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
    clock = [1_000_000_000]
    closed = threading.Event()

    class Source:
        def start(self):
            pass

        def read_latest(self, *_):
            return CapturedFrame(
                np.zeros((180, 320, 3), dtype=np.uint8), 1, 0, 1_000_000_000, Decimal(0), 320, 180
            )

        def stop(self, timeout_s=2):
            closed.set()

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, *_):
            clock[0] = 2_000_000_000
            with factory.begin() as database:
                database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
            assert closed.wait(1)
            clock[0] = 100_000_000_000
            return []

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: clock[0],
    )
    with factory() as database:
        assert database.get(LiveAnalysisState, job_id).elapsed_capture_seconds == 1


def test_checkpoint_flushes_while_the_next_inference_is_blocked(live_job):
    import threading
    import time

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
    closed = threading.Event()

    class Source:
        sequence = 0

        def start(self):
            pass

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

        def stop(self, timeout_s=2):
            closed.set()

    class Detector:
        name = tracker_name = "fake"
        version = tracker_version = "test"

        def detect(self, sequence, *_):
            if sequence == 2:
                deadline = time.monotonic() + 2.5
                while time.monotonic() < deadline:
                    with factory() as database:
                        if database.get(LiveAnalysisState, job_id).last_analyzed_sequence == 1:
                            break
                    time.sleep(0.05)
                else:
                    raise AssertionError(
                        "The preceding frame was not saved during blocked inference"
                    )
                with factory.begin() as database:
                    database.get(LiveAnalysisState, job_id).stop_requested_at = datetime.now(UTC)
                assert closed.wait(1)
            return []

    process_live_analysis_job(
        factory,
        job_id,
        settings=None,
        now=lambda: datetime.now(UTC),
        source_factory=lambda *_args, **_kwargs: Source(),
        detector_factory=lambda _: Detector(),
        monotonic_ns=lambda: 2_000_000_000,
    )
    with factory() as database:
        assert database.get(ProcessingJob, job_id).status == JobStatus.COMPLETED
        assert database.get(LiveAnalysisState, job_id).last_analyzed_sequence == 2
