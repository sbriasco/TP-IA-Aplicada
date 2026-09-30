"""Scene facts from feet and confirmed crossings, without a database."""

from __future__ import annotations

import uuid

from flowsight.vision.detector import Detection
from flowsight.vision.events import SceneEventRecorder
from flowsight.vision.spatial import ShopGeometry, SpatialCounter

WIDTH = 100
HEIGHT = 100
LINE = ((0.0, 0.5), (1.0, 0.5))
FRONT = ((0.0, 0.6), (1.0, 0.6), (1.0, 1.0), (0.0, 1.0))
INTERIOR = ((0.0, 0.0), (1.0, 0.0), (1.0, 0.4), (0.0, 0.4))
WINDOW = ((0.0, 0.0), (0.2, 0.0), (0.2, 0.2), (0.0, 0.2))


def _shop(**overrides: object) -> ShopGeometry:
    values: dict[str, object] = {
        "shop_id": uuid.uuid4(),
        "shop_name": "Local",
        "front_polygon": FRONT,
        "interior_polygon": INTERIOR,
        "line_start": LINE[0],
        "line_end": LINE[1],
        "entry_direction": "a_to_b",
        "window_polygon": WINDOW,
    }
    values.update(overrides)
    return ShopGeometry(**values)  # type: ignore[arg-type]


def _run(
    shop: ShopGeometry,
    frames: list[tuple[int, list[tuple[int, tuple[float, float]]]]],
    fps: float = 1,
) -> list[str]:
    counter = SpatialCounter([shop])
    recorder = SceneEventRecorder([shop], fps=fps)
    for frame_index, feet in frames:
        detections = [
            Detection(
                track_id=track_id,
                bbox=(x * WIDTH - 1, y * HEIGHT - 1, x * WIDTH + 1, y * HEIGHT),
            )
            for track_id, (x, y) in feet
        ]
        facts = counter.observe(frame_index, detections, width=WIDTH, height=HEIGHT)
        recorder.observe(frame_index, feet, facts)
    recorder.accept_crossings(counter.finish())
    return [f"{event.kind}:{event.zone_role}:{event.track_id}" for event in recorder.finish()]


def test_entry_sense_records_store_enter_and_the_opposite_records_store_exit() -> None:
    shop = _shop()
    entered = _run(shop, [(0, [(1, (0.5, 0.8))]), (11, [(1, (0.5, 0.2))])])
    assert "store_enter:None:1" in entered

    opposite = _run(
        _shop(entry_direction="b_to_a"),
        [(0, [(1, (0.5, 0.8))]), (11, [(1, (0.5, 0.2))])],
    )
    assert "store_exit:None:1" in opposite
    assert "store_enter:None:1" not in opposite


def test_line_extension_without_segment_intersection_records_nothing_about_the_store() -> None:
    short = _shop(line_start=(0.4, 0.5), line_end=(0.6, 0.5))
    kinds = _run(short, [(0, [(1, (0.1, 0.8))]), (11, [(1, (0.1, 0.2))])])
    assert "store_enter:None:1" not in kinds
    assert "store_exit:None:1" not in kinds


def test_oscillation_inside_ten_frames_confirms_no_store_event() -> None:
    kinds = _run(_shop(), [(0, [(1, (0.5, 0.8))]), (1, [(1, (0.5, 0.2))]), (11, [(1, (0.5, 0.8))])])
    assert "store_enter:None:1" not in kinds
    assert "store_exit:None:1" not in kinds


def test_leaving_the_front_zone_closes_a_dwell_in_video_seconds() -> None:
    shop = _shop()
    recorder = SceneEventRecorder([shop], fps=2)
    recorder.observe(0, [(1, (0.5, 0.8))], [])
    recorder.observe(4, [(1, (0.5, 0.5))], [])
    dwells = [event for event in recorder.finish() if event.kind == "dwell"]
    assert len(dwells) == 1
    assert dwells[0].zone_role == "front"
    assert dwells[0].duration_seconds == (4 - 0) / 2


def test_a_lost_track_inside_the_front_zone_has_no_dwell_or_store_exit() -> None:
    kinds = _run(_shop(), [(0, [(1, (0.5, 0.8))]), (3, [])])
    assert "dwell:front:1" not in kinds
    assert "store_exit:None:1" not in kinds
    assert "zone_exit:front:1" not in kinds


def test_interior_only_can_enter_and_exit_without_a_dwell() -> None:
    kinds = _run(_shop(), [(0, [(1, (0.5, 0.2))]), (2, [(1, (0.5, 0.5))])])
    assert "zone_enter:interior:1" in kinds
    assert "zone_exit:interior:1" in kinds
    assert not any(kind.startswith("dwell:") for kind in kinds)


def test_a_front_foot_without_store_enter_is_a_pass() -> None:
    kinds = _run(_shop(), [(0, [(1, (0.5, 0.8))])])
    assert "store_pass:None:1" in kinds
    assert "store_enter:None:1" not in kinds
