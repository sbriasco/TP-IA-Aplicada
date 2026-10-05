"""Atomic claiming and deterministic synthetic job processing."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import sessionmaker

from flowsight.core.config import Settings
from flowsight.db.models import JobKind, JobStatus, ProcessingJob, Session, WorkerMachine
from flowsight.services.jobs import transition_job
from flowsight.services.trace import persist_synthetic_trace
from flowsight.synthetic.trace import generate_synthetic_trace

# Kinds this worker knows how to process. `video_analysis` is the real-video path (US1).
SUPPORTED_JOB_KINDS = (JobKind.SYNTHETIC_BASE_FLOW, JobKind.VIDEO_ANALYSIS, JobKind.LIVE_ANALYSIS)


def claim_next_job(
    database_session: DatabaseSession,
    worker_id: str,
    occurred_at: datetime,
    *,
    machine_id: str | None = None,
    owner_epoch: uuid.UUID | None = None,
) -> ProcessingJob | None:
    if machine_id is not None:
        machine = database_session.scalar(
            select(WorkerMachine).where(WorkerMachine.machine_id == machine_id).with_for_update()
        )
        if owner_epoch is not None and (
            machine is None or machine.owner_epoch != owner_epoch or machine.worker_id != worker_id
        ):
            return None
        if machine is not None and machine.reservation_id is not None:
            if machine.reserved_until > occurred_at:
                return None
        active = database_session.scalar(
            select(ProcessingJob.id)
            .where(
                ProcessingJob.target_machine_id == machine_id,
                ProcessingJob.status == JobStatus.PROCESSING,
            )
            .limit(1)
        )
        if active is not None:
            return None
    scope = (
        or_(
            ProcessingJob.target_machine_id == machine_id, ProcessingJob.target_machine_id.is_(None)
        )
        if machine_id is not None
        else True
    )
    job = database_session.scalar(
        select(ProcessingJob)
        .join(Session, Session.id == ProcessingJob.session_id)
        .where(
            Session.deleted_at.is_(None),
            ProcessingJob.status == JobStatus.PENDING,
            ProcessingJob.kind.in_(SUPPORTED_JOB_KINDS),
            scope,
        )
        .order_by(ProcessingJob.created_at, ProcessingJob.id)
        .with_for_update(skip_locked=True, of=ProcessingJob)
        .limit(1)
    )
    if job is None:
        return None
    job.claimed_by = worker_id
    if machine_id is not None and machine is not None:
        machine.capture_state = "analyzing"
    transition_job(
        database_session,
        job_id=job.id,
        target=JobStatus.PROCESSING,
        occurred_at=occurred_at,
    )
    return job


def recover_interrupted_jobs(
    database_session: DatabaseSession,
    occurred_at: datetime,
    *,
    machine_id: str | None = None,
    worker_id: str | None = None,
) -> int:
    scope = True
    if machine_id is not None:
        scope = ProcessingJob.target_machine_id == machine_id
        if worker_id is not None:
            scope = or_(
                scope,
                (
                    ProcessingJob.target_machine_id.is_(None)
                    & (ProcessingJob.claimed_by == worker_id)
                ),
            )
    elif worker_id is not None:
        scope = ProcessingJob.target_machine_id.is_(None) & (ProcessingJob.claimed_by == worker_id)
    jobs = list(
        database_session.scalars(
            select(ProcessingJob)
            .where(ProcessingJob.status == JobStatus.PROCESSING)
            .where(scope)
            .with_for_update(skip_locked=True)
        )
    )
    for job in jobs:
        if job.kind == JobKind.LIVE_ANALYSIS:
            from flowsight.services.live_results import mark_live_interrupted

            mark_live_interrupted(
                database_session, job, reason="worker_interrupted", occurred_at=occurred_at
            )
        transition_job(
            database_session,
            job_id=job.id,
            target=JobStatus.FAILED,
            occurred_at=occurred_at,
            reason_code="worker_interrupted",
            failure_message="El worker anterior se interrumpió durante el procesamiento.",
        )
    return len(jobs)


def load_synthetic_fixture(
    database_session: DatabaseSession, job: ProcessingJob, fixture_path: Path
) -> dict[str, int]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return load_synthetic_payload(database_session, job, payload)


def load_synthetic_payload(
    database_session: DatabaseSession, job: ProcessingJob, payload: dict
) -> dict[str, int]:
    flow_session = job.session
    trace = generate_synthetic_trace(
        payload,
        job_id=job.id,
        session_id=job.session_id,
        camera_id=flow_session.camera_id,
    )
    return persist_synthetic_trace(database_session, trace)


def process_next_job(
    factory: sessionmaker[DatabaseSession],
    *,
    worker_id: str,
    fixture_path: Path,
    now: Callable[[], datetime],
    settings: Settings | None = None,
    owner_epoch: uuid.UUID | None = None,
    live_emit: Callable[[dict], None] | None = None,
    owner_health: Callable[[], None] | None = None,
) -> uuid.UUID | None:
    with factory.begin() as database_session:
        job = claim_next_job(
            database_session,
            worker_id,
            now(),
            machine_id=(settings.machine_id or "unconfigured") if settings is not None else None,
            owner_epoch=owner_epoch,
        )
        if job is None:
            return None
        job_id = job.id
        kind = job.kind

    if kind is JobKind.VIDEO_ANALYSIS:
        from flowsight.worker.video_analysis import process_video_analysis_job

        process_video_analysis_job(factory, job_id, settings=settings, now=now)
        return job_id

    if kind is JobKind.LIVE_ANALYSIS:
        from flowsight.worker.live_analysis import process_live_analysis_job

        process_live_analysis_job(
            factory,
            job_id,
            settings=settings,
            now=now,
            emit=live_emit,
            owner_epoch=owner_epoch,
            owner_health=owner_health,
        )
        return job_id

    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        for frame in payload["frames"]:
            with factory.begin() as database_session:
                job = database_session.get(ProcessingJob, job_id)
                if job is None:
                    raise LookupError("Trabajo inexistente.")
                load_synthetic_payload(
                    database_session,
                    job,
                    {"schema_version": payload["schema_version"], "frames": [frame]},
                )
        with factory.begin() as database_session:
            transition_job(
                database_session,
                job_id=job_id,
                target=JobStatus.COMPLETED,
                occurred_at=now(),
            )
    except Exception:
        with factory.begin() as database_session:
            job = database_session.get(ProcessingJob, job_id)
            if job is not None and job.status is JobStatus.PROCESSING:
                transition_job(
                    database_session,
                    job_id=job_id,
                    target=JobStatus.FAILED,
                    occurred_at=now(),
                    reason_code="synthetic_processing_error",
                    failure_message="El fixture sintético no pudo procesarse.",
                )
        raise
    return job_id
