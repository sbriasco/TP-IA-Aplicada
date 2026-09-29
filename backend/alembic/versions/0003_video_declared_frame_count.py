"""Frame count declared by the video header, to warn about incomplete videos (T051).

Existing rows keep `NULL`: their header was never read. The `downgrade` exists only
for the pytest fixtures (`downgrade base` / `upgrade head`); environments are never
recovered with a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_video_declared_frame_count"
down_revision: str | None = "0002_scene_configuration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("video_sources", sa.Column("declared_frame_count", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_video_sources_declared_frame_count",
        "video_sources",
        "declared_frame_count IS NULL OR declared_frame_count > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_video_sources_declared_frame_count", "video_sources", type_="check")
    op.drop_column("video_sources", "declared_frame_count")
