"""Bounded runtime minute window; older minutes remain only in durable storage."""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from flowsight.vision.live_spatial import LiveCrossingFact

QUANTUM = Decimal(".000001")


@dataclass
class _Bucket:
    shop_id: uuid.UUID
    index: int
    end: Decimal
    entries: int = 0
    exits: int = 0
    observed: Decimal = Decimal(0)
    missing: Decimal = Decimal(0)
    pending: int = 0
    is_open: bool = True
    unknown_tail: bool = False
    revision: int = 0

    def message(self):
        start = Decimal(self.index * 60)
        end = self.end.quantize(QUANTUM)
        observed = min(self.observed.quantize(QUANTUM), end - start)
        missing = min(self.missing.quantize(QUANTUM), end - start - observed)
        return {
            "shop_id": str(self.shop_id),
            "bucket_index": self.index,
            "start_seconds": float(start),
            "end_seconds": float(end),
            "entries": self.entries,
            "exits": self.exits,
            "observed_seconds": float(observed),
            "missing_seconds": float(missing),
            "pending_count": self.pending,
            "is_open": self.is_open,
            "coverage_incomplete": self.missing > 0,
            "unknown_tail": self.unknown_tail,
            "revision": self.revision,
        }


class LiveBuckets:
    def __init__(self, shop_ids: list[uuid.UUID]) -> None:
        if len(shop_ids) > 20 or len(set(shop_ids)) != len(shop_ids):
            raise ValueError("Invalid shop collection")
        self.shop_ids = tuple(shop_ids)
        self._recent: dict[tuple[uuid.UUID, int], _Bucket] = {}
        self._dirty: dict[tuple[uuid.UUID, int], _Bucket] = {}
        self._horizon = Decimal(0)
        self.coverage_complete = True

    def _bucket(self, shop_id, index, revision):
        key = (shop_id, index)
        row = self._recent.get(key) or self._dirty.get(key)
        if row is None:
            row = _Bucket(shop_id, index, Decimal(index * 60), revision=revision)
            self._recent[key] = row
        return row

    def _changed(self, row, revision):
        row.revision = revision
        self._dirty[(row.shop_id, row.index)] = row

    def observe(
        self,
        timestamp: Decimal,
        *,
        facts: list[LiveCrossingFact],
        pending: list[LiveCrossingFact],
        interval,
        revision: int,
    ):
        if not timestamp.is_finite() or timestamp < self._horizon:
            raise ValueError("Non-monotonic bucket horizon")
        self._horizon = timestamp
        current = int(timestamp // 60)
        if interval is not None:
            start, end, continuous = interval
            if not Decimal(0) <= start <= end <= timestamp:
                raise ValueError("Invalid coverage interval")
            if not continuous and end > start:
                self.coverage_complete = False
            while start < end:
                index = int(start // 60)
                stop = min(end, Decimal((index + 1) * 60))
                for shop_id in self.shop_ids:
                    row = self._bucket(shop_id, index, revision)
                    row.end = max(row.end, stop)
                    if continuous:
                        row.observed += stop - start
                    else:
                        row.missing += stop - start
                    self._changed(row, revision)
                start = stop
        for shop_id in self.shop_ids:
            row = self._bucket(shop_id, current, revision)
            if row.end != timestamp:
                row.end = timestamp
                self._changed(row, revision)
        for fact in facts:
            if fact.shop_id not in self.shop_ids or fact.capture_timestamp_seconds > timestamp:
                raise ValueError("Invalid crossing context")
            row = self._bucket(fact.shop_id, int(fact.capture_timestamp_seconds // 60), revision)
            if fact.direction == "entry":
                row.entries += 1
            else:
                row.exits += 1
            self._changed(row, revision)
        pending_counts = Counter(
            (fact.shop_id, int(fact.capture_timestamp_seconds // 60)) for fact in pending
        )
        for key, row in self._recent.items():
            count = pending_counts.get(key, 0)
            is_open = row.index == current
            if row.pending != count or row.is_open != is_open:
                row.pending, row.is_open = count, is_open
                self._changed(row, revision)
        self._recent = {key: row for key, row in self._recent.items() if row.index >= current - 59}

    def snapshot(self):
        return [
            row.message()
            for _, row in sorted(
                self._recent.items(), key=lambda item: (str(item[0][0]), item[0][1])
            )
        ]

    def dirty_rows(self):
        return [row.message() for row in self._dirty.values()]

    def acknowledge(self):
        self._dirty.clear()

    def finish(self, *, revision: int):
        for row in self._recent.values():
            if row.pending or row.is_open:
                row.pending = 0
                row.is_open = False
                self._changed(row, revision)
