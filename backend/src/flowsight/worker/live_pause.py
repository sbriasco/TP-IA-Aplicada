"""Durable pause acknowledgement and idle wait; camera stays closed."""

from sqlalchemy import select, text

from flowsight.capture.contracts import CaptureError
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveInterruption,
    ProcessingJob,
)


def _state(database, job_id, owner_guard):
    database.execute(text("SET LOCAL lock_timeout = '250ms'"))
    database.execute(text("SET LOCAL statement_timeout = '1000ms'"))
    if not owner_guard(database):
        raise CaptureError("worker_owner_lost")
    job = database.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update())
    state = database.scalar(
        select(LiveAnalysisState).where(LiveAnalysisState.job_id == job_id).with_for_update()
    )
    if job is None or state is None or job.status != JobStatus.PROCESSING:
        raise CaptureError("capture_closed")
    return state


def acknowledge_live_pause(factory, job_id, *, boundary_seconds, now, owner_guard):
    with factory.begin() as database:
        state = _state(database, job_id, owner_guard)
        if state.stop_requested_at is not None or state.capture_status == "paused":
            return state.revision
        segment = database.scalar(
            select(LiveCaptureSegment).where(
                LiveCaptureSegment.job_id == job_id,
                LiveCaptureSegment.segment_index == state.current_segment_index,
            )
        )
        if segment is not None:
            segment.ended_capture_seconds = boundary_seconds
            segment.last_sequence = state.last_analyzed_sequence
        database.add(
            LiveInterruption(
                job_id=job_id,
                session_id=state.session_id,
                start_seconds=boundary_seconds,
                reason="operator_pause",
                end_known=False,
            )
        )
        state.capture_status = "paused"
        state.paused_at = now
        state.coverage_complete = False
        state.revision += 1
        return state.revision


def wait_for_live_continue(factory, job_id, *, control, owner_guard):
    while not control.stopping.wait(0.2):
        with factory.begin() as database:
            state = _state(database, job_id, owner_guard)
            if state.stop_requested_at is not None:
                control.stop_capture()
                return False
            if state.resume_requested_at is not None:
                return True
    return False
