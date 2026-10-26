"""Visit patterns and estimated groups for a completed file analysis.

The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_visit_patterns"
down_revision: str | None = "0014_shop_funnel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

measure_availability = postgresql.ENUM(
    "available", "unavailable", name="measure_availability", create_type=False
)
scene_zone_role = postgresql.ENUM(
    "front", "interior", "window", name="scene_zone_role", create_type=False
)
visit_group_label = postgresql.ENUM(
    "group_estimate", name="visit_group_label", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    visit_group_label.create(bind, checkfirst=True)
    op.create_table(
        "visit_pattern_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("proximity_width_fraction", sa.Numeric(12, 6), nullable=False),
        sa.Column("direction_degrees", sa.Numeric(12, 6), nullable=False),
        sa.Column("minimum_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("motion_epsilon_width_fraction", sa.Numeric(12, 6), nullable=False),
        sa.Column("patterns_availability", measure_availability, nullable=False),
        sa.Column("patterns_unavailable_reason", sa.String(40), nullable=True),
        sa.Column("groups_availability", measure_availability, nullable=False),
        sa.Column("group_count", sa.Integer(), nullable=False),
        sa.Column("precision_uncommitted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_visit_pattern_reports_job_session",
        ),
        sa.UniqueConstraint("job_id", name="uq_visit_pattern_reports_job_id"),
        sa.CheckConstraint(
            "proximity_width_fraction = 0.08",
            name="ck_visit_pattern_reports_proximity",
        ),
        sa.CheckConstraint(
            "direction_degrees = 45", name="ck_visit_pattern_reports_direction"
        ),
        sa.CheckConstraint("minimum_seconds = 2", name="ck_visit_pattern_reports_minimum"),
        sa.CheckConstraint(
            "motion_epsilon_width_fraction = 0.005",
            name="ck_visit_pattern_reports_epsilon",
        ),
        sa.CheckConstraint(
            "precision_uncommitted IS TRUE",
            name="ck_visit_pattern_reports_precision_uncommitted",
        ),
        sa.CheckConstraint("group_count >= 0", name="ck_visit_pattern_reports_group_count"),
        sa.CheckConstraint(
            "(patterns_availability = 'unavailable') = (patterns_unavailable_reason IS NOT NULL)",
            name="ck_visit_pattern_reports_patterns_reason",
        ),
        sa.CheckConstraint(
            "patterns_unavailable_reason IS NULL OR patterns_unavailable_reason = 'no_areas'",
            name="ck_visit_pattern_reports_reason_code",
        ),
        sa.CheckConstraint(
            "groups_availability = 'available'",
            name="ck_visit_pattern_reports_groups_available",
        ),
    )
    op.create_table(
        "visit_area_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("from_shop_id", sa.Uuid(), nullable=False),
        sa.Column("to_shop_id", sa.Uuid(), nullable=False),
        sa.Column("from_zone_role", scene_zone_role, nullable=False),
        sa.Column("to_zone_role", scene_zone_role, nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["visit_pattern_reports.job_id"],
            name="fk_visit_area_transitions_report",
        ),
        sa.ForeignKeyConstraint(
            ["from_shop_id"], ["shops.id"], name="fk_visit_area_transitions_from_shop"
        ),
        sa.ForeignKeyConstraint(
            ["to_shop_id"], ["shops.id"], name="fk_visit_area_transitions_to_shop"
        ),
        sa.UniqueConstraint(
            "job_id",
            "from_shop_id",
            "from_zone_role",
            "to_shop_id",
            "to_zone_role",
            name="uq_visit_area_transitions_pair",
        ),
        sa.CheckConstraint("track_count >= 1", name="ck_visit_area_transitions_track_count"),
    )
    op.create_table(
        "visit_sequences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("areas", postgresql.JSONB(), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["visit_pattern_reports.job_id"],
            name="fk_visit_sequences_report",
        ),
        sa.UniqueConstraint("job_id", "areas", name="uq_visit_sequences_job_areas"),
        sa.CheckConstraint("track_count >= 1", name="ck_visit_sequences_track_count"),
    )
    op.create_table(
        "visit_shop_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("from_shop_id", sa.Uuid(), nullable=False),
        sa.Column("to_shop_id", sa.Uuid(), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["visit_pattern_reports.job_id"],
            name="fk_visit_shop_transitions_report",
        ),
        sa.ForeignKeyConstraint(
            ["from_shop_id"], ["shops.id"], name="fk_visit_shop_transitions_from_shop"
        ),
        sa.ForeignKeyConstraint(
            ["to_shop_id"], ["shops.id"], name="fk_visit_shop_transitions_to_shop"
        ),
        sa.UniqueConstraint(
            "job_id", "from_shop_id", "to_shop_id", name="uq_visit_shop_transitions_pair"
        ),
        sa.CheckConstraint(
            "from_shop_id <> to_shop_id", name="ck_visit_shop_transitions_distinct"
        ),
        sa.CheckConstraint("track_count >= 1", name="ck_visit_shop_transitions_track_count"),
    )
    op.create_table(
        "visit_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("started_video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("ended_video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("label", visit_group_label, nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["visit_pattern_reports.job_id"],
            name="fk_visit_groups_report",
        ),
        sa.UniqueConstraint("job_id", "ordinal", name="uq_visit_groups_job_ordinal"),
        sa.CheckConstraint("ordinal >= 1", name="ck_visit_groups_ordinal"),
        sa.CheckConstraint(
            "ended_video_timestamp_seconds >= started_video_timestamp_seconds",
            name="ck_visit_groups_span",
        ),
    )
    op.create_table(
        "visit_group_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["visit_groups.id"], name="fk_visit_group_members_group"
        ),
        sa.UniqueConstraint(
            "group_id", "track_id", name="uq_visit_group_members_group_track"
        ),
    )


def downgrade() -> None:
    op.drop_table("visit_group_members")
    op.drop_table("visit_groups")
    op.drop_table("visit_shop_transitions")
    op.drop_table("visit_sequences")
    op.drop_table("visit_area_transitions")
    op.drop_table("visit_pattern_reports")
    visit_group_label.drop(op.get_bind(), checkfirst=True)
