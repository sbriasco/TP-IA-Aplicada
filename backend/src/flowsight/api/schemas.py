"""Pydantic contracts for cameras, sessions and processing jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
)

from flowsight.db.models import JobKind, JobStatus, SourceKind
from flowsight.video.storage import Availability


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


CameraName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CameraName


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    source_kind: SourceKind
    camera: CameraResponse
    created_at: datetime


# Measured values are JSON numbers in this contract, so they are floats here
# rather than `Decimal` (which Pydantic serializes as strings).
class VideoSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relative_path: str
    original_filename: str
    size_bytes: int
    sha256: str
    origin_machine_id: str
    width: int
    height: int
    fps: float
    fps_is_estimated: bool
    frame_count: int
    duration_seconds: float
    registered_at: datetime
    availability: Availability


class ReferenceFrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID = Field(exclude=True)
    frame_index: int
    video_timestamp_seconds: float
    width: int
    height: int

    @computed_field
    @property
    def url(self) -> str:
        return f"/sessions/{self.session_id}/reference-frame"


class SessionDetail(SessionSummary):
    """Extends the specs/002 session response; keeps every field it returned."""

    camera_id: str
    video: VideoSourceResponse | None
    reference_frame: ReferenceFrameResponse | None
    duplicate_session_ids: list[uuid.UUID]


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
