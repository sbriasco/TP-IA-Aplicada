"""Scene events, shop metrics and traffic buckets.

The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_scene_metrics"
down_revision: str | None = "0004_video_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

scene_event_kind = postgresql.ENUM(
    "zone_enter",
    "zone_exit",
    "store_pass",
    "store_enter",
    "store_exit",
    "dwell",
    name="scene_event_kind",
    create_type=False,
)
scene_zone_role = postgresql.ENUM(
    "front", "interior", "window", name="scene_zone_role", create_type=False
)
shop_metric_code = postgresql.ENUM(
    "traffic_total",
    "store_pass",
    "entries",
    "exits",
    "entry_rate",
    "dwell_mean_seconds",
    "dwell_median_seconds",
    "visible_occupancy",
    name="shop_metric_code",
    create_type=False,
)
shop_metric_label = postgresql.ENUM(
    "visit_estimate",
    "visible",
    "observable",
    "none",
    name="shop_metric_label",
    create_type=False,
)
measure_availability = postgresql.ENUM(
    "available", "unavailable", name="measure_availability", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    scene_event_kind.create(bind, checkfirst=True)
    scene_zone_role.create(bind, checkfirst=True)
    shop_metric_code.create(bind, checkfirst=True)
    shop_metric_label.create(bind, checkfirst=True)

    op.create_table(
        "scene_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("kind", scene_event_kind, nullable=False),
        sa.Column("zone_role", scene_zone_role, nullable=True),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(12, 6), nullable=True),
        sa.Column("source_crossing_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_scene_events_job_session",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_scene_events_shop_id"),
        sa.ForeignKeyConstraint(
            ["source_crossing_id"],
            ["line_crossings.id"],
            name="fk_scene_events_source_crossing_id",
        ),
        sa.CheckConstraint("frame_index >= 0", name="ck_scene_events_frame_index"),
        sa.CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_scene_events_video_timestamp"
        ),
        sa.CheckConstraint(
            "(kind = 'dwell') = (duration_seconds IS NOT NULL)",
            name="ck_scene_events_dwell_duration",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_scene_events_duration_non_negative",
        ),
        sa.CheckConstraint(
            "(kind IN ('zone_enter', 'zone_exit', 'dwell')) = (zone_role IS NOT NULL)",
            name="ck_scene_events_zone_role",
        ),
        sa.CheckConstraint(
            "kind <> 'dwell' OR zone_role = 'front'", name="ck_scene_events_dwell_front"
        ),
    )
    op.create_index(
        "ix_scene_events_session_id_shop_id_video_timestamp_seconds",
        "scene_events",
        ["session_id", "shop_id", "video_timestamp_seconds"],
    )
    op.create_table(
        "shop_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("code", shop_metric_code, nullable=False),
        sa.Column("value", sa.Numeric(12, 6), nullable=True),
        sa.Column("availability", measure_availability, nullable=False),
        sa.Column("label", shop_metric_label, nullable=False),
        sa.Column("unavailable_reason", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_shop_metrics_job_session",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_shop_metrics_shop_id"),
        sa.UniqueConstraint(
            "job_id", "shop_id", "code", name="uq_shop_metrics_job_id_shop_id_code"
        ),
        sa.CheckConstraint(
            "(availability = 'unavailable') = (value IS NULL)",
            name="ck_shop_metrics_unavailable_value",
        ),
        sa.CheckConstraint(
            "value IS NULL OR value >= 0", name="ck_shop_metrics_value_non_negative"
        ),
    )
    op.create_table(
        "traffic_buckets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_index", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_traffic_buckets_job_session",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_traffic_buckets_shop_id"),
        sa.UniqueConstraint(
            "job_id",
            "shop_id",
            "bucket_index",
            name="uq_traffic_buckets_job_id_shop_id_bucket_index",
        ),
        sa.CheckConstraint("bucket_index >= 0", name="ck_traffic_buckets_bucket_index"),
        sa.CheckConstraint("start_seconds >= 0", name="ck_traffic_buckets_start_seconds"),
        sa.CheckConstraint("track_count >= 0", name="ck_traffic_buckets_track_count"),
    )


def downgrade() -> None:
    op.drop_table("traffic_buckets")
    op.drop_table("shop_metrics")
    op.drop_index(
        "ix_scene_events_session_id_shop_id_video_timestamp_seconds",
        table_name="scene_events",
    )
    op.drop_table("scene_events")
    bind = op.get_bind()
    shop_metric_label.drop(bind, checkfirst=True)
    shop_metric_code.drop(bind, checkfirst=True)
    scene_zone_role.drop(bind, checkfirst=True)
    scene_event_kind.drop(bind, checkfirst=True)
