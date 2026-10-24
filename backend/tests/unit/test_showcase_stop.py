"""Showcase stops close only when a foot leaves the window after at least three seconds."""

from __future__ import annotations

import uuid
from decimal import Decimal

from flowsight.vision.events import SceneEventRecorder
from flowsight.vision.spatial import ShopGeometry

FRONT = ((0.0, 0.6), (1.0, 0.6), (1.0, 1.0), (0.0, 1.0))
WINDOW = ((0.0, 0.0), (0.2, 0.0), (0.2, 0.2), (0.0, 0.2))
INSIDE = (0.1, 0.1)
OUTSIDE = (0.5, 0.5)
FRONT_FOOT = (0.5, 0.8)


def _shop() -> ShopGeometry:
    return ShopGeometry(
        shop_id=uuid.uuid4(),
        shop_name="Local",
        front_polygon=FRONT,
        interior_polygon=None,
        line_start=None,
        line_end=None,
        entry_direction=None,
        window_polygon=WINDOW,
    )


def _kinds(events: list[object]) -> list[str]:
    return [event.kind for event in events]  # type: ignore[attr-defined]


def test_three_seconds_in_the_window_records_one_stop_and_keeps_the_zone_entry() -> None:
    recorder = SceneEventRecorder([_shop()], fps=1)
    recorder.observe(0, [(1, INSIDE)], [])
    recorder.observe(3, [(1, OUTSIDE)], [])
    events = recorder.finish()
    stops = [event for event in events if event.kind == "showcase_stop"]
    assert len(stops) == 1
    assert stops[0].zone_role == "window"
    assert stops[0].duration_seconds == Decimal("3.000000")
    assert sum(1 for event in events if event.kind == "zone_enter") == 1
    assert "exposure" not in _kinds(events)


def test_two_seconds_in_the_window_does_not_record_a_stop() -> None:
    recorder = SceneEventRecorder([_shop()], fps=1)
    recorder.observe(0, [(1, INSIDE)], [])
    recorder.observe(2, [(1, OUTSIDE)], [])
    events = recorder.finish()
    assert not any(event.kind == "showcase_stop" for event in events)
    assert any(event.kind == "zone_exit" and event.zone_role == "window" for event in events)


def test_a_lost_track_or_the_end_of_the_video_does_not_close_the_stop() -> None:
    lost = SceneEventRecorder([_shop()], fps=1)
    lost.observe(0, [(1, INSIDE)], [])
    lost.observe(10, [], [])
    assert not any(event.kind == "showcase_stop" for event in lost.finish())

    ended = SceneEventRecorder([_shop()], fps=1)
    ended.observe(0, [(1, INSIDE)], [])
    assert not any(event.kind == "showcase_stop" for event in ended.finish())


def test_a_second_entry_keeps_both_zone_entries() -> None:
    recorder = SceneEventRecorder([_shop()], fps=1)
    recorder.observe(0, [(1, INSIDE)], [])
    recorder.observe(1, [(1, OUTSIDE)], [])
    recorder.observe(2, [(1, INSIDE)], [])
    events = recorder.finish()
    enters = [
        event for event in events if event.kind == "zone_enter" and event.zone_role == "window"
    ]
    assert len(enters) == 2
    assert not any(event.kind == "showcase_stop" for event in events)


def test_front_dwell_is_unchanged() -> None:
    recorder = SceneEventRecorder([_shop()], fps=2)
    recorder.observe(0, [(1, FRONT_FOOT)], [])
    recorder.observe(4, [(1, OUTSIDE)], [])
    events = recorder.finish()
    dwells = [event for event in events if event.kind == "dwell"]
    assert len(dwells) == 1
    assert dwells[0].zone_role == "front"
    assert dwells[0].duration_seconds == Decimal("2.000000")
    assert not any(event.kind == "showcase_stop" for event in events)
