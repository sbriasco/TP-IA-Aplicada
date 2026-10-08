"""Store the configuration name with the immutable scene version."""

import sqlalchemy as sa

from alembic import op

revision = "0013_scene_display_name"
down_revision = "0012_live_manual_pause"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("scene_versions", sa.Column("display_name", sa.String(120)))
    op.create_check_constraint(
        "ck_scene_versions_display_name",
        "scene_versions",
        "display_name IS NULL OR char_length(btrim(display_name)) BETWEEN 1 AND 120",
    )


def downgrade():
    op.drop_constraint("ck_scene_versions_display_name", "scene_versions", type_="check")
    op.drop_column("scene_versions", "display_name")
