"""FlowSight background worker bootstrap."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flowsight.core.config import Settings


def bootstrap_worker() -> Settings:
    """Validate configuration before the worker accepts any job."""

    from flowsight.core.config import load_settings

    return load_settings()


def run_worker() -> None:
    # Windows spawn reimports this module in the capture child. Keep DB, OpenCV
    # and model imports inside the worker entry point, outside that child path.
    from flowsight.db.session import create_database_engine, create_session_factory
    from flowsight.worker.lifecycle import process_next_job, recover_interrupted_jobs
    from flowsight.worker.live_channel import WorkerLiveChannel
    from flowsight.worker.live_control import MachineHeartbeat, MachineLease

    logging.basicConfig(level=logging.INFO)
    settings = bootstrap_worker()
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    fixture_path = Path(__file__).resolve().parents[4] / "fixtures" / "synthetic" / "base-flow.json"
    lease = (
        MachineLease(engine, settings.machine_id, settings.worker_id)
        if settings.machine_id is not None
        else None
    )
    heartbeat = None
    channel = None
    try:
        if lease is not None:
            if not lease.acquire(datetime.now(UTC)):
                logging.error("Ya hay un worker activo en este equipo.")
                return
            heartbeat = MachineHeartbeat(lease)
            heartbeat.start()
            if settings.live_channel_token is not None:
                channel = WorkerLiveChannel(settings, factory, lease)
                channel.start()
        with factory.begin() as database_session:
            recover_interrupted_jobs(
                database_session,
                datetime.now(UTC),
                machine_id=settings.machine_id or "unconfigured",
                worker_id=settings.worker_id,
            )
        while True:
            if heartbeat is not None:
                heartbeat.raise_if_failed()
            processed = process_next_job(
                factory,
                worker_id=settings.worker_id,
                fixture_path=fixture_path,
                now=lambda: datetime.now(UTC),
                settings=settings,
                owner_epoch=lease.owner_epoch if lease is not None else None,
                live_emit=channel.publish if channel is not None else None,
                owner_health=heartbeat.raise_if_failed if heartbeat is not None else None,
            )
            if processed is None:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if channel is not None:
            channel.stop()
        if heartbeat is not None:
            heartbeat.stop()
        if lease is not None:
            lease.release()
        engine.dispose()


if __name__ == "__main__":
    run_worker()
