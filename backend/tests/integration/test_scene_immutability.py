"""Scene configuration is immutable at the database layer (FR-023, SC-006).

The `flowsight_forbid_mutation` trigger of migration 0002 rejects every direct
`UPDATE` or `DELETE` on the four scene tables; `TRUNCATE` does not fire row triggers,
so fixtures can still reset them. Runs only against `destructive_database_url()`.
"""

from __future__ import annotations

import json
import logging.config
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCENE_TABLES = ("scene_versions", "scene_version_shops", "scene_zones", "scene_entry_lines")
IMMUTABLE_MESSAGE = "scene configuration is immutable"

# Columna que identifica la fila de prueba en cada tabla y un UPDATE que la cambiaría.
KEY_COLUMN = {
    "scene_versions": "id",
    "scene_version_shops": "id",
    "scene_zones": "id",
    "scene_entry_lines": "version_shop_id",
}
UPDATES = {
    "scene_versions": "UPDATE scene_versions SET frame_width = frame_width + 1 WHERE id = :key",
    "scene_version_shops": "UPDATE scene_version_shops SET name = 'Otro' WHERE id = :key",
    "scene_zones": "UPDATE scene_zones SET polygon = '[]'::jsonb WHERE id = :key",
    "scene_entry_lines": (
        "UPDATE scene_entry_lines SET entry_direction = 'b_to_a' WHERE version_shop_id = :key"
    ),
}

FRONT_ZONE = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
INTERIOR_ZONE = [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]]


@dataclass(frozen=True)
class SceneRows:
    version_id: UUID
    version_shop_id: UUID
    front_zone_id: UUID

    def key(self, table: str) -> UUID:
        return {
            "scene_versions": self.version_id,
            "scene_version_shops": self.version_shop_id,
            "scene_zones": self.front_zone_id,
            "scene_entry_lines": self.version_shop_id,
        }[table]


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    database_url = destructive_database_url()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
        monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
        config = Config(BACKEND_DIR / "alembic.ini")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        try:
            yield engine
        finally:
            engine.dispose()
            command.downgrade(config, "base")


@pytest.fixture()
def scene(engine: Engine) -> SceneRows:
    with engine.begin() as connection:
        return _insert_scene(connection)


def _insert_scene(connection: Connection) -> SceneRows:
    """One camera, a video session with its reference frame, one shop and a version v1
    with that shop, its front and interior zones and its entry line."""

    camera_id, session_id, shop_id = uuid4(), uuid4(), uuid4()
    version_id, version_shop_id, front_zone_id = uuid4(), uuid4(), uuid4()
    camera_name = f"Cámara {camera_id.hex[:8]}"
    connection.execute(
        text("INSERT INTO cameras (id, name, name_key) VALUES (:id, :name, :name_key)"),
        {"id": camera_id, "name": camera_name, "name_key": camera_name.casefold()},
    )
    connection.execute(
        text(
            "INSERT INTO sessions (id, name, camera_id, registered_camera_id, source_kind) "
            "VALUES (:id, 'Video', :camera_name, :camera, 'video_file')"
        ),
        {"id": session_id, "camera_name": camera_name, "camera": camera_id},
    )
    connection.execute(
        text(
            "INSERT INTO reference_frames (session_id, frame_index, video_timestamp_seconds, "
            "width, height, media_type, image) "
            "VALUES (:session, 0, 0, 1280, 720, 'image/jpeg', :image)"
        ),
        {"session": session_id, "image": b"\xff\xd8\xff\xd9"},
    )
    connection.execute(
        text("INSERT INTO shops (id, camera_id) VALUES (:id, :camera)"),
        {"id": shop_id, "camera": camera_id},
    )
    connection.execute(
        text(
            "INSERT INTO scene_versions (id, camera_id, version_number, reference_session_id, "
            "frame_width, frame_height, created_by_machine_id) "
            "VALUES (:id, :camera, 1, :session, 1280, 720, 'maquina-test')"
        ),
        {"id": version_id, "camera": camera_id, "session": session_id},
    )
    connection.execute(
        text(
            "INSERT INTO scene_version_shops "
            "(id, scene_version_id, shop_id, camera_id, position, name, name_key) "
            "VALUES (:id, :version, :shop, :camera, 0, 'Local A', 'local a')"
        ),
        {"id": version_shop_id, "version": version_id, "shop": shop_id, "camera": camera_id},
    )
    for zone_id, role, polygon in (
        (front_zone_id, "front", FRONT_ZONE),
        (uuid4(), "interior", INTERIOR_ZONE),
    ):
        connection.execute(
            text(
                "INSERT INTO scene_zones (id, version_shop_id, role, polygon) "
                "VALUES (:id, :version_shop, :role, CAST(:polygon AS jsonb))"
            ),
            {
                "id": zone_id,
                "version_shop": version_shop_id,
                "role": role,
                "polygon": json.dumps(polygon),
            },
        )
    connection.execute(
        text(
            "INSERT INTO scene_entry_lines "
            "(version_shop_id, start_x, start_y, end_x, end_y, entry_direction) "
            "VALUES (:version_shop, 0.1, 0.45, 0.4, 0.45, 'a_to_b')"
        ),
        {"version_shop": version_shop_id},
    )
    return SceneRows(version_id, version_shop_id, front_zone_id)


def _row(engine: Engine, table: str, key: UUID) -> dict | None:
    with engine.connect() as connection:
        return connection.scalar(
            text(f"SELECT to_jsonb(t) FROM {table} t WHERE t.{KEY_COLUMN[table]} = :key"),
            {"key": key},
        )


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("table", SCENE_TABLES)
def test_direct_mutation_is_rejected_and_row_is_unchanged(
    engine: Engine, scene: SceneRows, table: str, operation: str
) -> None:
    key = scene.key(table)
    before = _row(engine, table, key)
    assert before is not None

    statement = (
        UPDATES[table]
        if operation == "update"
        else f"DELETE FROM {table} WHERE {KEY_COLUMN[table]} = :key"
    )
    # El error aborta la transacción: cada intento usa su propia conexión.
    with pytest.raises(DBAPIError, match=IMMUTABLE_MESSAGE):
        with engine.begin() as connection:
            connection.execute(text(statement), {"key": key})

    assert _row(engine, table, key) == before


def test_truncate_still_resets_scene_tables(engine: Engine, scene: SceneRows) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE scene_entry_lines, scene_zones, scene_version_shops, scene_versions "
                "CASCADE"
            )
        )

    with engine.connect() as connection:
        counts = {
            table: connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in SCENE_TABLES
        }
    assert counts == dict.fromkeys(SCENE_TABLES, 0)

    # Después del TRUNCATE se puede volver a cargar una escena, y sigue siendo inmutable.
    with engine.begin() as connection:
        reloaded = _insert_scene(connection)
    with pytest.raises(DBAPIError, match=IMMUTABLE_MESSAGE):
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM scene_versions WHERE id = :key"), {"key": reloaded.version_id}
            )
