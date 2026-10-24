"""Shop funnel stages and the showcase stop event.

The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_shop_funnel"
down_revision: str | None = "0013_scene_display_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

shop_funnel_stage = postgresql.ENUM(
    "observed_pass",
    "exposure",
    "stop",
    "attention",
    "linked_entry",
    name="shop_funnel_stage",
    create_type=False,
)
shop_funnel_rate_code = postgresql.ENUM(
    "observed_pass_to_exposure",
    "exposure_to_stop",
    "stop_to_attention",
    "attention_to_linked_entry",
    name="shop_funnel_rate_code",
    create_type=False,
)
measure_availability = postgresql.ENUM(
    "available", "unavailable", name="measure_availability", create_type=False
)
shop_funnel_label = postgresql.ENUM(
    "none", "attention_estimate", name="shop_funnel_label", create_type=False
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE scene_event_kind ADD VALUE IF NOT EXISTS 'showcase_stop'")

    op.drop_constraint("ck_scene_events_dwell_duration", "scene_events", type_="check")
    op.drop_constraint("ck_scene_events_zone_role", "scene_events", type_="check")
    op.create_check_constraint(
        "ck_scene_events_dwell_duration",
        "scene_events",
        "(kind IN ('dwell', 'showcase_stop')) = (duration_seconds IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_scene_events_zone_role",
        "scene_events",
        "(kind IN ('zone_enter', 'zone_exit', 'dwell', 'showcase_stop')) = (zone_role IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_scene_events_showcase_window",
        "scene_events",
        "kind <> 'showcase_stop' OR zone_role = 'window'",
    )
    op.create_check_constraint(
        "ck_scene_events_showcase_duration",
        "scene_events",
        "kind <> 'showcase_stop' OR duration_seconds >= 3",
    )

    bind = op.get_bind()
    shop_funnel_stage.create(bind, checkfirst=True)
    shop_funnel_rate_code.create(bind, checkfirst=True)
    shop_funnel_label.create(bind, checkfirst=True)

    op.create_table(
        "shop_funnels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("stop_threshold_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("attention_threshold_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("excluded_window_only", sa.Integer(), nullable=False),
        sa.Column("precision_uncommitted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_shop_funnels_job_session",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_shop_funnels_shop_id"
        ),
        sa.UniqueConstraint("job_id", "shop_id", name="uq_shop_funnels_job_id_shop_id"),
        sa.CheckConstraint(
            "stop_threshold_seconds = 3", name="ck_shop_funnels_stop_threshold"
        ),
        sa.CheckConstraint(
            "attention_threshold_seconds = 8", name="ck_shop_funnels_attention_threshold"
        ),
        sa.CheckConstraint(
            "excluded_window_only >= 0", name="ck_shop_funnels_excluded_non_negative"
        ),
        sa.CheckConstraint(
            "precision_uncommitted IS TRUE", name="ck_shop_funnels_precision_uncommitted"
        ),
    )
    op.create_table(
        "shop_funnel_stages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("stage", shop_funnel_stage, nullable=False),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("availability", measure_availability, nullable=False),
        sa.Column("label", shop_funnel_label, nullable=False),
        sa.Column("unavailable_reason", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_shop_funnel_stages_job_session",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "shop_id"],
            ["shop_funnels.job_id", "shop_funnels.shop_id"],
            name="fk_shop_funnel_stages_funnel",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_shop_funnel_stages_shop_id"
        ),
        sa.UniqueConstraint(
            "job_id", "shop_id", "stage", name="uq_shop_funnel_stages_job_shop_stage"
        ),
        sa.CheckConstraint(
            "(availability = 'unavailable') = (count IS NULL)",
            name="ck_shop_funnel_stages_count",
        ),
        sa.CheckConstraint(
            "count IS NULL OR count >= 0", name="ck_shop_funnel_stages_count_non_negative"
        ),
        sa.CheckConstraint(
            "(label = 'attention_estimate') = (stage = 'attention' AND availability = 'available')",
            name="ck_shop_funnel_stages_attention_label",
        ),
    )
    op.create_table(
        "shop_funnel_rates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("code", shop_funnel_rate_code, nullable=False),
        sa.Column("value", sa.Numeric(12, 6), nullable=True),
        sa.Column("availability", measure_availability, nullable=False),
        sa.Column("unavailable_reason", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_shop_funnel_rates_job_session",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "shop_id"],
            ["shop_funnels.job_id", "shop_funnels.shop_id"],
            name="fk_shop_funnel_rates_funnel",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name="fk_shop_funnel_rates_shop_id"
        ),
        sa.UniqueConstraint(
            "job_id", "shop_id", "code", name="uq_shop_funnel_rates_job_shop_code"
        ),
        sa.CheckConstraint(
            "(availability = 'unavailable') = (value IS NULL)",
            name="ck_shop_funnel_rates_value",
        ),
        sa.CheckConstraint(
            "value IS NULL OR value >= 0", name="ck_shop_funnel_rates_value_non_negative"
        ),
    )


def downgrade() -> None:
    op.drop_table("shop_funnel_rates")
    op.drop_table("shop_funnel_stages")
    op.drop_table("shop_funnels")
    bind = op.get_bind()
    shop_funnel_rate_code.drop(bind, checkfirst=True)
    shop_funnel_stage.drop(bind, checkfirst=True)
    shop_funnel_label.drop(bind, checkfirst=True)

    op.drop_constraint("ck_scene_events_showcase_duration", "scene_events", type_="check")
    op.drop_constraint("ck_scene_events_showcase_window", "scene_events", type_="check")
    op.drop_constraint("ck_scene_events_dwell_duration", "scene_events", type_="check")
    op.drop_constraint("ck_scene_events_zone_role", "scene_events", type_="check")
    op.create_check_constraint(
        "ck_scene_events_dwell_duration",
        "scene_events",
        "(kind = 'dwell') = (duration_seconds IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_scene_events_zone_role",
        "scene_events",
        "(kind IN ('zone_enter', 'zone_exit', 'dwell')) = (zone_role IS NOT NULL)",
    )
