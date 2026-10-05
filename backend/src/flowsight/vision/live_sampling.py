"""Reservoir of normalized positions: bounded memory and bounded durable slots."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from random import Random


@dataclass(frozen=True)
class PositionSample:
    segment_index: int
    track_id: int
    sequence: int
    timestamp_s: Decimal
    foot: tuple[float, float]


@dataclass(frozen=True)
class PositionSlotChange:
    slot_index: int
    sample: PositionSample


class LivePositionSampler:
    def __init__(
        self,
        *,
        capacity: int = 20000,
        rng: Random | None = None,
        max_tracks: int = 2048,
    ) -> None:
        if not 1 <= capacity <= 20000 or not 1 <= max_tracks <= 2048:
            raise ValueError("Invalid sample/track capacity")
        self.capacity = capacity
        self.max_tracks = max_tracks
        self._rng = rng if rng is not None else Random()
        self.samples: dict[int, PositionSample] = {}
        self._dirty: dict[int, PositionSlotChange] = {}
        self._tracks: dict[tuple[int, int], tuple[Decimal, int]] = {}
        self.candidates_seen = 0
        self.evicted_tracks = 0
        self._horizon = Decimal(0)

    @property
    def tracked_count(self) -> int:
        return len(self._tracks)

    def observe(
        self,
        *,
        segment_index: int,
        track_id: int,
        sequence: int,
        timestamp_s: Decimal,
        foot: tuple[float, float],
    ) -> list[PositionSlotChange]:
        if (
            not timestamp_s.is_finite()
            or timestamp_s < self._horizon
            or segment_index < 0
            or sequence < 0
            or any(not math.isfinite(value) or not 0 <= value <= 1 for value in foot)
        ):
            return []
        self._horizon = timestamp_s
        for key, (seen_at, _) in list(self._tracks.items()):
            if timestamp_s - seen_at >= 1:
                del self._tracks[key]
        key = (segment_index, track_id)
        previous = self._tracks.get(key)
        second = int(timestamp_s)
        if previous is not None and previous[1] == second:
            self._tracks[key] = (timestamp_s, second)
            return []
        if previous is None and len(self._tracks) >= self.max_tracks:
            oldest = min(self._tracks, key=lambda item: self._tracks[item][0])
            del self._tracks[oldest]
            self.evicted_tracks += 1
        self._tracks[key] = (timestamp_s, second)
        self.candidates_seen += 1
        slot = (
            self.candidates_seen - 1
            if self.candidates_seen <= self.capacity
            else self._rng.randrange(self.candidates_seen)
        )
        if slot >= self.capacity:
            return []
        sample = PositionSample(segment_index, track_id, sequence, timestamp_s, foot)
        self.samples[slot] = sample
        change = PositionSlotChange(slot, sample)
        self._dirty[slot] = change
        return [change]

    def drain_changes(self) -> list[PositionSlotChange]:
        changes = list(self._dirty.values())
        self._dirty.clear()
        return changes

    def discontinue(self) -> None:
        """Forget continuity only; preserve positions and reservoir distribution."""
        self._tracks.clear()
