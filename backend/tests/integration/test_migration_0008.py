"""Upgrade existing cameras safely; rollback metadata without deleting scene content."""

from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_camera_and_configuration_migrations_preserve_existing_data(monkeypatch):
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    engine = create_engine(database_url)
    camera_id = uuid4()
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "0006_session_removal")
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO cameras (id, name, name_key) VALUES (:id, 'Entrada', 'entrada')"),
                {"id": camera_id},
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT name, deleted_at FROM cameras WHERE id = :id"), {"id": camera_id}
            ).one() == ("Entrada", None)
        schema = inspect(engine)
        assert "scene_version_removals" in schema.get_table_names()
        assert (
            schema.get_foreign_keys("scene_version_removals")[0]["referred_table"]
            == "scene_versions"
        )
        command.downgrade(config, "0006_session_removal")
        assert "scene_version_removals" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM cameras WHERE id = :id"), {"id": camera_id}
                )
                == 1
            )
    finally:
        engine.dispose()
        command.downgrade(config, "base")
