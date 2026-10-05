"""Crossing confirmation follows observed capture time, not frame count."""

from decimal import Decimal
from uuid import uuid4

import numpy as np

from flowsight.capture.contracts import CapturedFrame
from flowsight.vision.detector import Detection
from flowsight.vision.live_spatial import LiveSpatialCounter
from flowsight.vision.spatial import ShopGeometry


def shop() -> ShopGeometry:
    return ShopGeometry(uuid4(), "Sector", None, None, (0.1, 0.5), (0.9, 0.5), "a_to_b")


def observe(
    counter: LiveSpatialCounter,
    sequence: int,
    time: str,
    y: float,
    segment: int = 0,
    track_id: int = 1,
) -> list:
    frame = CapturedFrame(
        image=np.zeros((100, 100, 3), dtype=np.uint8),
        sequence=sequence,
        segment_index=segment,
        captured_monotonic_ns=int(Decimal(time) * 10**9),
        timestamp_seconds=Decimal(time),
        width=100,
        height=100,
    )
    return counter.observe(frame, [Detection(track_id, (40.0, y - 10, 60.0, y))])


def test_expiration_confirms_without_a_second_crossing_and_keeps_original_minute() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 1, "59.7", 80.0)
    assert observe(counter, 200, "59.8", 20.0) == []
    assert observe(counter, 300, "60.0", 20.0) == []
    facts = observe(counter, 400, "60.2", 20.0)
    assert len(facts) == 1
    assert facts[0].direction == "entry"
    assert facts[0].capture_timestamp_seconds == Decimal("59.8")
    assert facts[0].confirmed_at_capture_seconds == Decimal("60.2")
    assert counter.advance(Decimal("60.2")) == []


def test_opposite_crossings_inside_window_are_discarded() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 0, "0", 80.0)
    observe(counter, 5, ".1", 20.0)
    observe(counter, 100, ".2", 80.0)
    assert observe(counter, 200, ".6", 80.0) == []
    assert counter.advance(Decimal(".6")) == []


def test_return_outside_window_counts_both_directions() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 0, "0", 80.0)
    observe(counter, 1, ".1", 20.0)
    first = observe(counter, 2, ".5", 80.0)
    second = observe(counter, 3, ".9", 80.0)
    assert [fact.direction for fact in first + second] == ["entry", "exit"]


def test_gap_and_segment_do_not_bridge_a_crossing() -> None:
    for gap, segment in (("2", 0), (".1", 1)):
        counter = LiveSpatialCounter([shop()])
        observe(counter, 0, "0", 80.0)
        assert observe(counter, 1, gap, 20.0, segment) == []
        assert observe(counter, 2, str(Decimal(gap) + Decimal(".5")), 20.0, segment) == []


def test_discontinuity_discards_unconfirmed_crossing() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 0, "0", 80.0)
    observe(counter, 1, ".1", 20.0)
    counter.discontinue(Decimal(".2"))
    assert observe(counter, 2, ".7", 20.0, segment=1) == []


def test_advance_cannot_invent_a_future_observation() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 0, "0", 80.0)
    observe(counter, 1, ".1", 20.0)
    assert counter.advance(Decimal("99")) == []


def test_a_missing_track_cannot_be_confirmed_by_another_person() -> None:
    counter = LiveSpatialCounter([shop()])
    observe(counter, 0, "0", 80.0)
    observe(counter, 1, ".1", 20.0)
    assert observe(counter, 2, ".6", 20.0, track_id=2) == []
    assert counter.pending_count == 0
    assert counter.discarded_crossings == 1


def test_active_state_is_bounded_even_for_many_new_ids() -> None:
    counter = LiveSpatialCounter([shop()], max_tracks=2)
    frame = CapturedFrame(
        image=np.zeros((100, 100, 3), dtype=np.uint8),
        sequence=0,
        segment_index=0,
        captured_monotonic_ns=0,
        timestamp_seconds=Decimal(0),
        width=100,
        height=100,
    )
    counter.observe(frame, [Detection(track, (40.0, 60.0, 60.0, 80.0)) for track in range(20)])
    assert counter.tracked_count == 2
    assert counter.evicted_tracks == 18


def test_opposite_at_exact_window_boundary_is_still_oscillation() -> None:
    counter = LiveSpatialCounter([shop()], window_s=Decimal(".3"))
    observe(counter, 0, "0", 80.0)
    observe(counter, 1, ".1", 20.0)
    assert observe(counter, 2, ".4", 80.0) == []
    assert observe(counter, 3, ".8", 80.0) == []
