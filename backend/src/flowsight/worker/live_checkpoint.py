"""Independent, bounded transactional writer; it never owns an image."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from flowsight.capture.contracts import CaptureError


@dataclass(frozen=True)
class CheckpointSnapshot:
    metadata: dict
    facts: tuple
    slots: dict
    buckets: tuple[dict, ...]


class LiveCheckpointWriter:
    def __init__(
        self,
        persist,
        *,
        interval_s=1.0,
        failure_timeout_s=5.0,
        max_facts=4096,
        on_failure=None,
        clock=time.monotonic,
    ):
        if not 0 < interval_s <= 1 or not 0 < failure_timeout_s <= 5 or not 1 <= max_facts <= 4096:
            raise ValueError("Invalid checkpoint bounds")
        self.persist = persist
        self.interval_s = interval_s
        self.failure_timeout_s = failure_timeout_s
        self.max_facts = max_facts
        self.on_failure = on_failure
        self.clock = clock
        self.error = None
        self.checkpoint_revision = 0
        self.checkpoint_at = None
        self._metadata = None
        self._facts, self._slots, self._buckets = {}, {}, {}
        self._pending_since = None
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def pending_counts(self):
        with self._lock:
            return len(self._facts), len(self._slots), len(self._buckets)

    def _fail(self, code):
        with self._lock:
            first = self.error is None
            self.error = self.error or code
        if first and self.on_failure is not None:
            self.on_failure(code)

    def check_health(self):
        with self._lock:
            overdue = (
                self._pending_since is not None
                and self.clock() - self._pending_since >= self.failure_timeout_s
            )
        if overdue:
            self._fail("database_unavailable")
        if self.error is not None:
            raise CaptureError(self.error)

    def submit(self, metadata, *, facts, slots, buckets):
        self.check_health()
        facts_by_key = {fact.candidate_sequence: fact for fact in facts}
        buckets_by_key = {(row["shop_id"], row["bucket_index"]): dict(row) for row in buckets}
        with self._lock:
            overflow = (
                len(self._facts.keys() | facts_by_key.keys()) > self.max_facts
                or len(self._slots.keys() | slots.keys()) > 20000
                or len(self._buckets.keys() | buckets_by_key.keys()) > 3600
            )
            if not overflow:
                if self._pending_since is None:
                    self._pending_since = self.clock()
                self._metadata = dict(metadata)
                self._facts.update(facts_by_key)
                self._slots.update(slots)
                self._buckets.update(buckets_by_key)
        if overflow:
            self._fail("live_buffer_limit")
            raise CaptureError("live_buffer_limit")

    def start(self):
        self._thread.start()

    def _run(self):
        while not self._closed.wait(self.interval_s):
            try:
                self.check_health()
                self.flush()
            except CaptureError as error:
                self._fail(error.code)
                return
            except Exception:
                try:
                    self.check_health()
                except CaptureError:
                    return

    def flush(self):
        # A final flush joins any active write; inference never takes this lock.
        if not self._write_lock.acquire(timeout=self.failure_timeout_s):
            self._fail("database_unavailable")
            raise CaptureError("database_unavailable")
        try:
            self.check_health()
            with self._lock:
                if self._metadata is None or self._metadata["revision"] <= self.checkpoint_revision:
                    return
                snapshot = CheckpointSnapshot(
                    dict(self._metadata),
                    tuple(self._facts.values()),
                    dict(self._slots),
                    tuple(dict(row) for row in self._buckets.values()),
                )
            self.persist(snapshot)
            with self._lock:
                self.checkpoint_revision = snapshot.metadata["revision"]
                self.checkpoint_at = datetime.now(UTC)
                for fact in snapshot.facts:
                    if self._facts.get(fact.candidate_sequence) is fact:
                        del self._facts[fact.candidate_sequence]
                for slot, change in snapshot.slots.items():
                    if self._slots.get(slot) is change:
                        del self._slots[slot]
                for row in snapshot.buckets:
                    key = (row["shop_id"], row["bucket_index"])
                    if self._buckets.get(key) == row:
                        del self._buckets[key]
                self._pending_since = (
                    None if self._metadata["revision"] == self.checkpoint_revision else self.clock()
                )
        finally:
            self._write_lock.release()

    def close(self):
        self._closed.set()
        if self._thread.ident is not None:
            self._thread.join(2)
