"""Entries, exits and visible occupancy from normalized feet.

Uses the A/B convention of ``flowsight.scene.geometry.side_of_line``. The interior
zone is accepted on the shop so callers can pass the scene as stored, and it is
never counted.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from flowsight.scene.geometry import _point_in_polygon, segments_intersect, side_of_line
from flowsight.vision.detector import Detection

OSCILLATION_MAX_FRAMES = 10

Direction = Literal["entry", "exit"]
Disposition = Literal["confirmed", "oscillation"]


@dataclass(frozen=True)
class ShopGeometry:
    shop_id: uuid.UUID
    shop_name: str
    front_polygon: Sequence[Sequence[float]] | None
    interior_polygon: Sequence[Sequence[float]] | None
    line_start: tuple[float, float] | None
    line_end: tuple[float, float] | None
    entry_direction: Literal["a_to_b", "b_to_a"] | None
    window_polygon: Sequence[Sequence[float]] | None = None


@dataclass(frozen=True)
class CrossingFact:
    shop_id: uuid.UUID
    track_id: int
    frame_index: int
    direction: Direction
    disposition: Disposition
    foot: tuple[float, float]


@dataclass(frozen=True)
class ShopCounts:
    shop_id: uuid.UUID
    shop_name: str
    entries: int
    exits: int
    visible_occupancy: int


@dataclass
class _Pending:
    shop_id: uuid.UUID
    track_id: int
    frame_index: int
    direction: Direction
    foot: tuple[float, float]


@dataclass
class _Track:
    frame_index: int
    foot: tuple[float, float]
    pending: _Pending | None = None


def normalized_foot(detection: Detection, width: int, height: int) -> tuple[float, float]:
    """Bottom-center of the box, divided by the frame size. Same space as the scene."""

    x, y = detection.foot
    return (x / width, y / height)


class SpatialCounter:
    """One pass over a video. State is per shop and per track_id; ids do not inherit."""

    def __init__(self, shops: Sequence[ShopGeometry]) -> None:
        self._shops = list(shops)
        self._tracks: dict[tuple[uuid.UUID, int], _Track] = {}
        self._entries = {shop.shop_id: 0 for shop in self._shops}
        self._exits = {shop.shop_id: 0 for shop in self._shops}
        self._occupancy = {shop.shop_id: 0 for shop in self._shops}

    def observe(
        self,
        frame_index: int,
        detections: Sequence[Detection],
        *,
        width: int,
        height: int,
    ) -> list[CrossingFact]:
        feet = [
            (detection.track_id, normalized_foot(detection, width, height))
            for detection in detections
        ]
        facts: list[CrossingFact] = []
        for shop in self._shops:
            for track_id, foot in feet:
                facts.extend(self._cross(shop, track_id, frame_index, foot))
            self._occupancy[shop.shop_id] = _visible(shop, feet)
        return facts

    def finish(self) -> list[CrossingFact]:
        """Confirm crossings that never met an opposite one inside the window."""

        facts: list[CrossingFact] = []
        for track in self._tracks.values():
            if track.pending is not None:
                facts.append(self._confirm(track.pending))
                track.pending = None
        return facts

    def counts(self) -> list[ShopCounts]:
        return [
            ShopCounts(
                shop_id=shop.shop_id,
                shop_name=shop.shop_name,
                entries=self._entries[shop.shop_id],
                exits=self._exits[shop.shop_id],
                visible_occupancy=self._occupancy[shop.shop_id],
            )
            for shop in self._shops
        ]

    def measure_payloads(self, *, partial: bool) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for count in self.counts():
            for code, value in (
                ("entries", count.entries),
                ("exits", count.exits),
                ("visible_occupancy", count.visible_occupancy),
            ):
                payloads.append(
                    {
                        "shop_id": str(count.shop_id),
                        "code": code,
                        "value": value,
                        "availability": "available",
                        "partial": partial,
                    }
                )
        return payloads

    def _cross(
        self,
        shop: ShopGeometry,
        track_id: int,
        frame_index: int,
        foot: tuple[float, float],
    ) -> list[CrossingFact]:
        key = (shop.shop_id, track_id)
        previous = self._tracks.get(key)
        pending = previous.pending if previous is not None else None
        facts: list[CrossingFact] = []
        line_start = shop.line_start
        line_end = shop.line_end
        if (
            previous is not None
            and line_start is not None
            and line_end is not None
            and shop.entry_direction is not None
        ):
            sense = _crossing_sense(previous.foot, foot, line_start, line_end)
            if sense is not None:
                direction: Direction = "entry" if sense == shop.entry_direction else "exit"
                candidate = _Pending(shop.shop_id, track_id, frame_index, direction, foot)
                if pending is None:
                    pending = candidate
                else:
                    delta = frame_index - pending.frame_index
                    opposite = pending.direction != direction
                    if 0 < delta <= OSCILLATION_MAX_FRAMES and opposite:
                        facts.append(_fact(pending, "oscillation"))
                        facts.append(_fact(candidate, "oscillation"))
                        pending = None
                    else:
                        facts.append(self._confirm(pending))
                        pending = candidate
        self._tracks[key] = _Track(frame_index, foot, pending)
        return facts

    def _confirm(self, pending: _Pending) -> CrossingFact:
        if pending.direction == "entry":
            self._entries[pending.shop_id] += 1
        else:
            self._exits[pending.shop_id] += 1
        return _fact(pending, "confirmed")


def _crossing_sense(
    previous: tuple[float, float],
    current: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> Literal["a_to_b", "b_to_a"] | None:
    if not segments_intersect(previous, current, start, end):
        return None
    previous_side = side_of_line(start, end, previous)
    current_side = side_of_line(start, end, current)
    if previous_side == "A" and current_side == "B":
        return "a_to_b"
    if previous_side == "B" and current_side == "A":
        return "b_to_a"
    return None


def _visible(shop: ShopGeometry, feet: Sequence[tuple[int, tuple[float, float]]]) -> int:
    if not shop.front_polygon:
        return 0
    return len(
        {
            track_id
            for track_id, foot in feet
            if _point_in_polygon(foot, shop.front_polygon)
        }
    )


def _fact(pending: _Pending, disposition: Disposition) -> CrossingFact:
    return CrossingFact(
        shop_id=pending.shop_id,
        track_id=pending.track_id,
        frame_index=pending.frame_index,
        direction=pending.direction,
        disposition=disposition,
        foot=pending.foot,
    )
