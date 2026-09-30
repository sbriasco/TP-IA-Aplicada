"""Zone, pass and front-zone dwell facts. Store enter and exit come from confirmed crossings."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from flowsight.scene.geometry import _point_in_polygon
from flowsight.vision.spatial import CrossingFact, ShopGeometry

ZoneRoleName = Literal["front", "interior", "window"]
EventKind = Literal[
    "zone_enter", "zone_exit", "store_pass", "store_enter", "store_exit", "dwell"
]


@dataclass(frozen=True)
class SceneEventFact:
    shop_id: uuid.UUID
    track_id: int
    kind: EventKind
    zone_role: ZoneRoleName | None
    frame_index: int
    duration_seconds: Decimal | None
    crossing: CrossingFact | None


class SceneEventRecorder:
    """One pass. A lost track does not close a dwell or a store exit."""

    def __init__(self, shops: Sequence[ShopGeometry], *, fps: float) -> None:
        self._shops = list(shops)
        self._fps = fps
        self._inside: dict[tuple[uuid.UUID, int, ZoneRoleName], bool] = {}
        self._front_enter: dict[tuple[uuid.UUID, int], int] = {}
        self._first_front: dict[tuple[uuid.UUID, int], int] = {}
        self._entered: set[tuple[uuid.UUID, int]] = set()
        self._events: list[SceneEventFact] = []

    def observe(
        self,
        frame_index: int,
        feet: Sequence[tuple[int, tuple[float, float]]],
        crossings: Sequence[CrossingFact],
    ) -> None:
        for shop in self._shops:
            zones = _zones(shop)
            for track_id, foot in feet:
                for role, polygon in zones:
                    inside = _point_in_polygon(foot, polygon)
                    key = (shop.shop_id, track_id, role)
                    was = self._inside.get(key, False)
                    if inside and not was:
                        self._emit(shop.shop_id, track_id, "zone_enter", role, frame_index, None)
                        if role == "front":
                            pair = (shop.shop_id, track_id)
                            self._front_enter[pair] = frame_index
                            self._first_front.setdefault(pair, frame_index)
                    elif was and not inside:
                        self._emit(shop.shop_id, track_id, "zone_exit", role, frame_index, None)
                        if role == "front":
                            self._close_dwell(shop.shop_id, track_id, frame_index)
                    self._inside[key] = inside
        self.accept_crossings(crossings)

    def accept_crossings(self, crossings: Sequence[CrossingFact]) -> None:
        for crossing in crossings:
            if crossing.disposition != "confirmed":
                continue
            kind: EventKind = "store_enter" if crossing.direction == "entry" else "store_exit"
            if kind == "store_enter":
                self._entered.add((crossing.shop_id, crossing.track_id))
            self._events.append(
                SceneEventFact(
                    shop_id=crossing.shop_id,
                    track_id=crossing.track_id,
                    kind=kind,
                    zone_role=None,
                    frame_index=crossing.frame_index,
                    duration_seconds=None,
                    crossing=crossing,
                )
            )

    def finish(self) -> list[SceneEventFact]:
        for (shop_id, track_id), frame_index in self._first_front.items():
            if (shop_id, track_id) in self._entered:
                continue
            self._emit(shop_id, track_id, "store_pass", None, frame_index, None)
        return list(self._events)

    def _close_dwell(self, shop_id: uuid.UUID, track_id: int, frame_index: int) -> None:
        entered = self._front_enter.pop((shop_id, track_id), None)
        if entered is None:
            return
        duration = (
            (Decimal(frame_index) - Decimal(entered)) / Decimal(str(self._fps))
        ).quantize(Decimal("0.000001"))
        self._emit(shop_id, track_id, "dwell", "front", frame_index, duration)

    def _emit(
        self,
        shop_id: uuid.UUID,
        track_id: int,
        kind: EventKind,
        zone_role: ZoneRoleName | None,
        frame_index: int,
        duration: Decimal | None,
    ) -> None:
        self._events.append(
            SceneEventFact(
                shop_id=shop_id,
                track_id=track_id,
                kind=kind,
                zone_role=zone_role,
                frame_index=frame_index,
                duration_seconds=duration,
                crossing=None,
            )
        )


def _zones(
    shop: ShopGeometry,
) -> list[tuple[ZoneRoleName, Sequence[Sequence[float]]]]:
    zones: list[tuple[ZoneRoleName, Sequence[Sequence[float]]]] = []
    if shop.front_polygon:
        zones.append(("front", shop.front_polygon))
    if shop.interior_polygon:
        zones.append(("interior", shop.interior_polygon))
    if shop.window_polygon:
        zones.append(("window", shop.window_polygon))
    return zones
