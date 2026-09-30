"""Video analysis progress, official measures and line crossings.

The `downgrade` exists only for the pytest fixtures (`downgrade base` / `upgrade head`);
environments are never recovered with a downgrade. PostgreSQL cannot drop an enum
value safely, so `cancelled` stays in `job_status` after downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_video_analysis"
down_revision: str | None = "0003_video_declared_frame_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

measure_code = postgresql.ENUM(
    "entries", "exits", "visible_occupancy", name="measure_code", create_type=False
)
measure_availability = postgresql.ENUM(
    "available", "unavailable", name="measure_availability", create_type=False
)
crossing_direction = postgresql.ENUM("entry", "exit", name="crossing_direction", create_type=False)
crossing_disposition = postgresql.ENUM(
    "confirmed", "oscillation", name="crossing_disposition", create_type=False
)

_JOB_COLUMNS = (
    "frames_analyzed",
    "frames_total",
    "analyzed_video_timestamp_seconds",
    "result_complete",
    "detector_name",
    "detector_version",
    "tracker_name",
    "tracker_version",
    "trajectory_relative_path",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled'")

    op.add_column("processing_jobs", sa.Column("frames_analyzed", sa.Integer(), nullable=True))
    op.add_column("processing_jobs", sa.Column("frames_total", sa.Integer(), nullable=True))
    op.add_column(
        "processing_jobs",
        sa.Column("analyzed_video_timestamp_seconds", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("result_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("processing_jobs", sa.Column("detector_name", sa.String(40), nullable=True))
    op.add_column("processing_jobs", sa.Column("detector_version", sa.String(40), nullable=True))
    op.add_column("processing_jobs", sa.Column("tracker_name", sa.String(40), nullable=True))
    op.add_column("processing_jobs", sa.Column("tracker_version", sa.String(80), nullable=True))
    op.add_column(
        "processing_jobs", sa.Column("trajectory_relative_path", sa.String(255), nullable=True)
    )
    op.create_check_constraint(
        "ck_processing_jobs_result_complete",
        "processing_jobs",
        "result_complete = false OR status = 'completed'",
    )

    bind = op.get_bind()
    measure_code.create(bind, checkfirst=True)
    measure_availability.create(bind, checkfirst=True)
    crossing_direction.create(bind, checkfirst=True)
    crossing_disposition.create(bind, checkfirst=True)

    op.create_table(
        "analysis_measures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("code", measure_code, nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("availability", measure_availability, nullable=False),
        sa.Column("partial", sa.Boolean(), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_analysis_measures_job_session",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_analysis_measures_shop_id"),
        sa.UniqueConstraint(
            "job_id", "shop_id", "code", name="uq_analysis_measures_job_id_shop_id_code"
        ),
        sa.CheckConstraint(
            "value IS NULL OR value >= 0", name="ck_analysis_measures_value_non_negative"
        ),
        sa.CheckConstraint(
            "(availability = 'unavailable') = (value IS NULL)",
            name="ck_analysis_measures_unavailable_value",
        ),
        sa.CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_analysis_measures_video_timestamp"
        ),
    )
    op.create_table(
        "line_crossings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("direction", crossing_direction, nullable=False),
        sa.Column("disposition", crossing_disposition, nullable=False),
        sa.Column("foot_x", sa.Numeric(12, 6), nullable=False),
        sa.Column("foot_y", sa.Numeric(12, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_line_crossings_job_session",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_line_crossings_shop_id"),
        sa.CheckConstraint("frame_index >= 0", name="ck_line_crossings_frame_index"),
        sa.CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_line_crossings_video_timestamp"
        ),
        sa.CheckConstraint(
            "foot_x BETWEEN 0 AND 1 AND foot_y BETWEEN 0 AND 1",
            name="ck_line_crossings_foot",
        ),
    )
    op.create_index(
        "ix_line_crossings_session_id_shop_id_track_id",
        "line_crossings",
        ["session_id", "shop_id", "track_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_line_crossings_session_id_shop_id_track_id", table_name="line_crossings")
    op.drop_table("line_crossings")
    op.drop_table("analysis_measures")
    bind = op.get_bind()
    crossing_disposition.drop(bind, checkfirst=True)
    crossing_direction.drop(bind, checkfirst=True)
    measure_availability.drop(bind, checkfirst=True)
    measure_code.drop(bind, checkfirst=True)
    op.drop_constraint("ck_processing_jobs_result_complete", "processing_jobs", type_="check")
    for column in reversed(_JOB_COLUMNS):
        op.drop_column("processing_jobs", column)
