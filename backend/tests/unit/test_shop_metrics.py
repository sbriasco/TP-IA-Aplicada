"""The eight metrics from facts and the official integers, without a database."""

from __future__ import annotations

import uuid
from decimal import Decimal

from flowsight.vision.events import SceneEventFact
from flowsight.vision.metrics import build_shop_metrics

SHOP = uuid.uuid4()


def _event(
    kind: str,
    track_id: int,
    frame_index: int,
    zone_role: str | None = None,
    duration: str | None = None,
) -> SceneEventFact:
    return SceneEventFact(
        shop_id=SHOP,
        track_id=track_id,
        kind=kind,  # type: ignore[arg-type]
        zone_role=zone_role,  # type: ignore[arg-type]
        frame_index=frame_index,
        duration_seconds=None if duration is None else Decimal(duration),
        crossing=None,
    )


def _by_code(rows):
    return {row.code: row for row in rows}


def test_hand_case_keeps_official_integers_and_splits_traffic_once() -> None:
    events = [
        _event("zone_enter", 1, 0, "front"),
        _event("store_enter", 1, 11),
        _event("zone_enter", 2, 70, "front"),
        _event("store_pass", 2, 70),
        _event("zone_enter", 3, 0, "front"),
        _event("dwell", 3, 4, "front", "4"),
        _event("store_pass", 3, 0),
        _event("zone_enter", 4, 0, "front"),
        _event("store_pass", 4, 0),
        _event("zone_enter", 5, 0, "interior"),
    ]
    rows, flow, peak = build_shop_metrics(
        events,
        shop_id=SHOP,
        entries=9,
        exits=4,
        visible_occupancy=2,
        fps=1,
        duration_seconds=120,
        front_configured=True,
    )
    metrics = _by_code(rows)
    assert metrics["entries"].value == Decimal("9.000000")
    assert metrics["exits"].value == Decimal("4.000000")
    assert metrics["visible_occupancy"].value == Decimal("2.000000")
    assert metrics["visible_occupancy"].label == "visible"
    assert metrics["traffic_total"].value == Decimal("4.000000")
    assert metrics["traffic_total"].label == "visit_estimate"
    assert metrics["store_pass"].value == Decimal("3.000000")
    assert [bucket.track_count for bucket in flow] == [3, 1]
    assert sum(bucket.track_count for bucket in flow) == 4
    assert peak.bucket_index == 0
    assert metrics["entry_rate"].value == (Decimal(9) / Decimal(3)).quantize(Decimal("0.000001"))
    assert metrics["dwell_mean_seconds"].value == Decimal("4.000000")
    assert metrics["dwell_median_seconds"].label == "observable"


def test_peak_tie_uses_the_earliest_bucket_and_a_short_video_is_one_bucket() -> None:
    events = [
        _event("zone_enter", 1, 0, "front"),
        _event("zone_enter", 2, 70, "front"),
    ]
    _rows, flow, peak = build_shop_metrics(
        events,
        shop_id=SHOP,
        entries=0,
        exits=0,
        visible_occupancy=0,
        fps=1,
        duration_seconds=120,
        front_configured=True,
    )
    assert [bucket.track_count for bucket in flow] == [1, 1]
    assert peak.bucket_index == 0

    _rows, short, _peak = build_shop_metrics(
        events,
        shop_id=SHOP,
        entries=0,
        exits=0,
        visible_occupancy=0,
        fps=1,
        duration_seconds=30,
        front_configured=True,
    )
    assert len(short) == 1
    assert short[0].track_count == 2


def test_missing_passes_or_dwells_are_unavailable() -> None:
    rows, _flow, _peak = build_shop_metrics(
        [],
        shop_id=SHOP,
        entries=1,
        exits=0,
        visible_occupancy=0,
        fps=1,
        duration_seconds=10,
        front_configured=True,
    )
    metrics = _by_code(rows)
    assert metrics["entry_rate"].availability == "unavailable"
    assert metrics["entry_rate"].unavailable_reason == "no_passes"
    assert metrics["entry_rate"].value is None
    assert metrics["dwell_mean_seconds"].unavailable_reason == "no_closed_dwells"
    assert metrics["dwell_median_seconds"].unavailable_reason == "no_closed_dwells"


def test_missing_front_or_line_is_unavailable_instead_of_zero() -> None:
    rows, _flow, _peak = build_shop_metrics(
        [],
        shop_id=SHOP,
        entries=0,
        exits=0,
        visible_occupancy=0,
        fps=1,
        duration_seconds=10,
        front_configured=False,
        line_configured=False,
    )
    metrics = _by_code(rows)
    for code in (
        "traffic_total",
        "store_pass",
        "entries",
        "exits",
        "entry_rate",
        "visible_occupancy",
        "dwell_mean_seconds",
    ):
        assert metrics[code].availability == "unavailable"
        assert metrics[code].unavailable_reason == "scene_element_missing"
        assert metrics[code].value is None
