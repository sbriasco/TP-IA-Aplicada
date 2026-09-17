"""Controlled processing-job state transitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from flowsight.db.models import JobStatus, JobStatusTransition, ProcessingJob


class InvalidJobTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.PROCESSING},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}


def transition_job(
    database_session: Session,
    *,
    job_id: uuid.UUID | str,
    target: JobStatus | str,
    occurred_at: datetime,
    reason_code: str | None = None,
    failure_message: str | None = None,
) -> ProcessingJob:
    job = database_session.get(ProcessingJob, uuid.UUID(str(job_id)))
    if job is None:
        raise LookupError("Trabajo inexistente.")

    target_status = JobStatus(target)
    if target_status not in _ALLOWED_TRANSITIONS[job.status]:
        raise InvalidJobTransition(
            f"Transición inválida: {job.status.value} -> {target_status.value}"
        )
    if target_status is JobStatus.FAILED and (not reason_code or not failure_message):
        raise InvalidJobTransition("Un trabajo fallido requiere código y mensaje seguros.")

    previous_status = job.status
    job.status = target_status
    if target_status is JobStatus.PROCESSING:
        job.started_at = occurred_at
    if target_status in {JobStatus.COMPLETED, JobStatus.FAILED}:
        job.finished_at = occurred_at
        if job.started_at is not None:
            elapsed = occurred_at - job.started_at
            job.processing_duration_ms = max(0, round(elapsed.total_seconds() * 1000))
    if target_status is JobStatus.FAILED:
        job.failure_code = reason_code
        job.failure_message = failure_message

    job.transitions.append(
        JobStatusTransition(
            from_status=previous_status,
            to_status=target_status,
            occurred_at=occurred_at,
            reason_code=reason_code,
        )
    )
    database_session.flush()
    return job
