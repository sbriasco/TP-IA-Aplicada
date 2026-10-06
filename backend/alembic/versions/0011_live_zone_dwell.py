"""Persist observed webcam zone dwell summaries with the checkpoint."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_live_zone_dwell"
down_revision = "0010_live_capture_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "live_analysis_states",
        sa.Column(
            "zone_dwell", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )


def downgrade():
    op.drop_column("live_analysis_states", "zone_dwell")
