"""Allow a slightly tighter group rule without rewriting older reports.

New reports may store 0.12 of the frame width and 60 degrees. Reports already
stored at 0.08, 0.16, 45 or 90 degrees stay valid. The one-second minimum
does not change.
The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_tighter_group_thresholds"
down_revision: str | None = "0018_lax_group_thresholds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_visit_pattern_reports_proximity", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_direction", "visit_pattern_reports", type_="check"
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_proximity",
        "visit_pattern_reports",
        "proximity_width_fraction IN (0.08, 0.12, 0.16)",
    )
    op.create_check_constraint(
        "ck_visit_pattern_reports_direction",
        "visit_pattern_reports",
        "direction_degrees IN (45, 60, 90)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_visit_pattern_reports_proximity", "visit_pattern_reports", type_="check"
    )
    op.drop_constraint(
        "ck_visit_pattern_reports_direction", "visit_pattern_reports", type_="check"
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
