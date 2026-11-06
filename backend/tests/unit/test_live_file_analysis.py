"""Live capture time drives the same file counters."""

from __future__ import annotations

import uuid
from decimal import Decimal

from flowsight.vision.live_file_analysis import LiveFileAnalysis
from flowsight.vision.spatial import ShopGeometry

SHOP = uuid.uuid4()
FRONT = ((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5))
WINDOW = ((0.0, 0.0), (0.25, 0.0), (0.25, 0.25), (0.0, 0.25))
INSIDE = (0.1, 0.1)
OUTSIDE = (0.9, 0.9)


def _shop() -> ShopGeometry:
    return ShopGeometry(
        SHOP,
        "Zona",
        FRONT,
        None,
        (0.0, 0.2),
        (0.5, 0.2),
        "a_to_b",
        WINDOW,
    )


def _analysis() -> LiveFileAnalysis:
    return LiveFileAnalysis([_shop()], width=100, height=100)


def test_a_front_visit_counts_only_after_the_person_leaves() -> None:
    analysis = _analysis()
    for seconds in (Decimal("0"), Decimal("1"), Decimal("2")):
        analysis.observe(seconds, [(1, INSIDE)], [], [], [])
    while_inside = analysis.preview({})[SHOP]
    assert while_inside.store_pass == 0
    assert while_inside.entries == 0
    assert while_inside.attention == 0
    analysis.observe(Decimal("3"), [(1, OUTSIDE)], [], [], [])
    closed = analysis.preview({})[SHOP]
    assert closed.store_pass == 1
    assert closed.observed_pass == 1
    assert closed.exposure == 1
    assert closed.stop == 1
    assert closed.attention == 1
    _events, _patterns, _purchases, metrics, _buckets = analysis.finish({})
    by_code = {row.code: row for row in metrics[SHOP]}
    assert by_code["store_pass"].value == Decimal("1")
    assert by_code["traffic_total"].value == Decimal("1")


def test_a_gap_drops_the_open_visit_and_does_not_extend_the_group() -> None:
    analysis = _analysis()
    for seconds in (Decimal("0"), Decimal("1"), Decimal("2")):
        analysis.observe(
            seconds, [(1, INSIDE), (2, (0.16, 0.1))], [], [], []
        )
    analysis.discontinue()
    open_dwell = [
        event
        for event in analysis.events.draft_events()
        if event.kind == "dwell"
    ]
    assert open_dwell == []
    analysis.observe(Decimal("5"), [(1, INSIDE), (2, (0.16, 0.1))], [], [], [])
    analysis.observe(Decimal("7"), [(1, INSIDE), (2, (0.16, 0.1))], [], [], [])
    _events, patterns, _purchases, _metrics, _buckets = analysis.finish({})
    assert patterns.group_count == 1


def test_a_gap_just_over_one_second_keeps_the_clock_moving_forward() -> None:
    analysis = _analysis()
    analysis.observe(Decimal("0"), [(1, INSIDE)], [], [], [])
    analysis.discontinue()
    analysis.observe(Decimal("1.0004"), [(1, INSIDE)], [], [], [])
    events, patterns, _purchases, _metrics, _buckets = analysis.finish({})
    assert [event.kind for event in events if event.kind == "dwell"] == []
    assert patterns.group_count == 0
