"""Machine ownership and short device reservations, without frame persistence."""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from flowsight.db.models import WorkerMachine
from flowsight.services.live_jobs import (
    LiveMachineError as LiveMachineError,
)
from flowsight.services.live_jobs import (
    release_reservation as release_reservation,
)
from flowsight.services.live_jobs import (
    reserve_machine as reserve_machine,
)


class MachineHeartbeat:
    def __init__(
        self,
        lease: MachineLease,
        *,
        interval_s: float = 1,
        on_lost: Callable[[], None] | None = None,
    ) -> None:
        self.lease = lease
        self.interval_s = interval_s
        self.on_lost = on_lost
        self._stop = threading.Event()
        self._error: LiveMachineError | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                self.lease.heartbeat(datetime.now(UTC))
            except Exception as exc:
                self._error = (
                    exc
                    if isinstance(exc, LiveMachineError)
                    else (LiveMachineError("database_unavailable"))
                )
                if self.on_lost is not None:
                    self.on_lost()
                return

    def start(self) -> None:
        self._thread.start()

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        self._stop.set()
        if self._thread.ident is not None:
            self._thread.join(2)


class MachineLease:
    """Session advisory lock: ownership survives transactions, never a process exit."""

    def __init__(self, engine: Engine, machine_id: str, worker_id: str) -> None:
        self.engine = engine
        self.machine_id = machine_id
        self.worker_id = worker_id
        self.owner_epoch = uuid.uuid4()
        digest = hashlib.sha256(f"flowsight-machine:{machine_id}".encode()).digest()
        self._key = int.from_bytes(digest[:8], "big", signed=True)
        self._connection: Connection | None = None

    def acquire(self, now: datetime) -> bool:
        if self._connection is not None:
            return True
        connection = self.engine.connect()
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key})
        connection.commit()
        if not acquired:
            connection.close()
            return False
        self._connection = connection
        try:
            with Session(self.engine) as database, database.begin():
                row = database.get(WorkerMachine, self.machine_id)
                if row is None:
                    row = WorkerMachine(machine_id=self.machine_id)
                    database.add(row)
                row.worker_id = self.worker_id
                row.owner_epoch = self.owner_epoch
                row.heartbeat_at = now
                row.capture_state = "idle"
                row.reservation_id = None
                row.reserved_until = None
        except BaseException:
            self._unlock()
            raise
        return True

    def heartbeat(self, now: datetime) -> None:
        if self._connection is None:
            raise LiveMachineError("worker_unavailable")
        # A reconnected session no longer owns the lock, even if a simple SELECT succeeds.
        unsigned = self._key & ((1 << 64) - 1)
        held = self._connection.scalar(
            text("""
            SELECT EXISTS (SELECT 1 FROM pg_locks
            WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND objsubid = 1
            AND classid::bigint = :high AND objid::bigint = :low AND granted)
        """),
            {"high": unsigned >> 32, "low": unsigned & ((1 << 32) - 1)},
        )
        self._connection.commit()
        if not held:
            self._unlock()
            raise LiveMachineError("worker_owner_lost")
        with Session(self.engine) as database, database.begin():
            row = database.scalar(
                select(WorkerMachine)
                .where(WorkerMachine.machine_id == self.machine_id)
                .with_for_update()
            )
            if row is None or row.owner_epoch != self.owner_epoch:
                raise LiveMachineError("worker_owner_lost")
            row.heartbeat_at = now

    def _unlock(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._key})
            connection.commit()
        except Exception:
            connection.invalidate()
        finally:
            connection.close()

    def release(self) -> None:
        if self._connection is None:
            return
        try:
            with Session(self.engine) as database, database.begin():
                row = database.scalar(
                    select(WorkerMachine)
                    .where(WorkerMachine.machine_id == self.machine_id)
                    .with_for_update()
                )
                if row is not None and row.owner_epoch == self.owner_epoch:
                    row.heartbeat_at = datetime.now(UTC) - timedelta(seconds=6)
                    row.capture_state = "idle"
                    row.reservation_id = None
                    row.reserved_until = None
        finally:
            self._unlock()
