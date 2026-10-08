"""Machine admission shared by live preparation/start and the worker controller."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from flowsight.db.models import (
    Camera,
    JobKind,
    JobStatus,
    JobStatusTransition,
    LiveAnalysisState,
    LiveSource,
    ProcessingJob,
    SceneVersion,
    SceneVersionRemoval,
    WorkerMachine,
)
from flowsight.scene.geometry import aspect_ratio_matches
from flowsight.services.sessions import get_active_session


class LiveMachineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def reserve_machine(database: Session, machine_id: str, now: datetime) -> uuid.UUID:
    """Caller commits before probing; row lock serializes admission with job creation."""
    machine = database.scalar(
        select(WorkerMachine)
        .where(WorkerMachine.machine_id == machine_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if machine is None or machine.heartbeat_at <= now - timedelta(seconds=5):
        raise LiveMachineError("worker_unavailable")
    if machine.reserved_until is not None and machine.reserved_until > now:
        raise LiveMachineError("machine_busy")
    active = database.scalar(
        select(ProcessingJob.id)
        .where(
            ProcessingJob.target_machine_id == machine_id,
            ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
        )
        .limit(1)
    )
    if active is not None:
        raise LiveMachineError("machine_busy")
    reservation = uuid.uuid4()
    machine.reservation_id = reservation
    machine.reserved_until = now + timedelta(seconds=10)
    machine.capture_state = "probing"
    database.flush()
    return reservation


def release_reservation(database: Session, machine_id: str, reservation: uuid.UUID) -> None:
    machine = database.scalar(
        select(WorkerMachine)
        .where(WorkerMachine.machine_id == machine_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if machine is not None and machine.reservation_id == reservation:
        machine.reservation_id = None
        machine.reserved_until = None
        machine.capture_state = "idle"


def start_live_job(
    database: Session,
    *,
    session_id: uuid.UUID,
    machine_id: str,
    scene_version_id: uuid.UUID,
    checks,
    check_token: str,
    frame_confirmed: bool,
    now: datetime,
) -> ProcessingJob:
    if not frame_confirmed:
        raise LiveMachineError("encuadre_confirmation_required")
    reservation = reserve_machine(database, machine_id, now)
    machine = database.get(WorkerMachine, machine_id)
    session = get_active_session(database, session_id, lock=True)
    source = database.get(LiveSource, session_id)
    if session is None or source is None:
        raise LiveMachineError("not_found")
    if source.machine_id != machine_id:
        raise LiveMachineError("live_not_configured")
    check = checks.require(
        check_token,
        session_id=session_id,
        machine_id=machine_id,
        owner_epoch=machine.owner_epoch,
        device_index=source.device_index,
    )
    if (check.width, check.height) != (source.width, source.height):
        raise LiveMachineError("aspect_ratio_mismatch")
    camera = database.scalar(
        select(Camera)
        .where(Camera.id == session.registered_camera_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if camera is None or camera.deleted_at is not None:
        raise LiveMachineError("camera_removed")
    previous = database.scalar(
        select(ProcessingJob.id).where(
            ProcessingJob.session_id == session_id, ProcessingJob.kind == JobKind.LIVE_ANALYSIS
        )
    )
    if previous is not None:
        raise LiveMachineError("live_already_started")
    version = database.get(SceneVersion, scene_version_id)
    if version is None or version.camera_id != camera.id:
        raise LiveMachineError("scene_version_other_camera")
    if database.get(SceneVersionRemoval, scene_version_id) is not None:
        raise LiveMachineError("scene_version_removed")
    if not aspect_ratio_matches(
        source.width, source.height, version.frame_width, version.frame_height
    ):
        raise LiveMachineError("aspect_ratio_mismatch")
    job = ProcessingJob(
        id=uuid.uuid4(),
        session_id=session.id,
        kind=JobKind.LIVE_ANALYSIS,
        scene_version_id=version.id,
        registered_camera_id=camera.id,
        target_machine_id=machine_id,
        status=JobStatus.PENDING,
        result_complete=False,
    )
    database.add(job)
    job.transitions.append(
        JobStatusTransition(
            from_status=None,
            to_status=JobStatus.PENDING,
            occurred_at=now,
            reason_code="live_requested",
        )
    )
    database.flush()
    database.add(
        LiveAnalysisState(
            job_id=job.id, session_id=session.id, machine_id=machine_id, checkpoint_at=now
        )
    )
    source.frame_checked_at = now
    release_reservation(database, machine_id, reservation)
    database.flush()
    return job


def request_live_stop(database: Session, job_id: uuid.UUID, now: datetime) -> ProcessingJob:
    job = database.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None or get_active_session(database, job.session_id) is None:
        raise LiveMachineError("not_found")
    state = database.get(LiveAnalysisState, job_id)
    if job.kind != JobKind.LIVE_ANALYSIS or state is None:
        raise LiveMachineError("not_found")
    if job.status in (JobStatus.PENDING, JobStatus.PROCESSING) and state.stop_requested_at is None:
        state.stop_requested_at = now
    database.flush()
    return job


def _interrupted_job(database, job_id, machine_id=None):
    job = database.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        job is None
        or job.kind != JobKind.LIVE_ANALYSIS
        or get_active_session(database, job.session_id) is None
    ):
        raise LiveMachineError("not_found")
    state = database.scalar(
        select(LiveAnalysisState)
        .where(LiveAnalysisState.job_id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state is None or (machine_id is not None and state.machine_id != machine_id):
        raise LiveMachineError("live_not_configured")
    if job.status != JobStatus.PROCESSING or state.stop_requested_at is not None:
        raise LiveMachineError("live_stopping")
    if state.capture_status not in {"interrupted", "awaiting_confirmation"}:
        raise LiveMachineError("live_not_interrupted")
    return job, state


def _manual_control_job(database, job_id, machine_id, now):
    # Same lock order as checkpoint/resume: machine, job, state.
    machine = database.scalar(
        select(WorkerMachine)
        .where(WorkerMachine.machine_id == machine_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = database.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        job is None
        or job.kind != JobKind.LIVE_ANALYSIS
        or get_active_session(database, job.session_id) is None
    ):
        raise LiveMachineError("not_found")
    state = database.scalar(
        select(LiveAnalysisState)
        .where(LiveAnalysisState.job_id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state is None or state.machine_id != machine_id:
        raise LiveMachineError("live_wrong_machine")
    if job.status != JobStatus.PROCESSING or state.stop_requested_at is not None:
        raise LiveMachineError("live_stopping")
    if machine is None or machine.heartbeat_at <= now - timedelta(seconds=5):
        raise LiveMachineError("worker_unavailable")
    return job, state


def request_live_pause(database, job_id, now, *, machine_id):
    job, state = _manual_control_job(database, job_id, machine_id, now)
    if state.capture_status in {"pausing", "paused"}:
        return job
    if state.capture_status != "connected":
        raise LiveMachineError("live_not_connected")
    state.pause_requested_at = now
    state.paused_at = state.resume_requested_at = None
    state.capture_status = "pausing"
    database.flush()
    return job


def request_live_continue(database, job_id, now, *, machine_id):
    job, state = _manual_control_job(database, job_id, machine_id, now)
    if state.resume_requested_at is not None:
        return job
    if state.capture_status != "paused" or state.paused_at is None:
        raise LiveMachineError("live_not_paused")
    state.resume_requested_at = now
    database.flush()
    return job


def request_live_retry(database, job_id, now, *, machine_id=None):
    job, state = _interrupted_job(database, job_id, machine_id)
    state.retry_requested_at = now
    state.resume_confirmed_at = None
    state.capture_status = "interrupted"
    database.flush()
    return job


def request_live_resume(database, job_id, now, *, machine_id, checks, check_token, frame_confirmed):
    if frame_confirmed is not True:
        raise LiveMachineError("encuadre_confirmation_required")
    machine = database.scalar(
        select(WorkerMachine)
        .where(WorkerMachine.machine_id == machine_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if machine is None or (now - machine.heartbeat_at).total_seconds() >= 5:
        raise LiveMachineError("worker_unavailable")
    job, state = _interrupted_job(database, job_id, machine_id)
    if state.capture_status != "awaiting_confirmation" or state.resume_confirmed_at is not None:
        raise LiveMachineError("check_expired")
    source = database.get(LiveSource, job.session_id)
    check = checks.require(
        check_token,
        session_id=job.session_id,
        machine_id=machine_id,
        owner_epoch=machine.owner_epoch,
        device_index=source.device_index,
        job_id=job_id,
    )
    if check.segment_index != state.current_segment_index + 1:
        raise LiveMachineError("check_expired")
    if (check.width, check.height) != (source.width, source.height):
        raise LiveMachineError("aspect_ratio_mismatch")
    state.resume_confirmed_at = now
    database.flush()
    return job
