"""Atomic claiming and deterministic synthetic job processing."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import sessionmaker

from flowsight.db.models import JobStatus, ProcessingJob
from flowsight.services.jobs import transition_job
from flowsight.services.trace import persist_synthetic_trace
from flowsight.synthetic.trace import generate_synthetic_trace


def claim_next_job(
    database_session: DatabaseSession, worker_id: str, occurred_at: datetime
) -> ProcessingJob | None:
    job = database_session.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.status == JobStatus.PENDING)
        .order_by(ProcessingJob.created_at, ProcessingJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.claimed_by = worker_id
    transition_job(
        database_session,
        job_id=job.id,
        target=JobStatus.PROCESSING,
        occurred_at=occurred_at,
    )
    return job


def recover_interrupted_jobs(database_session: DatabaseSession, occurred_at: datetime) -> int:
    jobs = list(
        database_session.scalars(
            select(ProcessingJob)
            .where(ProcessingJob.status == JobStatus.PROCESSING)
            .with_for_update(skip_locked=True)
        )
    )
    for job in jobs:
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
) -> uuid.UUID | None:
    with factory.begin() as database_session:
        job = claim_next_job(database_session, worker_id, now())
        if job is None:
            return None
        job_id = job.id

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
