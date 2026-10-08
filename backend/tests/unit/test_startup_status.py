"""Startup report fields, without opening a database."""

from datetime import UTC, datetime, timedelta

from flowsight.core.startup_status import startup_report, worker_status


class _Database:
    def __init__(self, latest):
        self.latest = latest

    def scalar(self, _statement):
        return self.latest


def test_report_names_every_check() -> None:
    report = startup_report(
        database="connected", migrations="pending", worker="unavailable", detector="fake"
    )
    assert report == {
        "database": "connected",
        "migrations": "pending",
        "api": "available",
        "worker": "unavailable",
        "detector": "fake",
    }


def test_worker_needs_a_fresh_heartbeat() -> None:
    now = datetime(2026, 10, 8, tzinfo=UTC)
    assert worker_status(_Database(now - timedelta(seconds=1)), now=now) == "available"
    assert worker_status(_Database(now - timedelta(seconds=6)), now=now) == "unavailable"
    assert worker_status(_Database(None), now=now) == "unavailable"
