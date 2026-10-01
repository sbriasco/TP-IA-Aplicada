"""Retire configurations without modifying immutable scene rows."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_scene_configuration_removal"
down_revision: str | None = "0007_camera_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scene_version_removals",
        sa.Column(
            "scene_version_id", sa.Uuid(), sa.ForeignKey("scene_versions.id"), primary_key=True
        ),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("scene_version_removals")
