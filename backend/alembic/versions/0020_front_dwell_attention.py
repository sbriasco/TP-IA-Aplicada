"""Allow front-dwell funnel thresholds without rewriting older reports.

New reports may store a 1 second stop and a 2 second attention estimate.
Reports already stored at 3 and 8 seconds stay valid.
The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_front_dwell_attention"
down_revision: str | None = "0019_tighter_group_thresholds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_shop_funnels_stop_threshold", "shop_funnels", type_="check")
    op.drop_constraint(
        "ck_shop_funnels_attention_threshold", "shop_funnels", type_="check"
    )
    op.create_check_constraint(
        "ck_shop_funnels_stop_threshold",
        "shop_funnels",
        "stop_threshold_seconds IN (3, 1)",
    )
    op.create_check_constraint(
        "ck_shop_funnels_attention_threshold",
        "shop_funnels",
        "attention_threshold_seconds IN (8, 2)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_shop_funnels_stop_threshold", "shop_funnels", type_="check")
    op.drop_constraint(
        "ck_shop_funnels_attention_threshold", "shop_funnels", type_="check"
    )
    op.create_check_constraint(
        "ck_shop_funnels_stop_threshold",
        "shop_funnels",
        "stop_threshold_seconds = 3",
    )
    op.create_check_constraint(
        "ck_shop_funnels_attention_threshold",
        "shop_funnels",
        "attention_threshold_seconds = 8",
    )
