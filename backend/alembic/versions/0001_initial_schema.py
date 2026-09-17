"""Create the initial FlowSight schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_kind = postgresql.ENUM("synthetic", name="source_kind", create_type=False)
job_kind = postgresql.ENUM("synthetic_base_flow", name="job_kind", create_type=False)
job_status = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="job_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    source_kind.create(bind, checkfirst=True)
    job_kind.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("camera_id", sa.String(120), nullable=False),
        sa.Column("source_kind", source_kind, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "camera_id"),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("kind", job_kind, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_by", sa.String(120)),
        sa.Column("failure_code", sa.String(120)),
        sa.Column("failure_message", sa.String(500)),
        sa.Column("processing_duration_ms", sa.Integer()),
        sa.CheckConstraint("processing_duration_ms IS NULL OR processing_duration_ms >= 0"),
        sa.UniqueConstraint("id", "session_id"),
    )
    op.create_table(
        "job_status_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("from_status", job_status),
        sa.Column("to_status", job_status, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason_code", sa.String(120)),
    )
    op.create_table(
        "synthetic_frames",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("camera_id", sa.String(120), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"], ["processing_jobs.id", "processing_jobs.session_id"]
        ),
        sa.ForeignKeyConstraint(["session_id", "camera_id"], ["sessions.id", "sessions.camera_id"]),
        sa.UniqueConstraint("id", "session_id", "job_id", "camera_id"),
        sa.UniqueConstraint("session_id", "job_id", "camera_id", "frame_index"),
        sa.CheckConstraint("frame_index >= 0"),
        sa.CheckConstraint("video_timestamp_seconds >= 0"),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("frame_id", sa.Uuid(), nullable=False),
        sa.Column("camera_id", sa.String(120), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["frame_id", "session_id", "job_id", "camera_id"],
            [
                "synthetic_frames.id",
                "synthetic_frames.session_id",
                "synthetic_frames.job_id",
                "synthetic_frames.camera_id",
            ],
        ),
        sa.UniqueConstraint("id", "session_id", "job_id", "frame_id", "camera_id"),
    )
    op.create_index(
        "ix_observation_track_context", "observations", ["session_id", "camera_id", "track_id"]
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("frame_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid()),
        sa.Column("camera_id", sa.String(120), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.ForeignKeyConstraint(
            ["frame_id", "session_id", "job_id", "camera_id"],
            [
                "synthetic_frames.id",
                "synthetic_frames.session_id",
                "synthetic_frames.job_id",
                "synthetic_frames.camera_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["observation_id", "session_id", "job_id", "frame_id", "camera_id"],
            [
                "observations.id",
                "observations.session_id",
                "observations.job_id",
                "observations.frame_id",
                "observations.camera_id",
            ],
        ),
        sa.CheckConstraint("video_timestamp_seconds >= 0"),
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_index("ix_observation_track_context", table_name="observations")
    op.drop_table("observations")
    op.drop_table("synthetic_frames")
    op.drop_table("job_status_transitions")
    op.drop_table("processing_jobs")
    op.drop_table("sessions")
    bind = op.get_bind()
    job_status.drop(bind, checkfirst=True)
    job_kind.drop(bind, checkfirst=True)
    source_kind.drop(bind, checkfirst=True)
