"""Reopen capture without running inference until the operator confirms framing."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import cv2
from sqlalchemy import select, text

from flowsight.capture.contracts import CaptureError, FrameSource
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveInterruption,
    ProcessingJob,
)
from flowsight.preview.live_messages import CaptureReconnectCheck
from flowsight.vision.overlay import render_overlay_jpeg


@dataclass(frozen=True)
class ResumedCapture:
    source: FrameSource
    minimum_sequence: int
    revision: int


def recover_capture(
    factory,
    job_id,
    session_id,
    options,
    *,
    source_factory,
    control,
    epoch_ns,
    sequence,
    segment_index,
    emit,
    owner_guard,
    delays=(1, 2, 5),
    confirmation_timeout_s=60,
    clock=time.monotonic,
    interruption_reason="capture_lost",
    interruption_registered=False,
):
    """Three bounded opens per cycle; exhausted/expired cycles wait for manual retry."""
    if (
        len(delays) != 3
        or any(delay < 0 for delay in delays)
        or not 0 < confirmation_timeout_s <= 60
    ):
        raise ValueError("Invalid recovery bounds")

    def locked_state(database):
        database.execute(text("SET LOCAL lock_timeout = '250ms'"))
        database.execute(text("SET LOCAL statement_timeout = '1000ms'"))
        if not owner_guard(database):
            raise CaptureError("worker_owner_lost")
        job = database.scalar(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        )
        state = database.get(LiveAnalysisState, job_id)
        if (
            job is None
            or state is None
            or job.status != JobStatus.PROCESSING
            or state.stop_requested_at
        ):
            control.stop_capture()
            raise CaptureError("capture_closed")
        return state

    def phase(status):
        with factory.begin() as database:
            state = locked_state(database)
            state.capture_status = status
            state.resume_confirmed_at = None
            state.revision += 1
            return state.revision, state.retry_requested_at

    control.source.stop()
    with factory.begin() as database:
        state = locked_state(database)
        state.capture_status = "interrupted"
        state.coverage_complete = False
        state.resume_confirmed_at = None
        state.revision += 1
        retry_seen = state.retry_requested_at
        previous = database.scalar(
            select(LiveCaptureSegment).where(
                LiveCaptureSegment.job_id == job_id,
                LiveCaptureSegment.segment_index == segment_index - 1,
            )
        )
        if previous is not None and not interruption_registered:
            previous.ended_capture_seconds = state.elapsed_capture_seconds
            previous.last_sequence = state.last_analyzed_sequence
        if not interruption_registered:
            database.add(
                LiveInterruption(
                    job_id=job_id,
                    session_id=session_id,
                    start_seconds=state.elapsed_capture_seconds,
                    end_known=False,
                    reason=interruption_reason,
                )
            )

    while not control.stopping.is_set():
        restart = False
        for delay in delays:
            if control.stopping.wait(delay):
                return None
            source = None
            try:
                source = source_factory(
                    options,
                    epoch_ns=epoch_ns,
                    segment_index=segment_index,
                    initial_sequence=sequence,
                )
                control.replace_source(source)
                source.start()
                probe_deadline = clock() + 0.5
                frame = None
                while frame is None and clock() < probe_deadline and not control.stopping.is_set():
                    frame = source.read_latest(sequence, 0.05)
                if control.stopping.is_set():
                    return None
                if frame is None:
                    raise CaptureError("capture_read_timeout")
                revision, retry_seen = phase("awaiting_confirmation")
                scale = min(1.0, 960 / frame.width, 540 / frame.height)
                image = (
                    frame.image
                    if scale == 1
                    else cv2.resize(
                        frame.image, (round(frame.width * scale), round(frame.height * scale))
                    )
                )
                message = CaptureReconnectCheck.model_validate(
                    {
                        "type": "capture.reconnect-check",
                        "schema_version": "3",
                        "source_kind": "webcam",
                        "job_id": job_id,
                        "session_id": session_id,
                        "revision": revision,
                        "capture_status": "awaiting_confirmation",
                        "segment_index": segment_index,
                        "device_index": options.device_index,
                        "width": frame.width,
                        "height": frame.height,
                        "backend": source.status().backend,
                        "image_media_type": "image/jpeg",
                        "image_base64": base64.b64encode(
                            render_overlay_jpeg(image, [], [], None)
                        ).decode(),
                    }
                )
                if emit is not None:
                    emit(message.model_dump(mode="json"))
                # Only the bounded publisher/broker own the encoded preview;
                # the wait loop retains the latest raw frame for continuity checks.
                del message, image
                deadline = clock() + confirmation_timeout_s
                while not control.stopping.is_set():
                    with factory() as database:
                        state = database.get(LiveAnalysisState, job_id)
                        if (
                            state is None
                            or state.stop_requested_at
                            or state.capture_status == "ended"
                        ):
                            control.stop_capture()
                            return None
                        retry_requested = state.retry_requested_at
                        confirmed = state.resume_confirmed_at is not None
                        revision = state.revision
                    if retry_requested != retry_seen:
                        retry_seen = retry_requested
                        restart = True
                        source.stop()
                        break
                    if confirmed:
                        # Skip all raw frames already consumed for the neutral preview.
                        return ResumedCapture(source, frame.sequence, revision)
                    if clock() >= deadline:
                        source.stop()
                        _, retry_seen = phase("interrupted")
                        break
                    latest = source.read_latest(frame.sequence, 0.05)
                    if latest is not None:
                        if (latest.width, latest.height) != (frame.width, frame.height):
                            raise CaptureError("capture_resolution_changed")
                        frame = latest
                    control.stopping.wait(0.15)
                # An operator retry/expired check starts a fresh cycle only on
                # a new retry request; it never confirms framing by itself.
                break
            except CaptureError as error:
                if source is not None:
                    source.stop()
                if error.code in {"worker_owner_lost", "database_unavailable", "live_buffer_limit"}:
                    raise
                if control.stopping.is_set():
                    return None
                phase("interrupted")
        else:
            # All three opens failed. Keep the job active and wait for retry/stop.
            pass
        if restart:
            continue
        while not control.stopping.wait(0.2):
            with factory() as database:
                state = database.get(LiveAnalysisState, job_id)
                if state is None or state.stop_requested_at or state.capture_status == "ended":
                    control.stop_capture()
                    return None
                if state.retry_requested_at != retry_seen:
                    retry_seen = state.retry_requested_at
                    break
    return None
