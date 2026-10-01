"""Read model for the processed-session history. It does not calculate metrics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import selectinload

from flowsight.core.config import Settings
from flowsight.db.models import JobStatus, ProcessingJob, SceneVersion, VideoSource
from flowsight.db.models import Session as FlowSession
from flowsight.video.storage import Availability, check_availability


@dataclass(frozen=True)
class ProcessedSessionRow:
    session_id: uuid.UUID
    name: str
    video_filename: str | None
    video_availability: Availability | None
    job_id: uuid.UUID
    status: str
    finished_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    scene_version_id: uuid.UUID | None
    version_number: int | None
    result_complete: bool


def list_processed_sessions(
    database_session: DatabaseSession, settings: Settings
) -> list[ProcessedSessionRow]:
    jobs = list(
        database_session.scalars(
            select(ProcessingJob)
            .join(FlowSession, FlowSession.id == ProcessingJob.session_id)
            .where(FlowSession.deleted_at.is_(None))
            .options(selectinload(ProcessingJob.transitions))
            .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
        )
    )
    latest: list[ProcessingJob] = []
    seen: set[uuid.UUID] = set()
    for job in jobs:
        if job.session_id in seen:
            continue
        seen.add(job.session_id)
        latest.append(job)

    rows: list[ProcessedSessionRow] = []
    for job in latest:
        flow_session = database_session.get(FlowSession, job.session_id)
        if flow_session is None:
            continue
        source = database_session.get(VideoSource, job.session_id)
        version = (
            None
            if job.scene_version_id is None
            else database_session.get(SceneVersion, job.scene_version_id)
        )
        failure_code, failure_message = _reason(job)
        availability = None
        filename = None
        if source is not None:
            filename = source.original_filename
            availability = check_availability(
                settings.videos_dir, source.relative_path, source.size_bytes, source.sha256
            )
        rows.append(
            ProcessedSessionRow(
                session_id=flow_session.id,
                name=flow_session.name,
                video_filename=filename,
                video_availability=availability,
                job_id=job.id,
                status=job.status.value,
                finished_at=job.finished_at,
                failure_code=failure_code,
                failure_message=failure_message,
                scene_version_id=job.scene_version_id,
                version_number=None if version is None else version.version_number,
                result_complete=job.result_complete,
            )
        )
    return rows


def _reason(job: ProcessingJob) -> tuple[str | None, str | None]:
    if job.failure_message:
        return job.failure_code, job.failure_message
    if job.status in {JobStatus.FAILED, JobStatus.CANCELLED} and job.transitions:
        latest = max(job.transitions, key=lambda item: (item.occurred_at, item.id.int))
        return latest.reason_code, latest.reason_code
    return job.failure_code, job.failure_message
