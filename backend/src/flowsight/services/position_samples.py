"""Read feet already stored in the trajectory sample. It does not calculate metrics."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.core.config import Settings
from flowsight.db.models import ProcessingJob, Session
from flowsight.video.storage import video_path


@dataclass(frozen=True)
class PositionSample:
    video_timestamp_seconds: float
    foot: tuple[float, float]


@dataclass(frozen=True)
class PositionSampleSet:
    job_id: uuid.UUID
    availability: str
    samples: list[PositionSample]


class JobNotFound(LookupError):
    pass


def list_position_samples(
    database_session: DatabaseSession, settings: Settings, job_id: uuid.UUID
) -> PositionSampleSet:
    job = database_session.scalar(
        select(ProcessingJob)
        .join(Session, Session.id == ProcessingJob.session_id)
        .where(ProcessingJob.id == job_id, Session.deleted_at.is_(None))
    )
    if job is None:
        raise JobNotFound
    relative = job.trajectory_relative_path
    if relative is None or settings.videos_dir is None:
        return PositionSampleSet(job_id=job.id, availability="unavailable", samples=[])
    try:
        path = video_path(settings.videos_dir, relative)
    except ValueError:
        return PositionSampleSet(job_id=job.id, availability="unavailable", samples=[])
    if not path.is_file():
        return PositionSampleSet(job_id=job.id, availability="unavailable", samples=[])
    return PositionSampleSet(
        job_id=job.id, availability="available", samples=_feet(path.read_text(encoding="utf-8"))
    )


def _feet(payload: str) -> list[PositionSample]:
    samples: list[PositionSample] = []
    for line in payload.splitlines():
        if line.strip() == "":
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("record") != "sample":
            continue
        foot = record.get("foot")
        timestamp = record.get("video_timestamp_seconds")
        if (
            not isinstance(foot, list)
            or len(foot) != 2
            or not isinstance(timestamp, int | float)
            or not all(isinstance(value, int | float) for value in foot)
        ):
            continue
        samples.append(
            PositionSample(
                video_timestamp_seconds=float(timestamp),
                foot=(float(foot[0]), float(foot[1])),
            )
        )
    return samples
