"""Migration 0015 adds visit patterns without changing shop metrics or the funnel."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.historical_migration
TABLES = {
    "visit_pattern_reports",
    "visit_area_transitions",
    "visit_sequences",
    "visit_shop_transitions",
    "visit_groups",
    "visit_group_members",
}
METRIC_CODES = (
    "traffic_total",
    "store_pass",
    "entries",
    "exits",
    "entry_rate",
    "dwell_mean_seconds",
    "dwell_median_seconds",
    "visible_occupancy",
)


def test_upgrade_from_0014_adds_visit_patterns_and_keeps_closed_tables(monkeypatch) -> None:
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0014_shop_funnel")

    engine = create_engine(database_url)
    before_events = {column["name"] for column in inspect(engine).get_columns("scene_events")}
    before_funnels = {column["name"] for column in inspect(engine).get_columns("shop_funnels")}

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert TABLES.issubset(set(inspector.get_table_names()))
    assert {column["name"] for column in inspector.get_columns("scene_events")} == before_events
    assert {column["name"] for column in inspector.get_columns("shop_funnels")} == before_funnels
    report_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("visit_pattern_reports")
    }
    area_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("visit_area_transitions")
    }
    shop_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("visit_shop_transitions")
    }
    group_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("visit_groups")
    }
    member_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("visit_group_members")
    }
    assert ("job_id",) in report_unique
    assert (
        "job_id",
        "from_shop_id",
        "from_zone_role",
        "to_shop_id",
        "to_zone_role",
    ) in area_unique
    assert ("job_id", "from_shop_id", "to_shop_id") in shop_unique
    assert ("job_id", "ordinal") in group_unique
    assert ("group_id", "track_id") in member_unique
    with engine.connect() as connection:
        metric_codes = connection.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'shop_metric_code' ORDER BY e.enumsortorder"
            )
        ).scalars().all()
        zone_roles = connection.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'scene_zone_role' ORDER BY e.enumsortorder"
            )
        ).scalars().all()
    assert tuple(metric_codes) == METRIC_CODES
    assert tuple(zone_roles) == ("front", "interior", "window")

    command.downgrade(config, "0014_shop_funnel")
    inspector = inspect(engine)
    assert TABLES.isdisjoint(set(inspector.get_table_names()))
    assert "shop_funnels" in inspector.get_table_names()
    assert "scene_events" in inspector.get_table_names()
    engine.dispose()
