"""FlowSight background worker bootstrap."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from flowsight.core.config import Settings, load_settings
from flowsight.db.session import create_database_engine, create_session_factory
from flowsight.worker.lifecycle import process_next_job, recover_interrupted_jobs


def bootstrap_worker() -> Settings:
    """Validate configuration before the worker accepts any job."""

    return load_settings()


def run_worker() -> None:
    settings = bootstrap_worker()
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    fixture_path = Path(__file__).resolve().parents[4] / "fixtures" / "synthetic" / "base-flow.json"
    with factory.begin() as database_session:
        recover_interrupted_jobs(database_session, datetime.now(UTC))
    try:
        while True:
            processed = process_next_job(
                factory,
                worker_id=settings.worker_id,
                fixture_path=fixture_path,
                now=lambda: datetime.now(UTC),
            )
            if processed is None:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_worker()
