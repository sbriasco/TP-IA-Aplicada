"""Video counters fed by live capture time.

One second of capture is one second for metrics, the funnel, groups and
possible purchase. A gap above one second drops the open visit.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from flowsight.scene.geometry import _point_in_polygon
from flowsight.vision.detector import BagBox, Detection
from flowsight.vision.events import SceneEventRecorder
from flowsight.vision.funnel import build_funnel
from flowsight.vision.live_spatial import LiveCrossingFact
from flowsight.vision.metrics import build_shop_metrics
from flowsight.vision.possible_purchase import PossiblePurchaseDraft, PossiblePurchaseRecorder
from flowsight.vision.spatial import CrossingFact, ShopGeometry
from flowsight.vision.visit_patterns import (
    ConfiguredArea,
    VisitPatternDraft,
    VisitPatternRecorder,
)

CAPTURE_FPS = 1000


def capture_frame(seconds: Decimal) -> int:
    return int((seconds * Decimal(CAPTURE_FPS)).to_integral_value(rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True)
class LiveFileShopSummary:
    traffic_total: int | None
    store_pass: int | None
    entries: int | None
    exits: int | None
    entry_rate: Decimal | None
    dwell_mean_seconds: Decimal | None
    observed_pass: int | None
    exposure: int | None
    stop: int | None
    attention: int | None
    linked_entry: int | None
    group_count: int
    possible_purchase_count: int


class LiveFileAnalysis:
    """One live job. The recorders stay open until finish()."""

    def __init__(self, shops: Sequence[ShopGeometry], *, width: int, height: int) -> None:
        self._shops = list(shops)
        self._width = width
        self._height = height
        self._fps = float(CAPTURE_FPS)
        self.events = SceneEventRecorder(shops, fps=self._fps)
        self.patterns = VisitPatternRecorder(
            _areas(shops), fps=self._fps, width=width, height=height
        )
        self.purchases = PossiblePurchaseRecorder(fps=self._fps)
        self._last_frame: int | None = None
        self._duration = Decimal("0")
        self._occupancy = {shop.shop_id: 0 for shop in shops}

    def observe(
        self,
        seconds: Decimal,
        feet: Sequence[tuple[int, tuple[float, float]]],
        detections: list[Detection],
        bags: list[BagBox],
        crossings: Sequence[LiveCrossingFact],
    ) -> None:
        frame = capture_frame(seconds)
        # A gap just over one second is dropped on a synthetic frame one
        # millisecond later. Rounding can place the next real frame on or
        # before that index; keep the clock moving forward.
        if self._last_frame is not None and frame <= self._last_frame:
            frame = self._last_frame + 1
        self._duration = max(self._duration, seconds)
        self.events.observe(frame, feet, _crossings(crossings))
        self.patterns.observe(frame, feet)
        self.purchases.observe(frame, detections, bags)
        self._last_frame = frame
        self._occupancy = {
            shop.shop_id: sum(
                1
                for _track, foot in feet
                if shop.front_polygon is not None and _point_in_polygon(foot, shop.front_polygon)
            )
            for shop in self._shops
        }

    def discontinue(self) -> None:
        """Drop open visits. Confirmed groups stay reserved for this job."""

        if self._last_frame is None:
            return
        frame = self._last_frame + CAPTURE_FPS + 1
        self.events.observe(frame, [], [])
        self.patterns.observe(frame, [])
        self.purchases.observe(frame, [], [])
        self._last_frame = frame
        self._occupancy = {shop.shop_id: 0 for shop in self._shops}

    def preview(
        self, counts: Mapping[uuid.UUID, tuple[int, int]]
    ) -> dict[uuid.UUID, LiveFileShopSummary]:
        events = self.events.draft_events()
        patterns = deepcopy(self.patterns).finish()
        purchases = deepcopy(self.purchases).finish()
        return {
            shop.shop_id: _summary(
                self._metrics(shop, events, counts)[0],
                build_funnel(
                    events,
                    shop_id=shop.shop_id,
                    window_configured=shop.window_polygon is not None,
                    fps=self._fps,
                ),
                patterns,
                purchases,
            )
            for shop in self._shops
        }

    def finish(
        self, counts: Mapping[uuid.UUID, tuple[int, int]]
    ):
        events = self.events.finish()
        metrics = {}
        buckets = {}
        for shop in self._shops:
            rows, shop_buckets = self._metrics(shop, events, counts)
            metrics[shop.shop_id] = rows
            buckets[shop.shop_id] = shop_buckets
        return events, self.patterns.finish(), self.purchases.finish(), metrics, buckets

    def _metrics(self, shop: ShopGeometry, events, counts: Mapping[uuid.UUID, tuple[int, int]]):
        entries, exits = counts.get(shop.shop_id, (0, 0))
        rows, buckets, _peak = build_shop_metrics(
            events,
            shop_id=shop.shop_id,
            entries=entries,
            exits=exits,
            visible_occupancy=self._occupancy.get(shop.shop_id, 0),
            fps=self._fps,
            duration_seconds=float(self._duration),
            front_configured=shop.front_polygon is not None,
            line_configured=shop.line_start is not None and shop.line_end is not None,
        )
        return rows, buckets


def _areas(shops: Sequence[ShopGeometry]) -> list[ConfiguredArea]:
    areas: list[ConfiguredArea] = []
    for shop in shops:
        if shop.front_polygon:
            areas.append(ConfiguredArea(shop.shop_id, "front", shop.front_polygon))
        if shop.interior_polygon:
            areas.append(ConfiguredArea(shop.shop_id, "interior", shop.interior_polygon))
        if shop.window_polygon:
            areas.append(ConfiguredArea(shop.shop_id, "window", shop.window_polygon))
    return areas


def _crossings(facts: Sequence[LiveCrossingFact]) -> list[CrossingFact]:
    return [
        CrossingFact(
            shop_id=fact.shop_id,
            track_id=fact.track_id,
            frame_index=capture_frame(fact.confirmed_at_capture_seconds),
            direction=fact.direction,
            disposition="confirmed",
            foot=fact.foot,
        )
        for fact in facts
    ]


def _summary(metrics, funnel, patterns: VisitPatternDraft, purchases: PossiblePurchaseDraft):
    by_code = {row.code: row for row in metrics}
    stages = {stage.stage: stage.count for stage in funnel.stages}

    def number(code: str) -> int | None:
        row = by_code[code]
        if row.availability != "available" or row.value is None:
            return None
        return int(row.value)

    def decimal(code: str) -> Decimal | None:
        row = by_code[code]
        if row.availability != "available":
            return None
        return row.value

    return LiveFileShopSummary(
        traffic_total=number("traffic_total"),
        store_pass=number("store_pass"),
        entries=number("entries"),
        exits=number("exits"),
        entry_rate=decimal("entry_rate"),
        dwell_mean_seconds=decimal("dwell_mean_seconds"),
        observed_pass=stages["observed_pass"],
        exposure=stages["exposure"],
        stop=stages["stop"],
        attention=stages["attention"],
        linked_entry=stages["linked_entry"],
        group_count=patterns.group_count,
        possible_purchase_count=purchases.visit_count,
    )
