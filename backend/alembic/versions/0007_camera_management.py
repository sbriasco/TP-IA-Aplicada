"""Retire cameras without removing their sessions or immutable scenes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_camera_management"
down_revision: str | None = "0006_session_removal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "deleted_at")
