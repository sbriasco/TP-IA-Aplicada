"""Migration 0014 adds the shop funnel without changing the eight shop metrics."""

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


def test_upgrade_from_0013_adds_the_funnel_and_keeps_official_tables(monkeypatch) -> None:
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0013_scene_display_name")

    engine = create_engine(database_url)
    before_measures = {
        column["name"] for column in inspect(engine).get_columns("analysis_measures")
    }
    before_crossings = {
        column["name"] for column in inspect(engine).get_columns("line_crossings")
    }

    command.upgrade(config, "head")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"shop_funnels", "shop_funnel_stages", "shop_funnel_rates"}.issubset(tables)
    measures = {column["name"] for column in inspector.get_columns("analysis_measures")}
    crossings = {column["name"] for column in inspector.get_columns("line_crossings")}
    assert measures == before_measures
    assert crossings == before_crossings
    funnel_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("shop_funnels")
    }
    stage_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("shop_funnel_stages")
    }
    rate_unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("shop_funnel_rates")
    }
    assert ("job_id", "shop_id") in funnel_unique
    assert ("job_id", "shop_id", "stage") in stage_unique
    assert ("job_id", "shop_id", "code") in rate_unique
    with engine.connect() as connection:
        metric_codes = connection.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'shop_metric_code' ORDER BY e.enumsortorder"
            )
        ).scalars().all()
        event_kinds = connection.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'scene_event_kind'"
            )
        ).scalars().all()
    assert tuple(metric_codes) == METRIC_CODES
    assert "showcase_stop" in event_kinds

    command.downgrade(config, "0013_scene_display_name")
    after = set(inspect(engine).get_table_names())
    assert "shop_funnels" not in after
    assert "analysis_measures" in after
    assert "line_crossings" in after
    engine.dispose()
