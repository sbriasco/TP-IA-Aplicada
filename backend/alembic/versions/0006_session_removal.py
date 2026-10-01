"""Hide removed sessions while retaining files, results and immutable scenes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_session_removal"
down_revision: str | None = "0005_scene_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "deleted_at")
