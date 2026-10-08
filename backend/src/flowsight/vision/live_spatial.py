"""Crossings with capture-time debounce, bounded continuity and no video assumptions."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from flowsight.capture.contracts import CapturedFrame
from flowsight.vision.detector import Detection
from flowsight.vision.spatial import (
    Direction,
    ShopGeometry,
    Side,
    crossing_sense,
    foot_side,
    normalized_foot,
)


@dataclass(frozen=True)
class LiveCrossingFact:
    shop_id: uuid.UUID
    track_id: int
    segment_index: int
    candidate_sequence: int
    capture_sequence: int
    capture_timestamp_seconds: Decimal
    confirmed_at_capture_seconds: Decimal
    direction: Direction
    foot: tuple[float, float]


@dataclass(frozen=True)
class LiveShopCounts:
    shop_id: uuid.UUID
    shop_name: str
    entries: int
    exits: int


@dataclass
class _Track:
    timestamp: Decimal
    foot: tuple[float, float]
    side: Side | None
    pending: LiveCrossingFact | None = None


class LiveSpatialCounter:
    def __init__(
        self,
        shops: Sequence[ShopGeometry],
        *,
        window_s: Decimal = Decimal(1) / 3,
        gap_s: Decimal = Decimal(1),
        max_tracks: int = 2048,
    ) -> None:
        if window_s <= 0 or gap_s <= window_s or not 1 <= max_tracks <= 2048:
            raise ValueError("Invalid crossing policy")
        self._shops = list(shops)
        self.window_s = window_s
        self.gap_s = gap_s
        self.max_tracks = max_tracks
        self._tracks: dict[tuple[uuid.UUID, int], _Track] = {}
        self._counts = {shop.shop_id: [0, 0] for shop in shops}
        self._horizon = Decimal(-1)
        self._sequence = -1
        self._segment = -1
        self._candidate_sequence = 0
        self.discarded_crossings = 0
        self.evicted_tracks = 0

    @property
    def pending_count(self) -> int:
        return sum(track.pending is not None for track in self._tracks.values())

    @property
    def pending_candidates(self) -> list[LiveCrossingFact]:
        return [track.pending for track in self._tracks.values() if track.pending is not None]

    @property
    def tracked_count(self) -> int:
        return len(self._tracks)

    def counts(self) -> list[LiveShopCounts]:
        return [
            LiveShopCounts(shop.shop_id, shop.shop_name, *self._counts[shop.shop_id])
            for shop in self._shops
        ]

    def observe(
        self,
        frame: CapturedFrame,
        detections: Sequence[Detection],
    ) -> list[LiveCrossingFact]:
        timestamp = frame.timestamp_seconds
        if (
            not timestamp.is_finite()
            or timestamp < 0
            or timestamp < self._horizon
            or frame.sequence <= self._sequence
        ):
            return []
        if (
            frame.segment_index != self._segment
            or self._horizon >= 0
            and timestamp - self._horizon > self.gap_s
        ):
            self.discontinue(timestamp)
        self._segment = frame.segment_index
        self._sequence = frame.sequence
        self._horizon = timestamp
        feet = {
            detection.track_id: normalized_foot(detection, frame.width, frame.height)
            for detection in detections
        }
        feet = {
            track: foot
            for track, foot in feet.items()
            if all(math.isfinite(value) and 0 <= value <= 1 for value in foot)
        }
        # A lost track cannot confirm a pending crossing using another person's observations.
        for key, previous in list(self._tracks.items()):
            if timestamp - previous.timestamp > self.gap_s or key[1] not in feet:
                self.discarded_crossings += int(previous.pending is not None)
                del self._tracks[key]
        facts = self.advance(timestamp)
        for shop in self._shops:
            if shop.line_start is None or shop.line_end is None or shop.entry_direction is None:
                continue
            for track_id, foot in feet.items():
                key = (shop.shop_id, track_id)
                previous = self._tracks.get(key)
                pending = previous.pending if previous else None
                side = foot_side(shop.line_start, shop.line_end, foot)
                if previous is not None and side is None:
                    self._tracks[key] = _Track(timestamp, previous.foot, previous.side, pending)
                    continue
                sense = (
                    crossing_sense(
                        previous.side, previous.foot, side, foot, shop.line_start, shop.line_end
                    )
                    if previous is not None
                    else None
                )
                if sense is not None:
                    direction: Direction = "entry" if sense == shop.entry_direction else "exit"
                    self._candidate_sequence += 1
                    candidate = LiveCrossingFact(
                        shop.shop_id,
                        track_id,
                        self._segment,
                        self._candidate_sequence,
                        frame.sequence,
                        timestamp,
                        timestamp,
                        direction,
                        foot,
                    )
                    if pending is not None and pending.direction != direction:
                        self.discarded_crossings += 2
                        pending = None
                    else:
                        pending = candidate
                if previous is None and len(self._tracks) >= self.max_tracks:
                    oldest = min(self._tracks, key=lambda item: self._tracks[item].timestamp)
                    evicted = self._tracks.pop(oldest)
                    self.discarded_crossings += int(evicted.pending is not None)
                    self.evicted_tracks += 1
                self._tracks[key] = _Track(timestamp, foot, side, pending)
        return facts

    def advance(self, timestamp_s: Decimal) -> list[LiveCrossingFact]:
        """Only advance to an already observed horizon; a timer never invents frames."""
        timestamp = min(timestamp_s, self._horizon)
        facts: list[LiveCrossingFact] = []
        for track in self._tracks.values():
            pending = track.pending
            if (
                pending is not None
                and timestamp - pending.capture_timestamp_seconds > self.window_s
            ):
                fact = replace(
                    pending, confirmed_at_capture_seconds=timestamp, capture_sequence=self._sequence
                )
                self._counts[fact.shop_id][0 if fact.direction == "entry" else 1] += 1
                facts.append(fact)
                track.pending = None
        return facts

    def discontinue(self, timestamp_s: Decimal) -> None:
        del timestamp_s
        self.discarded_crossings += self.pending_count
        self._tracks.clear()
