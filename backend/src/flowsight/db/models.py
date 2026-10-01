"""Persistent entities for the reproducible synthetic FlowSight flow."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceKind(str, enum.Enum):
    SYNTHETIC = "synthetic"
    VIDEO_FILE = "video_file"


class JobKind(str, enum.Enum):
    SYNTHETIC_BASE_FLOW = "synthetic_base_flow"
    VIDEO_ANALYSIS = "video_analysis"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_type]


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("name_key", name="uq_cameras_name_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("id", "camera_id"),
        UniqueConstraint("id", "registered_camera_id", name="uq_sessions_id_registered_camera_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    # Texto de specs/002: clave de trazabilidad de las FK compuestas de la traza.
    camera_id: Mapped[str] = mapped_column(String(120))
    registered_camera_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cameras.id", name="fk_sessions_registered_camera_id")
    )
    source_kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, name="source_kind", values_callable=enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    camera: Mapped[Camera] = relationship()
    jobs: Mapped[list[ProcessingJob]] = relationship(
        back_populates="session", foreign_keys="ProcessingJob.session_id"
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint("id", "session_id"),
        ForeignKeyConstraint(
            ["session_id", "registered_camera_id"],
            ["sessions.id", "sessions.registered_camera_id"],
            name="fk_processing_jobs_session_camera",
        ),
        ForeignKeyConstraint(
            ["scene_version_id", "registered_camera_id"],
            ["scene_versions.id", "scene_versions.camera_id"],
            name="fk_processing_jobs_scene_version",
        ),
        CheckConstraint(
            "(kind = 'video_analysis') = "
            "(scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)",
            name="ck_processing_jobs_video_analysis_scene",
        ),
        CheckConstraint(
            "result_complete = false OR status = 'completed'",
            name="ck_processing_jobs_result_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    scene_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    registered_camera_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
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
    frames_analyzed: Mapped[int | None] = mapped_column(Integer)
    frames_total: Mapped[int | None] = mapped_column(Integer)
    analyzed_video_timestamp_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    result_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    detector_name: Mapped[str | None] = mapped_column(String(40))
    detector_version: Mapped[str | None] = mapped_column(String(40))
    tracker_name: Mapped[str | None] = mapped_column(String(40))
    tracker_version: Mapped[str | None] = mapped_column(String(80))
    trajectory_relative_path: Mapped[str | None] = mapped_column(String(255))
    session: Mapped[Session] = relationship(back_populates="jobs", foreign_keys=[session_id])
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


class ZoneRole(str, enum.Enum):
    INTERIOR = "interior"
    FRONT = "front"
    SHOWCASE = "showcase"


class EntryDirection(str, enum.Enum):
    A_TO_B = "a_to_b"
    B_TO_A = "b_to_a"


class VideoSource(Base):
    __tablename__ = "video_sources"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_video_sources_size_bytes"),
        CheckConstraint("width > 0 AND height > 0", name="ck_video_sources_size"),
        CheckConstraint("fps > 0", name="ck_video_sources_fps"),
        CheckConstraint("frame_count > 0", name="ck_video_sources_frame_count"),
        CheckConstraint(
            "declared_frame_count IS NULL OR declared_frame_count > 0",
            name="ck_video_sources_declared_frame_count",
        ),
        Index("ix_video_sources_sha256", "sha256"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(CHAR(64))
    origin_machine_id: Mapped[str] = mapped_column(String(40))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[Decimal] = mapped_column(Numeric(9, 4))
    fps_is_estimated: Mapped[bool] = mapped_column(Boolean)
    frame_count: Mapped[int] = mapped_column(Integer)
    # CAP_PROP_FRAME_COUNT del encabezado; solo sirve para avisar de un video
    # incompleto. NULL si no es confiable (MPEG) o si el video es anterior a 0003.
    declared_frame_count: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReferenceFrame(Base):
    __tablename__ = "reference_frames"
    __table_args__ = (
        CheckConstraint("frame_index >= 0", name="ck_reference_frames_frame_index"),
        CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_reference_frames_video_timestamp_seconds"
        ),
        CheckConstraint("width > 0 AND height > 0", name="ck_reference_frames_size"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    frame_index: Mapped[int] = mapped_column(Integer)
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(40))
    # El JPEG pesa: solo se carga cuando se pide la imagen.
    image: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("id", "camera_id", name="uq_shops_id_camera_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SceneVersion(Base):
    """Inmutable: un trigger de la base rechaza UPDATE y DELETE."""

    __tablename__ = "scene_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reference_session_id", "camera_id"],
            ["sessions.id", "sessions.registered_camera_id"],
            name="fk_scene_versions_reference_session",
        ),
        UniqueConstraint(
            "camera_id", "version_number", name="uq_scene_versions_camera_id_version_number"
        ),
        UniqueConstraint("id", "camera_id", name="uq_scene_versions_id_camera_id"),
        CheckConstraint("version_number >= 1", name="ck_scene_versions_version_number"),
        CheckConstraint(
            "frame_width > 0 AND frame_height > 0", name="ck_scene_versions_frame_size"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cameras.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    reference_session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    frame_width: Mapped[int] = mapped_column(Integer)
    frame_height: Mapped[int] = mapped_column(Integer)
    created_by_machine_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SceneVersionShop(Base):
    """Un local tal como aparece en una versión; inmutable."""

    __tablename__ = "scene_version_shops"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scene_version_id", "camera_id"],
            ["scene_versions.id", "scene_versions.camera_id"],
            name="fk_scene_version_shops_scene_version",
        ),
        ForeignKeyConstraint(
            ["shop_id", "camera_id"],
            ["shops.id", "shops.camera_id"],
            name="fk_scene_version_shops_shop",
        ),
        UniqueConstraint(
            "scene_version_id", "name_key", name="uq_scene_version_shops_scene_version_id_name_key"
        ),
        UniqueConstraint(
            "scene_version_id", "shop_id", name="uq_scene_version_shops_scene_version_id_shop_id"
        ),
        CheckConstraint("position >= 0", name="ck_scene_version_shops_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scene_version_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))


class SceneZone(Base):
    __tablename__ = "scene_zones"
    __table_args__ = (
        UniqueConstraint("version_shop_id", "role", name="uq_scene_zones_version_shop_id_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version_shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scene_version_shops.id"))
    role: Mapped[ZoneRole] = mapped_column(
        Enum(ZoneRole, name="zone_role", values_callable=enum_values)
    )
    # Lista de pares [x, y] normalizados a [0, 1].
    polygon: Mapped[list[list[float]]] = mapped_column(JSONB)


class SceneEntryLine(Base):
    __tablename__ = "scene_entry_lines"
    __table_args__ = (
        CheckConstraint(
            "start_x BETWEEN 0 AND 1 AND start_y BETWEEN 0 AND 1 "
            "AND end_x BETWEEN 0 AND 1 AND end_y BETWEEN 0 AND 1",
            name="ck_scene_entry_lines_normalized",
        ),
    )

    version_shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scene_version_shops.id"), primary_key=True
    )
    start_x: Mapped[float] = mapped_column(Double)
    start_y: Mapped[float] = mapped_column(Double)
    end_x: Mapped[float] = mapped_column(Double)
    end_y: Mapped[float] = mapped_column(Double)
    entry_direction: Mapped[EntryDirection] = mapped_column(
        Enum(EntryDirection, name="entry_direction", values_callable=enum_values)
    )


class MeasureCode(str, enum.Enum):
    ENTRIES = "entries"
    EXITS = "exits"
    VISIBLE_OCCUPANCY = "visible_occupancy"


class MeasureAvailability(str, enum.Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CrossingDirection(str, enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"


class CrossingDisposition(str, enum.Enum):
    CONFIRMED = "confirmed"
    OSCILLATION = "oscillation"


class AnalysisMeasure(Base):
    __tablename__ = "analysis_measures"
    __table_args__ = (
        UniqueConstraint(
            "job_id", "shop_id", "code", name="uq_analysis_measures_job_id_shop_id_code"
        ),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_analysis_measures_job_session",
        ),
        CheckConstraint(
            "value IS NULL OR value >= 0", name="ck_analysis_measures_value_non_negative"
        ),
        CheckConstraint(
            "(availability = 'unavailable') = (value IS NULL)",
            name="ck_analysis_measures_unavailable_value",
        ),
        CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_analysis_measures_video_timestamp"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", name="fk_analysis_measures_shop_id")
    )
    code: Mapped[MeasureCode] = mapped_column(
        Enum(MeasureCode, name="measure_code", values_callable=enum_values)
    )
    value: Mapped[int | None] = mapped_column(Integer)
    availability: Mapped[MeasureAvailability] = mapped_column(
        Enum(MeasureAvailability, name="measure_availability", values_callable=enum_values)
    )
    partial: Mapped[bool] = mapped_column(Boolean)
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))


class LineCrossing(Base):
    __tablename__ = "line_crossings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_line_crossings_job_session",
        ),
        Index(
            "ix_line_crossings_session_id_shop_id_track_id",
            "session_id",
            "shop_id",
            "track_id",
        ),
        CheckConstraint("frame_index >= 0", name="ck_line_crossings_frame_index"),
        CheckConstraint("video_timestamp_seconds >= 0", name="ck_line_crossings_video_timestamp"),
        CheckConstraint(
            "foot_x BETWEEN 0 AND 1 AND foot_y BETWEEN 0 AND 1",
            name="ck_line_crossings_foot",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", name="fk_line_crossings_shop_id")
    )
    track_id: Mapped[int] = mapped_column(Integer)
    frame_index: Mapped[int] = mapped_column(Integer)
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    direction: Mapped[CrossingDirection] = mapped_column(
        Enum(CrossingDirection, name="crossing_direction", values_callable=enum_values)
    )
    disposition: Mapped[CrossingDisposition] = mapped_column(
        Enum(CrossingDisposition, name="crossing_disposition", values_callable=enum_values)
    )
    foot_x: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    foot_y: Mapped[Decimal] = mapped_column(Numeric(12, 6))


class SceneEventKind(str, enum.Enum):
    ZONE_ENTER = "zone_enter"
    ZONE_EXIT = "zone_exit"
    STORE_PASS = "store_pass"
    STORE_ENTER = "store_enter"
    STORE_EXIT = "store_exit"
    DWELL = "dwell"


class SceneZoneRole(str, enum.Enum):
    FRONT = "front"
    INTERIOR = "interior"
    WINDOW = "window"


class ShopMetricCode(str, enum.Enum):
    TRAFFIC_TOTAL = "traffic_total"
    STORE_PASS = "store_pass"
    ENTRIES = "entries"
    EXITS = "exits"
    ENTRY_RATE = "entry_rate"
    DWELL_MEAN_SECONDS = "dwell_mean_seconds"
    DWELL_MEDIAN_SECONDS = "dwell_median_seconds"
    VISIBLE_OCCUPANCY = "visible_occupancy"


class ShopMetricLabel(str, enum.Enum):
    VISIT_ESTIMATE = "visit_estimate"
    VISIBLE = "visible"
    OBSERVABLE = "observable"
    NONE = "none"


class SceneEvent(Base):
    __tablename__ = "scene_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_scene_events_job_session",
        ),
        Index(
            "ix_scene_events_session_id_shop_id_video_timestamp_seconds",
            "session_id",
            "shop_id",
            "video_timestamp_seconds",
        ),
        CheckConstraint("frame_index >= 0", name="ck_scene_events_frame_index"),
        CheckConstraint("video_timestamp_seconds >= 0", name="ck_scene_events_video_timestamp"),
        CheckConstraint(
            "(kind = 'dwell') = (duration_seconds IS NOT NULL)",
            name="ck_scene_events_dwell_duration",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_scene_events_duration_non_negative",
        ),
        CheckConstraint(
            "(kind IN ('zone_enter', 'zone_exit', 'dwell')) = (zone_role IS NOT NULL)",
            name="ck_scene_events_zone_role",
        ),
        CheckConstraint(
            "kind <> 'dwell' OR zone_role = 'front'", name="ck_scene_events_dwell_front"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", name="fk_scene_events_shop_id")
    )
    track_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[SceneEventKind] = mapped_column(
        Enum(SceneEventKind, name="scene_event_kind", values_callable=enum_values)
    )
    zone_role: Mapped[SceneZoneRole | None] = mapped_column(
        Enum(SceneZoneRole, name="scene_zone_role", values_callable=enum_values)
    )
    frame_index: Mapped[int] = mapped_column(Integer)
    video_timestamp_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    source_crossing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("line_crossings.id", name="fk_scene_events_source_crossing_id")
    )


class ShopMetric(Base):
    __tablename__ = "shop_metrics"
    __table_args__ = (
        UniqueConstraint("job_id", "shop_id", "code", name="uq_shop_metrics_job_id_shop_id_code"),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_shop_metrics_job_session",
        ),
        CheckConstraint(
            "(availability = 'unavailable') = (value IS NULL)",
            name="ck_shop_metrics_unavailable_value",
        ),
        CheckConstraint("value IS NULL OR value >= 0", name="ck_shop_metrics_value_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", name="fk_shop_metrics_shop_id")
    )
    code: Mapped[ShopMetricCode] = mapped_column(
        Enum(ShopMetricCode, name="shop_metric_code", values_callable=enum_values)
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    availability: Mapped[MeasureAvailability] = mapped_column(
        Enum(MeasureAvailability, name="measure_availability", values_callable=enum_values)
    )
    label: Mapped[ShopMetricLabel] = mapped_column(
        Enum(ShopMetricLabel, name="shop_metric_label", values_callable=enum_values)
    )
    unavailable_reason: Mapped[str | None] = mapped_column(String(40))


class TrafficBucket(Base):
    __tablename__ = "traffic_buckets"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "shop_id",
            "bucket_index",
            name="uq_traffic_buckets_job_id_shop_id_bucket_index",
        ),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_traffic_buckets_job_session",
        ),
        CheckConstraint("bucket_index >= 0", name="ck_traffic_buckets_bucket_index"),
        CheckConstraint("start_seconds >= 0", name="ck_traffic_buckets_start_seconds"),
        CheckConstraint("track_count >= 0", name="ck_traffic_buckets_track_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", name="fk_traffic_buckets_shop_id")
    )
    bucket_index: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    track_count: Mapped[int] = mapped_column(Integer)
