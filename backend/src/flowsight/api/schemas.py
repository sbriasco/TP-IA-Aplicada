"""Pydantic contracts for sessions and processing jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flowsight.db.models import JobKind, JobStatus, SourceKind


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    camera_id: str = Field(min_length=1, max_length=120)

    @field_validator("name", "camera_id")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class SessionResponse(SessionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_kind: SourceKind
    created_at: datetime


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: JobKind


class TransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: JobStatus | None
    to_status: JobStatus
    occurred_at: datetime
    reason_code: str | None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    kind: JobKind
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    processing_duration_ms: int | None
    failure_code: str | None
    failure_message: str | None
    transitions: list[TransitionResponse]


class FrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    camera_id: str
    frame_index: int
    video_timestamp_seconds: Decimal


class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    frame_id: uuid.UUID
    camera_id: str
    track_id: int
    kind: str


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    frame_id: uuid.UUID
    observation_id: uuid.UUID | None
    camera_id: str
    video_timestamp_seconds: Decimal
    event_type: str


class JobTraceResponse(BaseModel):
    job: JobResponse
    transitions: list[TransitionResponse]
    frames: list[FrameResponse]
    observations: list[ObservationResponse]
    events: list[EventResponse]
