"""Pydantic contracts for cameras, sessions and processing jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AllowInfNan,
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StringConstraints,
    computed_field,
    field_validator,
)

from flowsight.db.models import (
    EntryDirection,
    JobKind,
    JobStatus,
    MeasureAvailability,
    MeasureCode,
    SourceKind,
)
from flowsight.video import probe
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


TrimmedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: TrimmedName


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
    declared_frame_count: int | None
    duration_seconds: float
    registered_at: datetime
    availability: Availability

    @computed_field
    @property
    def appears_incomplete(self) -> bool:
        return probe.appears_incomplete(self.frame_count, self.declared_frame_count)


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


class LiveSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    machine_id: str
    device_index: int
    capture_backend: str
    width: int
    height: int
    reported_fps: float | None
    label_mode: Literal["directions", "access"]
    prepared_at: datetime
    frame_checked_at: datetime | None


class SessionDetail(SessionSummary):
    """Extends the specs/002 session response; keeps every field it returned."""

    camera_id: str
    video: VideoSourceResponse | None
    reference_frame: ReferenceFrameResponse | None
    duplicate_session_ids: list[uuid.UUID]
    live_source: LiveSourceResponse | None = None


class JobCreate(BaseModel):
    """Extends specs/002: `kind` stays required and `scene_version_id` is optional."""

    model_config = ConfigDict(extra="forbid")

    kind: JobKind
    scene_version_id: uuid.UUID | None = None


class TransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: JobStatus | None
    to_status: JobStatus
    occurred_at: datetime
    reason_code: str | None


class LiveStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    capture_status: Literal[
        "starting", "connected", "interrupted", "awaiting_confirmation", "stopping", "ended"
    ]
    capture_started_at: datetime | None
    capture_ended_at: datetime | None
    elapsed_capture_seconds: float
    last_capture_sequence: int
    last_analyzed_sequence: int | None
    current_segment_index: int
    stop_requested_at: datetime | None
    retry_requested_at: datetime | None
    resume_confirmed_at: datetime | None
    checkpoint_at: datetime
    revision: int
    coverage_complete: bool
    unknown_tail: bool
    observed_seconds: float
    missing_seconds: float
    unconfirmed_crossings: int
    sample_candidates_seen: int
    sample_capacity: int


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    kind: JobKind
    scene_version_id: uuid.UUID | None
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    processing_duration_ms: int | None
    result_complete: bool
    frames_analyzed: int | None
    frames_total: int | None
    analyzed_video_timestamp_seconds: Decimal | None
    detector_name: str | None
    detector_version: str | None
    tracker_name: str | None
    tracker_version: str | None
    failure_code: str | None
    failure_message: str | None
    transitions: list[TransitionResponse]
    target_machine_id: str | None = None
    live_state: LiveStateResponse | None = None

    @computed_field
    @property
    def progress_percent(self) -> float | None:
        if not self.frames_total:
            return None
        return min(100, 100 * (self.frames_analyzed or 0) / self.frames_total)


class AnalysisMeasureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    session_id: uuid.UUID
    shop_id: uuid.UUID
    shop_name: str
    code: MeasureCode
    value: int | None
    availability: MeasureAvailability
    partial: bool
    video_timestamp_seconds: Decimal


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


# --- Scene versions (specs/004) ---------------------------------------------------
# Only the shape is validated here. Range and geometry go through
# `flowsight.scene.validation.validate_scene`, so every problem comes back with its
# rule inside a single 422 `invalid_scene_configuration`.

# Upper bound on shops per version: overlap warnings compare every zone pair of
# every shop pair, so the cost grows with the square of this number.
MAX_SHOPS_PER_VERSION = 20

Coordinate = Annotated[float, Strict(), AllowInfNan(False)]
Point = tuple[Coordinate, Coordinate]


class EntryLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: Point
    end: Point
    entry_direction: EntryDirection


class ZonesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    front: list[Point] | None = None
    interior: list[Point] | None = None
    showcase: list[Point] | None = None


class ShopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shop_id: uuid.UUID | None = None
    name: TrimmedName
    zones: ZonesInput
    entry_line: EntryLineInput | None


class SceneVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_session_id: uuid.UUID
    base_version_id: uuid.UUID | None = None
    shops: list[ShopInput] = Field(max_length=MAX_SHOPS_PER_VERSION)


class SceneIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule: str
    element: str
    shop_index: int | None
    shop_name: str | None
    message: str


class SceneVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    camera_id: uuid.UUID
    version_number: int
    reference_session_id: uuid.UUID
    frame_width: int
    frame_height: int
    created_by_machine_id: str | None
    created_at: datetime
    shop_count: int


class ZonesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    front: list[tuple[float, float]] | None = None
    interior: list[tuple[float, float]] | None = None
    showcase: list[tuple[float, float]] | None = None


class EntryLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: tuple[float, float]
    end: tuple[float, float]
    entry_direction: EntryDirection


class SceneVersionShopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: uuid.UUID
    name: str
    zones: ZonesResponse
    entry_line: EntryLineResponse


class SceneVersionResponse(SceneVersionSummary):
    """A saved version as `GET /scene-versions/{id}` returns it, identical every time."""

    shops: list[SceneVersionShopResponse]


class SceneVersionCreatedResponse(SceneVersionResponse):
    """`POST` response: the saved version plus its non-blocking warnings."""

    warnings: list[SceneIssueResponse]


class MetricValueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    code: str
    availability: str
    value: float | None = None
    label: str
    unavailable_reason: str | None = None


class TrafficBucketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    bucket_index: int
    start_seconds: float
    track_count: int


class ShopMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    shop_id: uuid.UUID
    metrics: list[MetricValueResponse]
    flow: list[TrafficBucketResponse]
    peak: TrafficBucketResponse


class ProcessedSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    name: str
    video_filename: str | None
    video_availability: str | None
    job_id: uuid.UUID
    status: str
    finished_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    scene_version_id: uuid.UUID | None
    version_number: int | None
    result_complete: bool
    source_kind: SourceKind
    live_duration_seconds: float | None = None
    coverage_complete: bool | None = None


class PositionSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_timestamp_seconds: float
    foot: tuple[float, float]


class PositionSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: uuid.UUID
    availability: str
    samples: list[PositionSampleResponse]


class LivePositionSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_timestamp_seconds: float
    foot: tuple[float, float]


class LivePositionSamplesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: uuid.UUID
    availability: str
    source_kind: Literal["webcam"] = "webcam"
    time_basis: Literal["capture"] = "capture"
    sample_count: int
    candidate_count: int
    returned_count: int
    capacity: int
    samples: list[LivePositionSampleResponse]


class ChatFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    availability: str
    value: float | None = None
    unavailable_reason: str | None = None
    start_seconds: float | None = None
    track_count: int | None = None
    bucket_index: int | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    session_id: uuid.UUID
    shop_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answered", "refused", "needs_clarification", "unavailable", "error"]
    message: str
    session_id: uuid.UUID | None
    shop_id: uuid.UUID | None
    shop_name: str | None
    scope: Literal["whole_session"] | None
    figures: list[ChatFigure]
    model_calls: int = Field(ge=0, le=2)


class SceneEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    zone_role: str | None = None
    track_id: int
    shop_id: uuid.UUID
    video_timestamp_seconds: float
    duration_seconds: float | None = None
