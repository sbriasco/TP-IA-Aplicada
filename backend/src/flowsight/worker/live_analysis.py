"""Live capture runner. Frames remain in RAM; checkpoint data belongs to one job."""

from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import cv2
from sqlalchemy import select

from flowsight.capture.contracts import CaptureError, CaptureSettings
from flowsight.capture.fake import FakeCaptureOptions
from flowsight.capture.process import ProcessFrameSource
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveSource,
    ProcessingJob,
    WorkerMachine,
)
from flowsight.preview.live_messages import LiveUpdate
from flowsight.services.jobs import transition_job
from flowsight.services.live_jobs import LiveMachineError
from flowsight.services.live_results import mark_live_interrupted, persist_live_checkpoint
from flowsight.vision.detector import Detection, build_detector
from flowsight.vision.live_buckets import LiveBuckets
from flowsight.vision.live_performance import LivePerformance
from flowsight.vision.live_sampling import LivePositionSampler
from flowsight.vision.live_spatial import LiveSpatialCounter
from flowsight.vision.overlay import render_overlay_jpeg
from flowsight.vision.spatial import normalized_foot
from flowsight.worker.live_checkpoint import LiveCheckpointWriter
from flowsight.worker.video_analysis import _scene_context


class LiveStopControl:
    """Stop capture independently of slow inference; the runner owns durable completion."""

    def __init__(self, factory, job_id, source, *, clock=time.monotonic_ns, health=None) -> None:
        self.factory, self.job_id, self.source = factory, job_id, source
        self.stopping = threading.Event()
        self.closed = threading.Event()
        self.error: str | None = None
        self.clock, self.health = clock, health
        self.capture_stopped_ns = None
        self._database_failure_since = None
        self._source_lock = threading.RLock()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.closed.wait(0.2):
            try:
                if self.health is not None:
                    self.health()
                with self.factory() as database:
                    state = database.get(LiveAnalysisState, self.job_id)
                    stop = (
                        state is None
                        or state.stop_requested_at is not None
                        or state.capture_status == "ended"
                    )
                if stop:
                    self.stop_capture()
                    return
                self._database_failure_since = None
            except (CaptureError, LiveMachineError) as error:
                self.fail(error.code)
                return
            except Exception:
                self._database_failure_since = self._database_failure_since or time.monotonic()
                if time.monotonic() - self._database_failure_since >= 5:
                    self.fail("database_unavailable")
                    return

    def stop_capture(self):
        if not self.stopping.is_set():
            self.capture_stopped_ns = self.clock()
            self.stopping.set()
        with self._source_lock:
            self.source.stop()

    def replace_source(self, source):
        with self._source_lock:
            if self.stopping.is_set():
                source.stop()
                raise CaptureError("capture_closed")
            self.source = source

    def fail(self, code):
        self.error = self.error or code
        self.stop_capture()

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.closed.set()
        if self.thread.ident is not None:
            self.thread.join(2)


def process_live_analysis_job(
    factory,
    job_id: uuid.UUID,
    *,
    settings,
    now: Callable[[], datetime],
    source_factory=None,
    detector_factory=build_detector,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    emit: Callable[[dict], None] | None = None,
    owner_epoch: uuid.UUID | None = None,
    owner_health: Callable[[], None] | None = None,
) -> None:
    with factory.begin() as database:
        state = database.get(LiveAnalysisState, job_id)
        job = database.get(ProcessingJob, job_id)
        if state is None or job is None or job.status != JobStatus.PROCESSING:
            return
        if state.stop_requested_at is not None:
            state.capture_status = "ended"
            state.capture_ended_at = now()
            state.checkpoint_at = now()
            state.revision += 1
            transition_job(database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=now())
            return
        origin = database.get(LiveSource, job.session_id)
        capture_settings = CaptureSettings(
            origin.device_index, origin.capture_backend, origin.width, origin.height
        )
        session_id = job.session_id
        machine_id = job.target_machine_id
        zones, _, shops = _scene_context(database, job.scene_version_id)
        label_mode = origin.label_mode
    source = None
    control = None
    writer = None
    try:
        if source_factory is None:
            first_open = True

            def source_factory(options, **kwargs):
                nonlocal first_open
                if first_open and settings.environment == "test" and options.backend == "fake":
                    kwargs["fake_options"] = FakeCaptureOptions(
                        fail_after=settings.live_fake_fail_after
                    )
                first_open = False
                return ProcessFrameSource(options, **kwargs)

        source = source_factory(capture_settings)
        control = LiveStopControl(factory, job_id, source, clock=monotonic_ns, health=owner_health)
        control.start()
        try:
            source.start()
        except CaptureError:
            if control.stopping.is_set() and control.error is None:
                _complete_unstarted(factory, job_id, machine_id, owner_epoch, now)
                return
            raise
        if control.stopping.is_set():
            if control.error is not None:
                raise CaptureError(control.error)
            _complete_unstarted(factory, job_id, machine_id, owner_epoch, now)
            return
        detector = detector_factory(settings)
        counter = LiveSpatialCounter(shops)
        buckets = LiveBuckets([shop.shop_id for shop in shops])
        sampler = LivePositionSampler()
        performance = LivePerformance()
        segment_id = uuid.uuid4()
        segment_index = 0
        segment_start = Decimal(0)
        segment_reason = "initial"
        horizon, observed, missing = Decimal(0), Decimal(0), Decimal(0)
        sequence, analyzed, revision = 0, 0, 0
        minimum_read_sequence = 0
        resumed_pending = False
        epoch_ns = None
        first_sequence = None
        started_at = None
        pending_facts = []
        dirty_slots = {}
        last_frame = None
        last_publish = None

        def save(snapshot):
            metadata = snapshot.metadata
            _checkpoint(
                factory,
                job_id,
                session_id,
                metadata["segment_id"],
                metadata["started_at"],
                metadata["frame"],
                metadata["analyzed"],
                metadata["revision"],
                metadata["observed"],
                metadata["missing"],
                SimpleNamespace(candidates_seen=metadata["candidates_seen"]),
                SimpleNamespace(discarded_crossings=metadata["discarded_crossings"]),
                snapshot.facts,
                snapshot.slots,
                now(),
                bucket_rows=snapshot.buckets,
                owner_epoch=owner_epoch,
                machine_id=machine_id,
            )

        writer = LiveCheckpointWriter(save, on_failure=control.fail)

        def check_health():
            if owner_health is not None:
                owner_health()
            writer.check_health()

        control.health = check_health
        writer.start()

        def submit(frame, checkpoint_revision, *, ending_capture_seconds=None):
            writer.submit(
                {
                    "segment_id": segment_id,
                    "started_at": started_at,
                    "frame": SimpleNamespace(
                        sequence=frame.sequence,
                        segment_index=frame.segment_index,
                        timestamp_seconds=frame.timestamp_seconds,
                        first_sequence=first_sequence,
                        segment_start_seconds=segment_start,
                        segment_reason=segment_reason,
                        ending_capture_seconds=ending_capture_seconds,
                    ),
                    "analyzed": analyzed,
                    "revision": checkpoint_revision,
                    "observed": observed,
                    "missing": missing,
                    "candidates_seen": sampler.candidates_seen,
                    "discarded_crossings": counter.discarded_crossings,
                },
                facts=pending_facts,
                slots=dirty_slots,
                buckets=buckets.dirty_rows(),
            )
            pending_facts.clear()
            dirty_slots.clear()
            buckets.acknowledge()

        with factory.begin() as database:
            job = database.get(ProcessingJob, job_id)
            job.detector_name, job.detector_version = detector.name, detector.version
            job.tracker_name, job.tracker_version = detector.tracker_name, detector.tracker_version
        while True:
            if control.stopping.is_set():
                break
            try:
                frame = source.read_latest(max(sequence, minimum_read_sequence), 0.05)
            except CaptureError:
                if control.stopping.is_set() and control.error is None:
                    break
                if last_frame is None:
                    raise
                from flowsight.worker.live_recovery import recover_capture

                counter.discontinue(horizon)
                performance.reset()
                sampler.discontinue()
                reset = getattr(detector, "reset_tracking", None)
                if reset is not None:
                    reset()
                buckets.observe(
                    horizon,
                    facts=[],
                    pending=counter.pending_candidates,
                    interval=None,
                    revision=revision + 1,
                )
                revision += 1
                submit(last_frame, revision)
                writer.flush()
                resumed = recover_capture(
                    factory,
                    job_id,
                    session_id,
                    capture_settings,
                    source_factory=source_factory,
                    control=control,
                    epoch_ns=epoch_ns,
                    sequence=sequence,
                    segment_index=segment_index + 1,
                    emit=emit,
                    owner_guard=lambda database: _owns_machine(database, machine_id, owner_epoch),
                )
                if resumed is None:
                    with factory() as database:
                        revision = max(revision, database.get(LiveAnalysisState, job_id).revision)
                    break
                source = resumed.source
                minimum_read_sequence = resumed.minimum_sequence
                revision = resumed.revision
                segment_id = uuid.uuid4()
                segment_index += 1
                segment_reason = "reconnected"
                resumed_pending = True
                continue
            if frame is None:
                time.sleep(0.005)
                continue
            if (frame.width, frame.height) != (
                capture_settings.requested_width,
                capture_settings.requested_height,
            ):
                raise CaptureError("capture_resolution_changed")
            if epoch_ns is None:
                epoch_ns = frame.captured_monotonic_ns
                first_sequence = frame.sequence
                started_at = now() - timedelta(seconds=max(0, monotonic_ns() - epoch_ns) / 10**9)
            frame = replace(
                frame,
                timestamp_seconds=Decimal(frame.captured_monotonic_ns - epoch_ns) / Decimal(10**9),
            )
            gap = frame.timestamp_seconds - horizon
            continuous = not resumed_pending and gap <= 1
            if resumed_pending:
                segment_start = frame.timestamp_seconds
                first_sequence = frame.sequence
            if last_frame is not None:
                if resumed_pending:
                    missing += max(Decimal(0), gap)
                elif gap > 1:
                    # Commit the old segment before changing the snapshot context;
                    # no old fact/sample may acquire the new segment's identity.
                    writer.flush()
                    missing += gap
                    counter.discontinue(horizon)
                    performance.reset()
                    sampler.discontinue()
                    reset = getattr(detector, "reset_tracking", None)
                    if reset is not None:
                        reset()
                    segment_id = uuid.uuid4()
                    segment_index += 1
                    segment_start = frame.timestamp_seconds
                    segment_reason = "analysis_gap"
                    first_sequence = frame.sequence
                else:
                    observed += max(Decimal(0), gap)
            frame = replace(frame, segment_index=segment_index)
            detections = detector.detect(frame.sequence, frame.width, frame.height, frame.image)
            new_facts = counter.observe(frame, detections)
            pending_facts.extend(new_facts)
            buckets.observe(
                frame.timestamp_seconds,
                facts=new_facts,
                pending=counter.pending_candidates,
                interval=None
                if last_frame is None
                else (horizon, frame.timestamp_seconds, continuous),
                revision=revision + 1,
            )
            for detection in detections:
                sampler.observe(
                    segment_index=frame.segment_index,
                    track_id=detection.track_id,
                    sequence=frame.sequence,
                    timestamp_s=frame.timestamp_seconds,
                    foot=normalized_foot(detection, frame.width, frame.height),
                )
            dirty_slots.update((change.slot_index, change) for change in sampler.drain_changes())
            sequence, horizon = frame.sequence, frame.timestamp_seconds
            analyzed += 1
            revision += 1
            last_frame = frame
            resumed_pending = False
            submit(frame, revision)
            publication_ns = monotonic_ns()
            fps = performance.observe(
                frame.sequence, float(frame.timestamp_seconds), publication_ns / 10**9
            )
            if emit is not None and (
                last_publish is None
                or publication_ns - last_publish >= 10**9 / settings.preview_max_fps
            ):
                _emit_update(
                    emit,
                    frame,
                    detections,
                    zones,
                    shops,
                    counter,
                    buckets,
                    job_id,
                    session_id,
                    revision,
                    writer.checkpoint_revision,
                    writer.checkpoint_at,
                    label_mode,
                    publication_ns,
                    analyzed,
                    epoch_ns,
                    fps,
                )
                last_publish = publication_ns
        control.stop_capture()
        if control.error is not None:
            raise CaptureError(control.error)
        counter.discontinue(horizon)
        capture_end = horizon
        if epoch_ns is not None:
            capture_end = max(
                horizon, Decimal(max(0, control.capture_stopped_ns - epoch_ns)) / Decimal(10**9)
            )
        if capture_end > horizon:
            missing += capture_end - horizon
            buckets.observe(
                capture_end,
                facts=[],
                pending=counter.pending_candidates,
                interval=(horizon, capture_end, False),
                revision=revision + 1,
            )
        buckets.finish(revision=revision + 1)
        if last_frame is not None:
            submit(last_frame, revision + 1, ending_capture_seconds=capture_end)
            writer.flush()
        writer.close()
        with factory.begin() as database:
            if not _owns_machine(database, machine_id, owner_epoch):
                return
            state = database.get(LiveAnalysisState, job_id)
            state.capture_status = "ended"
            state.capture_ended_at = now()
            state.checkpoint_at = now()
            if epoch_ns is not None:
                state.elapsed_capture_seconds = max(
                    horizon, Decimal(max(0, control.capture_stopped_ns - epoch_ns)) / Decimal(10**9)
                )
            segment = database.get(LiveCaptureSegment, segment_id)
            if segment is not None:
                segment.ended_capture_seconds = horizon
                segment.last_sequence = sequence
            transition_job(database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=now())
    except Exception as error:
        code = getattr(error, "code", "live_analysis_failed")
        if control is not None:
            control.stop_capture()
        if writer is not None:
            writer.close()
        logging.getLogger("flowsight.capture").info(
            "Live runner failed: %s (%s)", code, type(error).__name__
        )
        if code == "worker_owner_lost":
            # The current owner alone may recover this job; a former worker
            # must neither publish another checkpoint nor transition its status.
            return
        with factory.begin() as database:
            if not _owns_machine(database, machine_id, owner_epoch):
                return
            state = database.get(LiveAnalysisState, job_id)
            job = database.get(ProcessingJob, job_id)
            if state is not None and job.status == JobStatus.PROCESSING:
                reason = (
                    "database_unavailable"
                    if code in {"database_unavailable", "live_buffer_limit"}
                    else "worker_interrupted"
                )
                mark_live_interrupted(database, job, reason=reason, occurred_at=now())
                transition_job(
                    database,
                    job_id=job_id,
                    target=JobStatus.FAILED,
                    occurred_at=now(),
                    reason_code=code,
                    failure_message=(
                        "El análisis en vivo se interrumpió. Se conserva el checkpoint."
                    ),
                )
    finally:
        if writer is not None:
            writer.close()
        if control is not None:
            control.close()
        if source is not None:
            source.stop()


def _checkpoint(factory, *args, **kwargs):
    with factory.begin() as database:
        persist_live_checkpoint(database, *args, **kwargs)


def _owns_machine(database, machine_id, owner_epoch):
    if owner_epoch is None:
        return True
    machine = database.scalar(
        select(WorkerMachine)
        .where(WorkerMachine.machine_id == machine_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return machine is not None and machine.owner_epoch == owner_epoch


def _complete_unstarted(factory, job_id, machine_id, owner_epoch, now):
    with factory.begin() as database:
        if not _owns_machine(database, machine_id, owner_epoch):
            return
        job = database.scalar(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        )
        if job is None or job.status != JobStatus.PROCESSING:
            return
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "ended"
        state.capture_ended_at = now()
        state.checkpoint_at = now()
        state.revision += 1
        transition_job(database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=now())


def _emit_update(
    emit,
    frame,
    detections,
    zones,
    shops,
    counter,
    buckets,
    job_id,
    session_id,
    revision,
    checkpoint_revision,
    checkpoint_at,
    label_mode,
    publication_ns,
    analyzed,
    epoch_ns,
    fps=(None, None),
):
    scale = min(1.0, 960 / frame.width, 540 / frame.height)
    image = (
        frame.image.copy()
        if scale == 1
        else cv2.resize(frame.image, (round(frame.width * scale), round(frame.height * scale)))
    )
    height, width = image.shape[:2]
    scaled_detections = [
        Detection(detection.track_id, tuple(value * scale for value in detection.bbox))
        for detection in detections
    ]
    for shop in shops:
        if shop.line_start is not None and shop.line_end is not None:
            start = (round(shop.line_start[0] * width), round(shop.line_start[1] * height))
            end = (round(shop.line_end[0] * width), round(shop.line_end[1] * height))
            cv2.line(image, start, end, (0, 0, 255), 2)
    jpeg = render_overlay_jpeg(image, scaled_detections, zones, None)
    directions = {shop.shop_id: shop.entry_direction for shop in shops}
    summaries = []
    for counts in counter.counts():
        entries_are_a_to_b = directions[counts.shop_id] == "a_to_b"
        summaries.append(
            {
                "shop_id": str(counts.shop_id),
                "shop_name": counts.shop_name,
                "entry_count": counts.entries,
                "exit_count": counts.exits,
                "a_to_b_count": counts.entries if entries_are_a_to_b else counts.exits,
                "b_to_a_count": counts.exits if entries_are_a_to_b else counts.entries,
                "total_crossings": counts.entries + counts.exits,
                "partial": True,
                "label_mode": label_mode,
                "entry_direction": directions[counts.shop_id],
            }
        )
    message = LiveUpdate.model_validate(
        {
            "type": "live.update",
            "schema_version": "3",
            "source_kind": "webcam",
            "session_id": str(session_id),
            "job_id": str(job_id),
            "revision": revision,
            "capture_status": "connected",
            "segment_index": frame.segment_index,
            "capture_sequence": frame.sequence,
            "capture_timestamp_seconds": float(frame.timestamp_seconds),
            "captured_monotonic_ms": frame.captured_monotonic_ns / 10**6,
            "published_monotonic_ms": publication_ns / 10**6,
            "image_media_type": "image/jpeg",
            "image_base64": base64.b64encode(jpeg).decode(),
            "partial": True,
            "capture_fps": fps[0],
            "analysis_fps": fps[1],
            "capture_to_publish_ms": max(0, (publication_ns - frame.captured_monotonic_ns) / 10**6),
            "shops": summaries,
            "minutes": buckets.snapshot(),
            "coverage_complete": buckets.coverage_complete,
            "checkpoint_revision": checkpoint_revision,
            "checkpoint_at": None if checkpoint_at is None else checkpoint_at.isoformat(),
        }
    )
    emit(message.model_dump(mode="json"))
