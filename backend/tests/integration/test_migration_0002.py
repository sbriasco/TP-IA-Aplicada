"""Migration 0002: registered cameras, scene tables and the video job gate.

Runs only against `destructive_database_url()`: every test goes back to `base`.
The `downgrade` of 0002 exists only for these fixtures; environments are never
recovered with a downgrade.
"""

from __future__ import annotations

import logging
import logging.config
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
INITIAL_REVISION = "0001_initial"
SCENE_TABLES = ("scene_versions", "scene_version_shops", "scene_zones", "scene_entry_lines")
CHECK_VIOLATION = "23514"

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

# (camera_id de texto de specs/002, orden de creación). "Cam01" aparece dos veces:
# un mismo texto genera una sola cámara aunque tenga varias sesiones.
LEGACY_SESSIONS: tuple[tuple[str, int], ...] = (
    ("Cam01", 0),
    ("cam01 ", 1),
    ("Otra", 2),
    ("Straße", 3),
    ("STRASSE", 4),
    ("\tTab01\n", 5),
    ("Cam01", 6),
)

# Nombre y name_key esperados por cada camera_id de texto. En cada choque, el de
# min(created_at) conserva el nombre y el otro recibe " (2)"; los nombres se guardan
# sin los espacios de los extremos.
EXPECTED_CAMERAS: dict[str, tuple[str, str]] = {
    "Cam01": ("Cam01", "cam01"),
    "cam01 ": ("cam01 (2)", "cam01 (2)"),
    "Otra": ("Otra", "otra"),
    "Straße": ("Straße", "strasse"),
    "STRASSE": ("STRASSE (2)", "strasse (2)"),
    "\tTab01\n": ("Tab01", "tab01"),
}


@pytest.fixture()
def alembic_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", destructive_database_url())
    # env.py llama a fileConfig, que quita los handlers de caplog; en estas pruebas
    # dejamos el logging como lo configura pytest.
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    return Config(BACKEND_DIR / "alembic.ini")


@pytest.fixture()
def legacy_database(alembic_config: Config):
    """A database at 0001 with the synthetic sessions of specs/002."""

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, INITIAL_REVISION)
    engine = create_engine(destructive_database_url())
    session_ids: list[tuple[UUID, str]] = []
    with engine.begin() as connection:
        for camera_id, order in LEGACY_SESSIONS:
            session_id = uuid4()
            session_ids.append((session_id, camera_id))
            connection.execute(
                text(
                    "INSERT INTO sessions (id, name, camera_id, source_kind, created_at) "
                    "VALUES (:id, :name, :camera_id, 'synthetic', :created_at)"
                ),
                {
                    "id": session_id,
                    "name": f"Sesión {order}",
                    "camera_id": camera_id,
                    "created_at": T0 + timedelta(minutes=order),
                },
            )
        connection.execute(
            text(
                "INSERT INTO processing_jobs (id, session_id, kind, status) "
                "VALUES (:id, :session_id, 'synthetic_base_flow', 'completed')"
            ),
            {"id": uuid4(), "session_id": session_ids[0][0]},
        )
    yield engine, session_ids
    engine.dispose()
    command.downgrade(alembic_config, "base")


def _cameras_by_legacy_id(connection: Connection) -> dict[str, tuple[str, str]]:
    rows = connection.execute(
        text(
            "SELECT s.camera_id, c.name, c.name_key "
            "FROM sessions s JOIN cameras c ON c.id = s.registered_camera_id"
        )
    ).all()
    return {camera_id: (name, name_key) for camera_id, name, name_key in rows}


def test_migration_creates_one_camera_per_distinct_camera_id_with_suffix_on_collision(
    alembic_config: Config, legacy_database
) -> None:
    engine, _ = legacy_database
    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        camera_count = connection.scalar(text("SELECT count(*) FROM cameras"))
        by_legacy_id = _cameras_by_legacy_id(connection)
        stored = connection.execute(text("SELECT name, name_key FROM cameras")).all()

    assert camera_count == len(EXPECTED_CAMERAS)
    assert by_legacy_id == EXPECTED_CAMERAS

    from flowsight.services.cameras import normalize_name_key

    for name, name_key in stored:
        assert normalize_name_key(name) == name_key


def test_migration_keeps_sessions_and_their_text_camera_id(
    alembic_config: Config, legacy_database
) -> None:
    engine, session_ids = legacy_database
    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, camera_id, registered_camera_id FROM sessions")
        ).all()
        column = next(
            column
            for column in inspect(connection).get_columns("sessions")
            if column["name"] == "registered_camera_id"
        )

    assert sorted((row.id, row.camera_id) for row in rows) == sorted(session_ids)
    assert all(row.registered_camera_id is not None for row in rows)
    assert column["nullable"] is False
    # Las dos sesiones "Cam01" comparten cámara; ninguna otra se fusionó.
    cameras = {row.camera_id: set() for row in rows}
    for row in rows:
        cameras[row.camera_id].add(row.registered_camera_id)
    assert all(len(ids) == 1 for ids in cameras.values())
    assert len({next(iter(ids)) for ids in cameras.values()}) == len(EXPECTED_CAMERAS)


def test_migration_warns_about_each_name_conflict(
    alembic_config: Config, legacy_database, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        command.upgrade(alembic_config, "head")

    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and record.name.startswith("alembic")
    ]
    assert any("Cam01" in message and "cam01" in message for message in warnings)
    assert any("Straße" in message and "STRASSE" in message for message in warnings)
    assert not any("Otra" in message for message in warnings)


def test_migration_adds_enum_values(alembic_config: Config, legacy_database) -> None:
    engine, _ = legacy_database
    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        source_kinds = set(
            connection.scalars(text("SELECT unnest(enum_range(NULL::source_kind))::text"))
        )
        job_kinds = set(connection.scalars(text("SELECT unnest(enum_range(NULL::job_kind))::text")))

    assert {"synthetic", "video_file"} <= source_kinds
    assert {"synthetic_base_flow", "video_analysis"} <= job_kinds


def _insert_scene_version(connection: Connection) -> tuple[UUID, UUID, UUID]:
    camera_id, session_id, version_id = uuid4(), uuid4(), uuid4()
    connection.execute(
        text(
            "INSERT INTO cameras (id, name, name_key, created_at) "
            "VALUES (:id, 'Nueva', 'nueva', now())"
        ),
        {"id": camera_id},
    )
    connection.execute(
        text(
            "INSERT INTO sessions (id, name, camera_id, registered_camera_id, source_kind) "
            "VALUES (:id, 'Video', 'Nueva', :camera, 'video_file')"
        ),
        {"id": session_id, "camera": camera_id},
    )
    connection.execute(
        text(
            "INSERT INTO scene_versions (id, camera_id, version_number, reference_session_id, "
            "frame_width, frame_height, created_at) "
            "VALUES (:id, :camera, 1, :session, 1920, 1080, now())"
        ),
        {"id": version_id, "camera": camera_id, "session": session_id},
    )
    return camera_id, session_id, version_id


def _pgcode(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def test_processing_jobs_check_ties_video_analysis_to_scene_version(
    alembic_config: Config, legacy_database
) -> None:
    engine, _ = legacy_database
    command.upgrade(alembic_config, "head")
    with engine.begin() as connection:
        camera_id, session_id, version_id = _insert_scene_version(connection)

    insert_job = text(
        "INSERT INTO processing_jobs "
        "(id, session_id, kind, status, scene_version_id, registered_camera_id) "
        "VALUES (:id, :session, :kind, 'pending', :version, :camera)"
    )
    with engine.begin() as connection:
        connection.execute(
            insert_job,
            {
                "id": uuid4(),
                "session": session_id,
                "kind": "video_analysis",
                "version": version_id,
                "camera": camera_id,
            },
        )

    rejected = (
        ("video_analysis", None, None),
        ("synthetic_base_flow", version_id, camera_id),
    )
    for kind, version, camera in rejected:
        with pytest.raises(IntegrityError) as error:
            with engine.begin() as connection:
                connection.execute(
                    insert_job,
                    {
                        "id": uuid4(),
                        "session": session_id,
                        "kind": kind,
                        "version": version,
                        "camera": camera,
                    },
                )
        assert _pgcode(error.value) == CHECK_VIOLATION, kind


def test_scene_tables_are_immutable(alembic_config: Config, legacy_database) -> None:
    engine, _ = legacy_database
    command.upgrade(alembic_config, "head")

    with engine.connect() as connection:
        triggered = set(
            connection.scalars(
                text(
                    "SELECT t.tgrelid::regclass::text FROM pg_trigger t "
                    "JOIN pg_proc p ON p.oid = t.tgfoid "
                    "WHERE p.proname = 'flowsight_forbid_mutation' AND NOT t.tgisinternal"
                )
            )
        )
    assert triggered == set(SCENE_TABLES)

    with engine.begin() as connection:
        _, _, version_id = _insert_scene_version(connection)
    for statement in (
        "UPDATE scene_versions SET version_number = 2 WHERE id = :id",
        "DELETE FROM scene_versions WHERE id = :id",
    ):
        with pytest.raises(DBAPIError, match="scene configuration is immutable"):
            with engine.begin() as connection:
                connection.execute(text(statement), {"id": version_id})


def test_upgrade_is_repeatable_and_downgrade_to_0001_works_as_fixture(
    alembic_config: Config, legacy_database
) -> None:
    engine: Engine
    engine, session_ids = legacy_database
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")

    command.downgrade(alembic_config, INITIAL_REVISION)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        session_columns = {column["name"] for column in inspect(connection).get_columns("sessions")}
        job_columns = {
            column["name"] for column in inspect(connection).get_columns("processing_jobs")
        }
        functions = connection.scalar(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'flowsight_forbid_mutation'")
        )
        new_enums = connection.scalar(
            text("SELECT count(*) FROM pg_type WHERE typname IN ('zone_role', 'entry_direction')")
        )
        sessions = connection.scalar(text("SELECT count(*) FROM sessions"))

    assert tables.isdisjoint(
        {"cameras", "video_sources", "reference_frames", "shops", *SCENE_TABLES}
    )
    assert "registered_camera_id" not in session_columns
    assert {"scene_version_id", "registered_camera_id"}.isdisjoint(job_columns)
    assert functions == 0
    assert new_enums == 0
    assert sessions == len(session_ids)

    # Volver a subir sobre los mismos datos (y con los valores de enum que quedaron)
    # reproduce el mismo resultado.
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        assert _cameras_by_legacy_id(connection) == EXPECTED_CAMERAS
