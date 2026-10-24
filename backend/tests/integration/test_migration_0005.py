"""Migration 0005 adds scene events and shop metrics without touching official measures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.historical_migration


def test_upgrade_from_0004_adds_scene_metrics_and_keeps_official_measures(
    monkeypatch,
) -> None:
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0004_video_analysis")

    engine = create_engine(database_url)
    before = set(inspect(engine).get_table_names())
    assert "scene_events" not in before
    official_columns = {
        column["name"] for column in inspect(engine).get_columns("analysis_measures")
    }

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {"scene_events", "shop_metrics", "traffic_buckets"}.issubset(
        set(inspector.get_table_names())
    )
    assert official_columns == {
        column["name"] for column in inspector.get_columns("analysis_measures")
    }
    unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("shop_metrics")
    }
    assert ("job_id", "shop_id", "code") in unique
    indexes = {tuple(index["column_names"]) for index in inspector.get_indexes("scene_events")}
    assert ("session_id", "shop_id", "video_timestamp_seconds") in indexes

    command.downgrade(config, "0004_video_analysis")
    after = set(inspect(engine).get_table_names())
    assert "scene_events" not in after
    assert "analysis_measures" in after
    engine.dispose()
