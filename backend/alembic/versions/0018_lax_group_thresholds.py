"""Accept the looser group thresholds without rewriting older reports.

Older reports stay at 0.08, 45 degrees and 2 seconds. New reports may store
0.16, 90 degrees and 1 second. The motion cutoff stays 0.005.
The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_lax_group_thresholds"
down_revision: str | None = "0017_chat_threads_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_visit_pattern_reports_proximity", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_direction", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_minimum", "visit_pattern_reports", type_="check"
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_proximity",
        "visit_pattern_reports",
        "proximity_width_fraction IN (0.08, 0.16)",
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_direction",
        "visit_pattern_reports",
        "direction_degrees IN (45, 90)",
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_minimum",
        "visit_pattern_reports",
        "minimum_seconds IN (1, 2)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_visit_pattern_reports_proximity", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_direction", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_minimum", "visit_pattern_reports", type_="check"
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_proximity",
        "visit_pattern_reports",
        "proximity_width_fraction = 0.08",
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_direction",
        "visit_pattern_reports",
        "direction_degrees = 45",
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_minimum",
        "visit_pattern_reports",
        "minimum_seconds = 2",
    )
