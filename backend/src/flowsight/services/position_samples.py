"""Read feet already stored in the trajectory sample. It does not calculate metrics."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.core.config import Settings
from flowsight.db.models import (
    LiveAnalysisState,
    LivePositionSample,
    ProcessingJob,
    Session,
    SourceKind,
)
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


@dataclass(frozen=True)
class LivePositionSampleSet:
    job_id: uuid.UUID
    availability: str
    samples: list[dict]
    sample_count: int
    candidate_count: int
    capacity: int
    source_kind: str = "webcam"
    time_basis: str = "capture"


class JobNotFound(LookupError):
    pass


def list_position_samples(
    database_session: DatabaseSession, settings: Settings, job_id: uuid.UUID
) -> PositionSampleSet | LivePositionSampleSet:
    job = database_session.scalar(
        select(ProcessingJob)
        .join(Session, Session.id == ProcessingJob.session_id)
        .where(ProcessingJob.id == job_id, Session.deleted_at.is_(None))
    )
    if job is None:
        raise JobNotFound
    session = database_session.get(Session, job.session_id)
    if session.source_kind == SourceKind.WEBCAM:
        state = database_session.get(LiveAnalysisState, job_id)
        rows = list(
            database_session.scalars(
                select(LivePositionSample)
                .where(LivePositionSample.job_id == job_id)
                .order_by(LivePositionSample.slot_index)
                .limit(20000)
            )
        )
        count = len(rows)
        selected = rows if count <= 2000 else [rows[index * count // 2000] for index in range(2000)]
        return LivePositionSampleSet(
            job_id=job_id,
            availability="available",
            samples=[
                {
                    "capture_timestamp_seconds": float(row.capture_timestamp_seconds),
                    "foot": (float(row.foot_x), float(row.foot_y)),
                }
                for row in selected
            ],
            sample_count=count,
            candidate_count=0 if state is None else state.sample_candidates_seen,
            capacity=20000 if state is None else state.sample_capacity,
        )
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
