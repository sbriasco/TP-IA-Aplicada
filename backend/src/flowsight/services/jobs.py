"""Controlled processing-job state transitions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flowsight.db.models import (
    JobKind,
    JobStatus,
    JobStatusTransition,
    ProcessingJob,
    SceneVersion,
    SourceKind,
    VideoSource,
)
from flowsight.db.models import Session as FlowSession
from flowsight.scene.geometry import NORMALIZED_DECIMALS, aspect_ratio_matches


class InvalidJobTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.PROCESSING, JobStatus.CANCELLED},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
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
        if job.frames_analyzed is None:
            job.frames_analyzed = 0
    if target_status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
        job.finished_at = occurred_at
        if job.started_at is not None:
            elapsed = occurred_at - job.started_at
            job.processing_duration_ms = max(0, round(elapsed.total_seconds() * 1000))
    if target_status is JobStatus.COMPLETED:
        job.result_complete = True
    elif target_status in {JobStatus.FAILED, JobStatus.CANCELLED}:
        job.result_complete = False
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


JobRequestErrorCode = Literal[
    "job_kind_mismatch",
    "scene_version_not_allowed",
    "scene_not_configured",
    "scene_version_required",
    "scene_version_other_camera",
    "aspect_ratio_mismatch",
]

_KIND_FOR_SOURCE = {
    SourceKind.SYNTHETIC: JobKind.SYNTHETIC_BASE_FLOW,
    SourceKind.VIDEO_FILE: JobKind.VIDEO_ANALYSIS,
}


class JobRequestError(ValueError):
    """Job request refused before writing anything; the API translates `code`.

    `extra` carries additional fields for the error body (the aspect ratios of
    `aspect_ratio_mismatch`).
    """

    def __init__(self, code: JobRequestErrorCode, **extra: Any) -> None:
        super().__init__(code)
        self.code = code
        self.extra = extra


def create_job_for_session(
    database_session: Session,
    flow_session: FlowSession,
    kind: JobKind | str,
    scene_version_id: uuid.UUID | None,
) -> ProcessingJob:
    """Create a `pending` job after the checks of FR-025 to FR-028 (specs/004, R12).

    Order: `job_kind_mismatch` → `scene_version_not_allowed` → `scene_not_configured`
    → `scene_version_required` → `scene_version_other_camera` → `aspect_ratio_mismatch`.
    Synthetic jobs keep the specs/002 shape (no `scene_version_id` nor
    `registered_camera_id`). The caller commits.
    """

    job_kind = JobKind(kind)
    if _KIND_FOR_SOURCE[flow_session.source_kind] is not job_kind:
        raise JobRequestError("job_kind_mismatch")

    registered_camera_id: uuid.UUID | None = None
    if job_kind is JobKind.SYNTHETIC_BASE_FLOW:
        if scene_version_id is not None:
            raise JobRequestError("scene_version_not_allowed")
    else:
        camera_id = flow_session.registered_camera_id
        version_count = database_session.scalar(
            select(func.count())
            .select_from(SceneVersion)
            .where(SceneVersion.camera_id == camera_id)
        )
        if not version_count:
            raise JobRequestError("scene_not_configured")
        if scene_version_id is None:
            raise JobRequestError("scene_version_required")
        # An unknown id reads the same as a version of another camera (T028).
        version = database_session.scalar(
            select(SceneVersion).where(
                SceneVersion.id == scene_version_id, SceneVersion.camera_id == camera_id
            )
        )
        if version is None:
            raise JobRequestError("scene_version_other_camera")
        # FR-028 compares the session's video against the version's reference frame.
        video = database_session.get(VideoSource, flow_session.id)
        if video is None:
            raise LookupError("La sesión de video no tiene video registrado.")
        if not aspect_ratio_matches(
            video.width, video.height, version.frame_width, version.frame_height
        ):
            raise JobRequestError(
                "aspect_ratio_mismatch",
                video_aspect_ratio=round(video.width / video.height, NORMALIZED_DECIMALS),
                version_aspect_ratio=round(
                    version.frame_width / version.frame_height, NORMALIZED_DECIMALS
                ),
            )
        registered_camera_id = camera_id

    occurred_at = datetime.now(UTC)
    job = ProcessingJob(
        session_id=flow_session.id,
        kind=job_kind,
        status=JobStatus.PENDING,
        scene_version_id=scene_version_id,
        registered_camera_id=registered_camera_id,
        transitions=[
            JobStatusTransition(
                from_status=None,
                to_status=JobStatus.PENDING,
                occurred_at=occurred_at,
            )
        ],
    )
    database_session.add(job)
    database_session.flush()
    return job
