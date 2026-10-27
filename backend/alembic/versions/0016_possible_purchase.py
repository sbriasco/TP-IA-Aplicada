"""Possible purchase estimates for a completed file analysis.

The downgrade exists only for pytest fixtures. Environments are never recovered
with a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_possible_purchase"
down_revision: str | None = "0015_visit_patterns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

measure_availability = postgresql.ENUM(
    "available", "unavailable", name="measure_availability", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "possible_purchase_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("minimum_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("visit_count", sa.Integer(), nullable=False),
        sa.Column("availability", measure_availability, nullable=False),
        sa.Column("precision_uncommitted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["processing_jobs.id", "processing_jobs.session_id"],
            name="fk_possible_purchase_reports_job_session",
        ),
        sa.UniqueConstraint("job_id", name="uq_possible_purchase_reports_job_id"),
        sa.CheckConstraint(
            "minimum_seconds = 1", name="ck_possible_purchase_reports_minimum"
        ),
        sa.CheckConstraint(
            "visit_count >= 0", name="ck_possible_purchase_reports_visit_count"
        ),
        sa.CheckConstraint(
            "availability = 'available'",
            name="ck_possible_purchase_reports_available",
        ),
        sa.CheckConstraint(
            "precision_uncommitted IS TRUE",
            name="ck_possible_purchase_reports_precision_uncommitted",
        ),
    )
    op.create_table(
        "possible_purchase_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["possible_purchase_reports.id"],
            name="fk_possible_purchase_members_report",
        ),
        sa.UniqueConstraint(
            "report_id", "track_id", name="uq_possible_purchase_members_report_track"
        ),
    )


def downgrade() -> None:
    op.drop_table("possible_purchase_members")
    op.drop_table("possible_purchase_reports")
