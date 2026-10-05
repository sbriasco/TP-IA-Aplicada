"""Live source/job enum values; commit before schema revision uses them."""

from alembic import op

revision = "0009_live_capture"
down_revision = "0008_scene_configuration_removal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'webcam'")
        op.execute("ALTER TYPE job_kind ADD VALUE IF NOT EXISTS 'live_analysis'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely. Retained like revision0004.
    pass
