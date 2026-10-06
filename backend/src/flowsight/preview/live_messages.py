"""Finite, bounded messages for the loopback producer and public live observer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FiniteSeconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, strict=True)]


class LiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaptureReconnectCheck(LiveModel):
    """A raw framing check carries no inference time, detections or counters."""

    type: Literal["capture.reconnect-check"]
    schema_version: Literal["3"]
    source_kind: Literal["webcam"]
    job_id: uuid.UUID
    session_id: uuid.UUID
    revision: Count
    capture_status: Literal["awaiting_confirmation"]
    segment_index: Count
    device_index: Annotated[int, Field(ge=0, le=32, strict=True)]
    width: Annotated[int, Field(gt=0, le=1920, strict=True)]
    height: Annotated[int, Field(gt=0, le=1080, strict=True)]
    backend: Literal["dshow", "msmf", "fake"]
    image_media_type: Literal["image/jpeg"]
    image_base64: str = Field(min_length=4, max_length=273068, pattern=r"^[A-Za-z0-9+/]+={0,2}$")


class LiveShopSnapshot(LiveModel):
    shop_id: uuid.UUID
    shop_name: str = Field(max_length=120)
    entry_count: Count
    exit_count: Count
    a_to_b_count: Count
    b_to_a_count: Count
    total_crossings: Count
    partial: bool
    label_mode: Literal["directions", "access"]
    entry_direction: Literal["a_to_b", "b_to_a"] | None = None

    @model_validator(mode="after")
    def valid_counts(self):
        if self.total_crossings != self.entry_count + self.exit_count or (
            self.total_crossings != self.a_to_b_count + self.b_to_a_count
        ):
            raise ValueError("Crossing counts disagree")
        return self


class LiveMinute(LiveModel):
    shop_id: uuid.UUID
    bucket_index: Count
    start_seconds: FiniteSeconds
    end_seconds: FiniteSeconds
    entries: Count
    exits: Count
    observed_seconds: Annotated[float, Field(ge=0, le=60, allow_inf_nan=False)]
    missing_seconds: Annotated[float, Field(ge=0, le=60, allow_inf_nan=False)]
    pending_count: Count
    is_open: bool
    coverage_incomplete: bool
    unknown_tail: bool
    revision: Count

    @model_validator(mode="after")
    def valid_interval(self):
        if (
            self.start_seconds != self.bucket_index * 60
            or not (self.start_seconds <= self.end_seconds <= self.start_seconds + 60)
            or self.observed_seconds + self.missing_seconds
            > (self.end_seconds - self.start_seconds + 1e-6)
        ):
            raise ValueError("Invalid minute coverage")
        return self


class LiveZoneDwell(LiveModel):
    interior_average_seconds: FiniteSeconds | None
    front_average_seconds: FiniteSeconds | None
    interior_sample_count: Count
    front_sample_count: Count


class LiveUpdate(LiveModel):
    type: Literal["live.update"]
    schema_version: Literal["3"]
    source_kind: Literal["webcam"]
    session_id: uuid.UUID
    job_id: uuid.UUID
    revision: Count
    capture_status: Literal["connected"]
    segment_index: Count
    capture_sequence: Count
    capture_timestamp_seconds: FiniteSeconds
    captured_monotonic_ms: FiniteSeconds
    published_monotonic_ms: FiniteSeconds
    image_media_type: Literal["image/jpeg"]
    image_base64: str = Field(min_length=4, max_length=273068, pattern=r"^[A-Za-z0-9+/]+={0,2}$")
    partial: bool
    capture_fps: FiniteSeconds | None
    analysis_fps: FiniteSeconds | None
    capture_to_publish_ms: FiniteSeconds
    shops: list[LiveShopSnapshot] = Field(max_length=20)
    minutes: list[LiveMinute] = Field(max_length=1200)
    coverage_complete: bool
    checkpoint_revision: Count
    checkpoint_at: datetime | None
    capture_started_at: datetime | None = None
    zone_dwell: dict[uuid.UUID, LiveZoneDwell] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def bounded_snapshot(self):
        shop_ids = {shop.shop_id for shop in self.shops}
        if len(shop_ids) != len(self.shops):
            raise ValueError("Duplicate shops")
        seen = set()
        counts = {}
        for minute in self.minutes:
            key = (minute.shop_id, minute.bucket_index)
            if minute.shop_id not in shop_ids or key in seen:
                raise ValueError("Invalid minute context")
            seen.add(key)
            counts[minute.shop_id] = counts.get(minute.shop_id, 0) + 1
            if counts[minute.shop_id] > 60:
                raise ValueError("Too many minutes for one shop")
        if self.checkpoint_revision > self.revision:
            raise ValueError("Checkpoint exceeds runtime revision")
        if len(self.model_dump_json().encode()) > 1048576:
            raise ValueError("Message too large")
        return self
