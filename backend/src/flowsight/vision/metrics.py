"""Eight shop metrics from scene facts and the three official counts."""

from __future__ import annotations

import math
import statistics
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from flowsight.vision.events import SceneEventFact

_SIX = Decimal("0.000001")
_LABELS = {
    "traffic_total": "visit_estimate",
    "visible_occupancy": "visible",
    "dwell_mean_seconds": "observable",
    "dwell_median_seconds": "observable",
}


@dataclass(frozen=True)
class MetricValue:
    code: str
    value: Decimal | None
    availability: str
    label: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class TrafficBucketValue:
    bucket_index: int
    start_seconds: Decimal
    track_count: int


def build_shop_metrics(
    events: Sequence[SceneEventFact],
    *,
    shop_id: uuid.UUID,
    entries: int,
    exits: int,
    visible_occupancy: int,
    fps: float,
    duration_seconds: float,
    front_configured: bool,
    line_configured: bool = True,
) -> tuple[list[MetricValue], list[TrafficBucketValue], TrafficBucketValue]:
    shop_events = [event for event in events if event.shop_id == shop_id]
    buckets = _buckets(
        shop_events, fps=fps, duration_seconds=duration_seconds, front=front_configured
    )
    peak = min(buckets, key=lambda bucket: (-bucket.track_count, bucket.bucket_index))
    traffic = sum(bucket.track_count for bucket in buckets)
    passes = sum(1 for event in shop_events if event.kind == "store_pass")
    dwells = [
        event.duration_seconds
        for event in shop_events
        if (
            event.kind == "dwell"
            and event.zone_role == "front"
            and event.duration_seconds is not None
        )
    ]
    rows = [
        _count("traffic_total", traffic if front_configured else None, "scene_element_missing"),
        _count("store_pass", passes if front_configured else None, "scene_element_missing"),
        _count("entries", entries if line_configured else None, "scene_element_missing"),
        _count("exits", exits if line_configured else None, "scene_element_missing"),
        _rate(entries, passes, front_configured and line_configured),
        _dwell("dwell_mean_seconds", dwells, front_configured, statistics.fmean),
        _dwell("dwell_median_seconds", dwells, front_configured, statistics.median),
        _count(
            "visible_occupancy",
            visible_occupancy if front_configured else None,
            "scene_element_missing",
        ),
    ]
    return rows, buckets, peak


def _buckets(
    events: Sequence[SceneEventFact],
    *,
    fps: float,
    duration_seconds: float,
    front: bool,
) -> list[TrafficBucketValue]:
    count = 1 if duration_seconds < 60 else max(1, math.ceil(duration_seconds / 60))
    totals = [0 for _ in range(count)]
    if front:
        first: dict[int, int] = {}
        for event in events:
            if event.kind == "zone_enter" and event.zone_role == "front":
                first.setdefault(event.track_id, event.frame_index)
        for frame_index in first.values():
            instant = float(Decimal(frame_index) / Decimal(str(fps)))
            index = 0 if duration_seconds < 60 else min(count - 1, int(instant // 60))
            totals[index] += 1
    return [
        TrafficBucketValue(
            bucket_index=index,
            start_seconds=(Decimal(index) * Decimal(60)).quantize(_SIX),
            track_count=total,
        )
        for index, total in enumerate(totals)
    ]


def _count(code: str, value: int | None, missing_reason: str | None) -> MetricValue:
    if value is None:
        return _unavailable(code, missing_reason or "scene_element_missing")
    return MetricValue(
        code, Decimal(value).quantize(_SIX), "available", _LABELS.get(code, "none"), None
    )


def _rate(entries: int, passes: int, ready: bool) -> MetricValue:
    if not ready:
        return _unavailable("entry_rate", "scene_element_missing")
    if passes == 0:
        return _unavailable("entry_rate", "no_passes")
    value = (Decimal(entries) / Decimal(passes)).quantize(_SIX)
    return MetricValue("entry_rate", value, "available", "none", None)


def _dwell(
    code: str,
    dwells: Sequence[Decimal],
    front: bool,
    reducer,
) -> MetricValue:
    if not front:
        return _unavailable(code, "scene_element_missing")
    if not dwells:
        return _unavailable(code, "no_closed_dwells")
    value = Decimal(str(reducer([float(item) for item in dwells]))).quantize(_SIX)
    return MetricValue(code, value, "available", "observable", None)


def _unavailable(code: str, reason: str) -> MetricValue:
    return MetricValue(code, None, "unavailable", _LABELS.get(code, "none"), reason)
