"""Migration 0003: `video_sources.declared_frame_count` (T051).

Runs only against `destructive_database_url()`: every test goes back to `base`.
The `downgrade` of 0003 exists only for these fixtures; environments are never
recovered with a downgrade.
"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCENE_REVISION = "0002_scene_configuration"


@pytest.fixture()
def alembic_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", destructive_database_url())
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    return Config(BACKEND_DIR / "alembic.ini")


@pytest.fixture()
def database_at_0002(alembic_config: Config):
    """A database at 0002 with one registered video session."""

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, SCENE_REVISION)
    engine = create_engine(destructive_database_url())
    session_id = _insert_video_session(engine)
    yield engine, session_id
    engine.dispose()
    command.downgrade(alembic_config, "base")


def _insert_video_session(engine: Engine) -> UUID:
    camera_id = uuid4()
    session_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO cameras (id, name, name_key) VALUES (:id, 'Cam', 'cam')"),
            {"id": camera_id},
        )
        connection.execute(
            text(
                "INSERT INTO sessions (id, name, camera_id, registered_camera_id, source_kind) "
                "VALUES (:id, 'Video', 'Cam', :camera, 'video_file')"
            ),
            {"id": session_id, "camera": camera_id},
        )
        connection.execute(
            text(
                "INSERT INTO video_sources (session_id, relative_path, original_filename, "
                "size_bytes, sha256, origin_machine_id, width, height, fps, fps_is_estimated, "
                "frame_count, duration_seconds) VALUES (:id, 'x.avi', 'x.avi', 10, :sha, "
                "'equipo-test', 640, 480, 25, false, 50, 2)"
            ),
            {"id": session_id, "sha": "0" * 64},
        )
    return session_id


def _set_declared(engine: Engine, session_id: UUID, value: int | None) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE video_sources SET declared_frame_count = :value WHERE session_id = :id"),
            {"value": value, "id": session_id},
        )


def test_existing_rows_keep_a_null_declared_frame_count(
    alembic_config: Config, database_at_0002
) -> None:
    engine, session_id = database_at_0002

    command.upgrade(alembic_config, "head")

    columns = {column["name"]: column for column in inspect(engine).get_columns("video_sources")}
    assert columns["declared_frame_count"]["nullable"] is True
    with engine.connect() as connection:
        declared = connection.scalar(
            text("SELECT declared_frame_count FROM video_sources WHERE session_id = :id"),
            {"id": session_id},
        )
    assert declared is None


@pytest.mark.parametrize("value", [0, -1])
def test_declared_frame_count_must_be_positive(
    alembic_config: Config, database_at_0002, value: int
) -> None:
    engine, session_id = database_at_0002
    command.upgrade(alembic_config, "head")

    with pytest.raises(IntegrityError):
        _set_declared(engine, session_id, value)

    _set_declared(engine, session_id, 50)
    _set_declared(engine, session_id, None)


def test_upgrade_is_repeatable(alembic_config: Config, database_at_0002) -> None:
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")

    engine, _ = database_at_0002
    names = {column["name"] for column in inspect(engine).get_columns("video_sources")}
    assert "declared_frame_count" in names
