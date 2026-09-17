"""Persistent entities for the reproducible synthetic FlowSight flow."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceKind(str, enum.Enum):
    SYNTHETIC = "synthetic"


class JobKind(str, enum.Enum):
    SYNTHETIC_BASE_FLOW = "synthetic_base_flow"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_type]


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("id", "camera_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    camera_id: Mapped[str] = mapped_column(String(120))
    source_kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, name="source_kind", values_callable=enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="session")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (UniqueConstraint("id", "session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    kind: Mapped[JobKind] = mapped_column(
        Enum(JobKind, name="job_kind", values_callable=enum_values)
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer)
    session: Mapped[Session] = relationship(back_populates="jobs")
    transitions: Mapped[list[JobStatusTransition]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStatusTransition.occurred_at",
    )


class JobStatusTransition(Base):
    __tablename__ = "job_status_transitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_jobs.id"))
    from_status: Mapped[JobStatus | None] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=enum_values)
    )
    to_status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=enum_values)
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String(120))
    job: Mapped[ProcessingJob] = relationship(back_populates="transitions")


class SyntheticFrame(Base):
    __tablename__ = "synthetic_frames"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "session_id"], ["processing_jobs.id", "processing_jobs.session_id"]
        ),
        ForeignKeyConstraint(["session_id", "camera_id"], ["sessions.id", "sessions.camera_id"]),
        UniqueConstraint("id", "session_id", "job_id", "camera_id"),
        UniqueConstraint("session_id", "job_id", "camera_id", "frame_index"),
        CheckConstraint("frame_index >= 0"),
        CheckConstraint("video_timestamp_seconds >= 0"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    camera_id: Mapped[str] = mapped_column(String(120))
    frame_index: Mapped[int] = mapped_column(Integer)
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["frame_id", "session_id", "job_id", "camera_id"],
            [
                "synthetic_frames.id",
                "synthetic_frames.session_id",
                "synthetic_frames.job_id",
                "synthetic_frames.camera_id",
            ],
        ),
        UniqueConstraint("id", "session_id", "job_id", "frame_id", "camera_id"),
        Index("ix_observation_track_context", "session_id", "camera_id", "track_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    frame_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    camera_id: Mapped[str] = mapped_column(String(120))
    track_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(50))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["frame_id", "session_id", "job_id", "camera_id"],
            [
                "synthetic_frames.id",
                "synthetic_frames.session_id",
                "synthetic_frames.job_id",
                "synthetic_frames.camera_id",
            ],
        ),
        ForeignKeyConstraint(
            ["observation_id", "session_id", "job_id", "frame_id", "camera_id"],
            [
                "observations.id",
                "observations.session_id",
                "observations.job_id",
                "observations.frame_id",
                "observations.camera_id",
            ],
        ),
        CheckConstraint("video_timestamp_seconds >= 0"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    frame_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    observation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    camera_id: Mapped[str] = mapped_column(String(120))
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    event_type: Mapped[str] = mapped_column(String(120))
