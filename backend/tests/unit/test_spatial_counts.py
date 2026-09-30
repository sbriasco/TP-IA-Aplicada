"""Entries, exits and visible occupancy from feet, without a database."""

from __future__ import annotations

import uuid

from flowsight.vision.detector import Detection
from flowsight.vision.spatial import ShopGeometry, SpatialCounter

WIDTH = 100
HEIGHT = 100
LINE = ((0.0, 0.5), (1.0, 0.5))
FRONT = ((0.0, 0.6), (1.0, 0.6), (1.0, 1.0), (0.0, 1.0))
INTERIOR = ((0.0, 0.0), (1.0, 0.0), (1.0, 0.4), (0.0, 0.4))


def _shop(entry_direction: str = "a_to_b") -> ShopGeometry:
    return ShopGeometry(
        shop_id=uuid.uuid4(),
        shop_name="Local",
        front_polygon=FRONT,
        interior_polygon=INTERIOR,
        line_start=LINE[0],
        line_end=LINE[1],
        entry_direction=entry_direction,
    )


def _detection(track_id: int, foot_x: float, foot_y: float) -> Detection:
    return Detection(
        track_id=track_id,
        bbox=(foot_x - 10, foot_y - 20, foot_x + 10, foot_y),
    )


def _observe(counter: SpatialCounter, frame_index: int, *detections: Detection) -> None:
    counter.observe(frame_index, list(detections), width=WIDTH, height=HEIGHT)


def test_configured_entry_sense_counts_entries_and_the_opposite_counts_exits() -> None:
    a_to_b = SpatialCounter([_shop("a_to_b")])
    _observe(a_to_b, 0, _detection(1, 50, 80))
    _observe(a_to_b, 1, _detection(1, 50, 20))
    a_to_b.finish()

    assert a_to_b.counts()[0].entries == 1
    assert a_to_b.counts()[0].exits == 0

    b_to_a = SpatialCounter([_shop("b_to_a")])
    _observe(b_to_a, 0, _detection(1, 50, 80))
    _observe(b_to_a, 1, _detection(1, 50, 20))
    b_to_a.finish()

    assert b_to_a.counts()[0].entries == 0
    assert b_to_a.counts()[0].exits == 1


def test_opposite_crossings_within_ten_frames_are_oscillation() -> None:
    counter = SpatialCounter([_shop()])
    _observe(counter, 0, _detection(1, 50, 80))
    first = counter.observe(1, [_detection(1, 50, 20)], width=WIDTH, height=HEIGHT)
    second = counter.observe(11, [_detection(1, 50, 80)], width=WIDTH, height=HEIGHT)

    assert first == []
    assert [fact.disposition for fact in second] == ["oscillation", "oscillation"]
    assert counter.counts()[0].entries == 0
    assert counter.counts()[0].exits == 0


def test_opposite_crossings_eleven_frames_apart_both_confirm() -> None:
    counter = SpatialCounter([_shop()])
    _observe(counter, 0, _detection(1, 50, 80))
    _observe(counter, 1, _detection(1, 50, 20))
    later = counter.observe(12, [_detection(1, 50, 80)], width=WIDTH, height=HEIGHT)
    finished = counter.finish()

    assert [fact.disposition for fact in later] == ["confirmed"]
    assert [fact.direction for fact in later] == ["entry"]
    assert [fact.disposition for fact in finished] == ["confirmed"]
    assert [fact.direction for fact in finished] == ["exit"]
    assert counter.counts()[0].entries == 1
    assert counter.counts()[0].exits == 1


def test_a_new_track_id_does_not_inherit_a_crossing_or_create_an_exit() -> None:
    counter = SpatialCounter([_shop()])
    _observe(counter, 0, _detection(1, 50, 80))
    _observe(counter, 1, _detection(2, 50, 20))
    facts = counter.finish()

    assert facts == []
    assert counter.counts()[0].entries == 0
    assert counter.counts()[0].exits == 0


def test_visible_occupancy_is_the_last_frame_front_zone_only() -> None:
    counter = SpatialCounter([_shop()])
    _observe(
        counter,
        0,
        _detection(1, 50, 80),
        _detection(2, 20, 90),
        _detection(3, 80, 70),
        _detection(4, 40, 95),
    )
    _observe(
        counter,
        1,
        _detection(1, 50, 80),
        _detection(2, 20, 90),
        _detection(3, 50, 20),
    )

    counts = counter.counts()[0]
    assert counts.visible_occupancy == 2
    payloads = counter.measure_payloads(partial=True)
    occupancy = next(item for item in payloads if item["code"] == "visible_occupancy")
    assert occupancy["value"] == 2
    assert occupancy["partial"] is True
    assert occupancy["availability"] == "available"
