"""Registered cameras, video sources and immutable scene configuration.

The `downgrade` exists only for the pytest fixtures (`downgrade base` / `upgrade head`);
environments are never recovered with a downgrade.
"""

import logging
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_scene_configuration"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

CAMERA_NAME_LENGTH = 120
SCENE_TABLES = ("scene_versions", "scene_version_shops", "scene_zones", "scene_entry_lines")

zone_role = postgresql.ENUM("interior", "front", "showcase", name="zone_role", create_type=False)
entry_direction = postgresql.ENUM("a_to_b", "b_to_a", name="entry_direction", create_type=False)


def normalize_name_key(name: str) -> str:
    """Fixed copy of `flowsight.services.cameras.normalize_name_key`.

    Migrations never import application code: this one must keep computing the same
    keys it computed when it was written.
    """

    return name.strip().casefold()


def upgrade() -> None:
    # PostgreSQL can't use a new enum value inside the transaction that added it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'video_file'")
        op.execute("ALTER TYPE job_kind ADD VALUE IF NOT EXISTS 'video_analysis'")

    bind = op.get_bind()
    zone_role.create(bind, checkfirst=True)
    entry_direction.create(bind, checkfirst=True)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(CAMERA_NAME_LENGTH), nullable=False),
        sa.Column("name_key", sa.String(CAMERA_NAME_LENGTH), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name_key", name="uq_cameras_name_key"),
    )

    op.add_column("sessions", sa.Column("registered_camera_id", sa.Uuid(), nullable=True))
    _migrate_session_cameras(bind)
    op.alter_column("sessions", "registered_camera_id", nullable=False)
    op.create_foreign_key(
        "fk_sessions_registered_camera_id",
        "sessions",
        "cameras",
        ["registered_camera_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_sessions_id_registered_camera_id", "sessions", ["id", "registered_camera_id"]
    )

    op.create_table(
        "video_sources",
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), primary_key=True),
        sa.Column("relative_path", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("origin_machine_id", sa.String(40), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Numeric(9, 4), nullable=False),
        sa.Column("fps_is_estimated", sa.Boolean(), nullable=False),
        sa.Column("frame_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_video_sources_size_bytes"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_video_sources_size"),
        sa.CheckConstraint("fps > 0", name="ck_video_sources_fps"),
        sa.CheckConstraint("frame_count > 0", name="ck_video_sources_frame_count"),
    )
    op.create_index("ix_video_sources_sha256", "video_sources", ["sha256"])

    op.create_table(
        "reference_frames",
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), primary_key=True),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("video_timestamp_seconds", sa.Numeric(12, 6), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(40), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("frame_index >= 0", name="ck_reference_frames_frame_index"),
        sa.CheckConstraint(
            "video_timestamp_seconds >= 0", name="ck_reference_frames_video_timestamp_seconds"
        ),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_reference_frames_size"),
    )

    op.create_table(
        "shops",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "camera_id", name="uq_shops_id_camera_id"),
    )

    op.create_table(
        "scene_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("camera_id", sa.Uuid(), sa.ForeignKey("cameras.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("reference_session_id", sa.Uuid(), nullable=False),
        sa.Column("frame_width", sa.Integer(), nullable=False),
        sa.Column("frame_height", sa.Integer(), nullable=False),
        sa.Column("created_by_machine_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["reference_session_id", "camera_id"],
            ["sessions.id", "sessions.registered_camera_id"],
            name="fk_scene_versions_reference_session",
        ),
        sa.UniqueConstraint(
            "camera_id", "version_number", name="uq_scene_versions_camera_id_version_number"
        ),
        sa.UniqueConstraint("id", "camera_id", name="uq_scene_versions_id_camera_id"),
        sa.CheckConstraint("version_number >= 1", name="ck_scene_versions_version_number"),
        sa.CheckConstraint(
            "frame_width > 0 AND frame_height > 0", name="ck_scene_versions_frame_size"
        ),
    )

    op.create_table(
        "scene_version_shops",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scene_version_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("camera_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.ForeignKeyConstraint(
            ["scene_version_id", "camera_id"],
            ["scene_versions.id", "scene_versions.camera_id"],
            name="fk_scene_version_shops_scene_version",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id", "camera_id"],
            ["shops.id", "shops.camera_id"],
            name="fk_scene_version_shops_shop",
        ),
        sa.UniqueConstraint(
            "scene_version_id", "name_key", name="uq_scene_version_shops_scene_version_id_name_key"
        ),
        sa.UniqueConstraint(
            "scene_version_id", "shop_id", name="uq_scene_version_shops_scene_version_id_shop_id"
        ),
        sa.CheckConstraint("position >= 0", name="ck_scene_version_shops_position"),
    )

    op.create_table(
        "scene_zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "version_shop_id",
            sa.Uuid(),
            sa.ForeignKey("scene_version_shops.id"),
            nullable=False,
        ),
        sa.Column("role", zone_role, nullable=False),
        sa.Column("polygon", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("version_shop_id", "role", name="uq_scene_zones_version_shop_id_role"),
    )

    op.create_table(
        "scene_entry_lines",
        sa.Column(
            "version_shop_id",
            sa.Uuid(),
            sa.ForeignKey("scene_version_shops.id"),
            primary_key=True,
        ),
        sa.Column("start_x", sa.Double(), nullable=False),
        sa.Column("start_y", sa.Double(), nullable=False),
        sa.Column("end_x", sa.Double(), nullable=False),
        sa.Column("end_y", sa.Double(), nullable=False),
        sa.Column("entry_direction", entry_direction, nullable=False),
        sa.CheckConstraint(
            "start_x BETWEEN 0 AND 1 AND start_y BETWEEN 0 AND 1 "
            "AND end_x BETWEEN 0 AND 1 AND end_y BETWEEN 0 AND 1",
            name="ck_scene_entry_lines_normalized",
        ),
    )

    op.add_column("processing_jobs", sa.Column("scene_version_id", sa.Uuid(), nullable=True))
    op.add_column("processing_jobs", sa.Column("registered_camera_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_processing_jobs_session_camera",
        "processing_jobs",
        "sessions",
        ["session_id", "registered_camera_id"],
        ["id", "registered_camera_id"],
    )
    op.create_foreign_key(
        "fk_processing_jobs_scene_version",
        "processing_jobs",
        "scene_versions",
        ["scene_version_id", "registered_camera_id"],
        ["id", "camera_id"],
    )
    op.create_check_constraint(
        "ck_processing_jobs_video_analysis_scene",
        "processing_jobs",
        "(kind = 'video_analysis') = "
        "(scene_version_id IS NOT NULL AND registered_camera_id IS NOT NULL)",
    )

    op.execute(
        """
        CREATE FUNCTION flowsight_forbid_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'scene configuration is immutable';
        END;
        $$
        """
    )
    for table in SCENE_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION flowsight_forbid_mutation()"
        )


def _migrate_session_cameras(bind: sa.Connection) -> None:
    """Create one camera per distinct `sessions.camera_id`, suffixing name collisions."""

    rows = bind.execute(
        sa.text(
            "SELECT camera_id, min(created_at) AS first_seen FROM sessions "
            "GROUP BY camera_id ORDER BY first_seen, camera_id"
        )
    ).all()

    groups: dict[str, list[tuple[str, object]]] = {}
    for camera_id, first_seen in rows:
        groups.setdefault(normalize_name_key(camera_id), []).append((camera_id, first_seen))

    # The first camera of each group keeps its name; suffixes never take a key in use.
    used_keys = set(groups)
    assignments: list[tuple[str, str, object]] = []
    for key, members in groups.items():
        first_id, first_seen = members[0]
        assignments.append((first_id, first_id.strip(), first_seen))
        renamed: list[str] = []
        suffix_number = 2
        for camera_id, seen in members[1:]:
            while True:
                name = _suffixed(camera_id.strip(), suffix_number)
                suffix_number += 1
                if normalize_name_key(name) not in used_keys:
                    break
            used_keys.add(normalize_name_key(name))
            assignments.append((camera_id, name, seen))
            renamed.append(f"{camera_id!r} -> {name!r}")
        if renamed:
            logger.warning(
                "Cámaras con el mismo nombre normalizado %r: %r conserva el nombre; "
                "renombradas sin fusionar sesiones: %s",
                key,
                first_id,
                ", ".join(renamed),
            )

    for camera_id, name, first_seen in assignments:
        registered_camera_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO cameras (id, name, name_key, created_at) "
                "VALUES (:id, :name, :name_key, :created_at)"
            ),
            {
                "id": registered_camera_id,
                "name": name,
                "name_key": normalize_name_key(name),
                "created_at": first_seen,
            },
        )
        bind.execute(
            sa.text(
                "UPDATE sessions SET registered_camera_id = :registered_camera_id "
                "WHERE camera_id = :camera_id"
            ),
            {"registered_camera_id": registered_camera_id, "camera_id": camera_id},
        )


def _suffixed(name: str, number: int) -> str:
    suffix = f" ({number})"
    return name[: CAMERA_NAME_LENGTH - len(suffix)] + suffix


def downgrade() -> None:
    op.drop_constraint("ck_processing_jobs_video_analysis_scene", "processing_jobs", type_="check")
    op.drop_constraint("fk_processing_jobs_scene_version", "processing_jobs", type_="foreignkey")
    op.drop_constraint("fk_processing_jobs_session_camera", "processing_jobs", type_="foreignkey")
    op.drop_column("processing_jobs", "registered_camera_id")
    op.drop_column("processing_jobs", "scene_version_id")

    op.drop_table("scene_entry_lines")
    op.drop_table("scene_zones")
    op.drop_table("scene_version_shops")
    op.drop_table("scene_versions")
    op.drop_table("shops")
    op.drop_table("reference_frames")
    op.drop_index("ix_video_sources_sha256", table_name="video_sources")
    op.drop_table("video_sources")
    op.execute("DROP FUNCTION flowsight_forbid_mutation()")

    op.drop_constraint("uq_sessions_id_registered_camera_id", "sessions", type_="unique")
    op.drop_constraint("fk_sessions_registered_camera_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "registered_camera_id")
    op.drop_table("cameras")

    bind = op.get_bind()
    entry_direction.drop(bind, checkfirst=True)
    zone_role.drop(bind, checkfirst=True)
    # The values added to source_kind and job_kind stay: PostgreSQL can't drop them,
    # and the downgrade of 0001 drops both types entirely.
