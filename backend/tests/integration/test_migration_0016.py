"""Migration 0016 adds possible purchases without changing closed analytics tables."""

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
TABLES = {"possible_purchase_reports", "possible_purchase_members"}
CLOSED = (
    "scene_events",
    "shop_funnels",
    "visit_pattern_reports",
)


def test_upgrade_from_0015_adds_possible_purchase_and_keeps_closed_tables(
    monkeypatch,
) -> None:
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0015_visit_patterns")

    engine = create_engine(database_url)
    before = {
        table: {column["name"] for column in inspect(engine).get_columns(table)}
        for table in CLOSED
    }

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert TABLES.issubset(set(inspector.get_table_names()))
    for table, columns in before.items():
        assert {column["name"] for column in inspector.get_columns(table)} == columns

    report_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("possible_purchase_reports")
    }
    member_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("possible_purchase_members")
    }
    assert ("job_id",) in report_unique
    assert ("report_id", "track_id") in member_unique

    command.downgrade(config, "0015_visit_patterns")
    after = inspect(engine)
    assert not TABLES.intersection(set(after.get_table_names()))
    for table, columns in before.items():
        assert {column["name"] for column in after.get_columns(table)} == columns
