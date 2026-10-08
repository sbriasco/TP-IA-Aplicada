"""One reading of database, migrations, worker heartbeat and the selected detector."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[3]
WORKER_FRESH_SECONDS = 5


def migration_status(database_url: str) -> str:
    """``current`` when the database matches the Alembic head, otherwise ``pending``."""

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
    return "current" if current == head else "pending"


def worker_status(database: Session, *, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    latest = database.scalar(text("SELECT max(heartbeat_at) FROM worker_machines"))
    if latest is None:
        return "unavailable"
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    age = (moment - latest).total_seconds()
    return "available" if age < WORKER_FRESH_SECONDS else "unavailable"


def startup_report(
    *,
    database: str,
    migrations: str,
    worker: str,
    detector: str,
) -> dict[str, str]:
    return {
        "database": database,
        "migrations": migrations,
        "api": "available",
        "worker": worker,
        "detector": detector,
    }
