"""Area sequences and estimated groups from known feet, without a database."""

from __future__ import annotations

import uuid

from flowsight.vision.visit_patterns import (
    Area,
    ConfiguredArea,
    build_visit_patterns,
)

SHOP_A = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
SHOP_B = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
WIDTH = 100
HEIGHT = 100
FPS = 10.0


def _square(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _area(shop: uuid.UUID, role: str, polygon: tuple[tuple[float, float], ...]) -> ConfiguredArea:
    return ConfiguredArea(shop, role, polygon)  # type: ignore[arg-type]


LEFT = _area(SHOP_A, "front", _square(0.0, 0.2, 0.3, 0.8))
RIGHT = _area(SHOP_A, "interior", _square(0.5, 0.2, 0.8, 0.8))
OVERLAP_A = _area(SHOP_A, "front", _square(0.0, 0.2, 0.45, 0.8))
OVERLAP_B = _area(SHOP_A, "interior", _square(0.25, 0.2, 0.7, 0.8))
OTHER = _area(SHOP_B, "front", _square(0.5, 0.2, 0.8, 0.8))


def _walk(frames: range, tracks: dict[int, tuple[float, float]], step: float = 0.0):
    observations = []
    for frame in frames:
        feet = []
        for track_id, (x_pos, y_pos) in tracks.items():
            feet.append((track_id, (x_pos + step * frame, y_pos)))
        observations.append((frame, feet))
    return observations


def test_leaving_one_area_for_another_counts_one_transition_and_one_sequence() -> None:
    draft = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), (1, [(1, (0.6, 0.5))])],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.patterns_availability == "available"
    assert draft.area_transitions[0].from_zone_role == "front"
    assert draft.area_transitions[0].to_zone_role == "interior"
    assert draft.area_transitions[0].track_count == 1
    assert draft.sequences[0].areas == (
        Area(SHOP_A, "front"),
        Area(SHOP_A, "interior"),
    )
    assert draft.shop_transitions == ()


def test_overlap_does_not_count_until_the_foot_leaves_the_first_area() -> None:
    draft = build_visit_patterns(
        [
            (0, [(1, (0.1, 0.5))]),
            (1, [(1, (0.3, 0.5))]),
            (2, [(1, (0.6, 0.5))]),
        ],
        [OVERLAP_A, OVERLAP_B],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert len(draft.area_transitions) == 1
    assert draft.area_transitions[0].track_count == 1
    assert draft.sequences[0].areas[-1].zone_role == "interior"


def test_a_first_sighting_inside_two_areas_waits_for_a_single_area() -> None:
    draft = build_visit_patterns(
        [(0, [(1, (0.3, 0.5))]), (1, [(1, (0.1, 0.5))])],
        [OVERLAP_A, OVERLAP_B],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.area_transitions == ()
    assert draft.sequences[0].areas == (Area(SHOP_A, "front"),)


def test_returning_to_the_same_area_does_not_repeat_it() -> None:
    draft = build_visit_patterns(
        [
            (0, [(1, (0.1, 0.5))]),
            (1, [(1, (0.9, 0.5))]),
            (2, [(1, (0.1, 0.5))]),
        ],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.area_transitions == ()
    assert draft.sequences[0].areas == (Area(SHOP_A, "front"),)


def test_repeating_a_transition_still_counts_the_visit_once() -> None:
    draft = build_visit_patterns(
        [
            (0, [(1, (0.1, 0.5))]),
            (1, [(1, (0.6, 0.5))]),
            (2, [(1, (0.1, 0.5))]),
            (3, [(1, (0.6, 0.5))]),
        ],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    pair = next(
        row
        for row in draft.area_transitions
        if row.from_zone_role == "front" and row.to_zone_role == "interior"
    )
    assert pair.track_count == 1
    assert len(draft.sequences) == 1
    assert draft.sequences[0].track_count == 1


def test_a_gap_longer_than_one_second_starts_another_sequence() -> None:
    draft = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), (12, [(1, (0.6, 0.5))])],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.area_transitions == ()
    assert {tuple(row.areas) for row in draft.sequences} == {
        (Area(SHOP_A, "front"),),
        (Area(SHOP_A, "interior"),),
    }


def test_exactly_one_second_still_links_the_transition() -> None:
    draft = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), (10, [(1, (0.6, 0.5))])],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert len(draft.area_transitions) == 1


def test_more_than_one_second_outside_closes_the_sequence() -> None:
    outside = [(frame, [(1, (0.9, 0.5))]) for frame in range(1, 13)]
    draft = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), *outside, (13, [(1, (0.6, 0.5))])],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.area_transitions == ()
    assert len(draft.sequences) == 2


def test_a_shop_change_is_counted_only_when_the_shop_changes() -> None:
    changed = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), (1, [(1, (0.6, 0.5))])],
        [LEFT, OTHER],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert changed.shop_transitions[0].from_shop_id == SHOP_A
    assert changed.shop_transitions[0].to_shop_id == SHOP_B
    assert changed.shop_transitions[0].track_count == 1
    same = build_visit_patterns(
        [(0, [(1, (0.1, 0.5))]), (1, [(1, (0.6, 0.5))])],
        [LEFT, RIGHT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert same.area_transitions != ()
    assert same.shop_transitions == ()


def test_no_polygons_make_patterns_unavailable_and_keep_groups() -> None:
    draft = build_visit_patterns(
        _walk(range(0, 22), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.patterns_availability == "unavailable"
    assert draft.patterns_unavailable_reason == "no_areas"
    assert draft.area_transitions == ()
    assert draft.groups_availability == "available"
    assert draft.group_count == 1
    assert draft.groups[0].label == "group_estimate"
    assert draft.groups[0].track_ids == (1, 2)


def test_polygons_without_steps_stay_available_and_empty() -> None:
    draft = build_visit_patterns(
        [(0, [(1, (0.95, 0.95))])],
        [LEFT],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.patterns_availability == "available"
    assert draft.patterns_unavailable_reason is None
    assert draft.area_transitions == ()
    assert draft.sequences == ()


def test_two_moving_visits_within_the_thresholds_form_one_estimated_group() -> None:
    draft = build_visit_patterns(
        _walk(range(0, 22), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.group_count == 1
    assert draft.groups[0].track_ids == (1, 2)
    span = (
        draft.groups[0].ended_video_timestamp_seconds
        - draft.groups[0].started_video_timestamp_seconds
    )
    assert span >= 2


def test_a_still_visit_a_short_approach_and_a_distant_third_stay_out() -> None:
    still = build_visit_patterns(
        _walk(range(0, 22), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.0),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    short = build_visit_patterns(
        _walk(range(0, 11), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    third = build_visit_patterns(
        _walk(
            range(0, 22),
            {1: (0.10, 0.50), 2: (0.16, 0.50), 3: (0.90, 0.50)},
            step=0.02,
        ),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert still.group_count == 0
    assert short.group_count == 0
    assert third.group_count == 1
    assert third.groups[0].track_ids == (1, 2)


def test_a_visit_that_fits_two_groups_stays_in_one() -> None:
    earlier = build_visit_patterns(
        [
            *_walk(range(0, 16), {1: (0.50, 0.50), 2: (0.56, 0.50)}, step=0.02),
            *_walk(range(16, 22), {1: (0.50, 0.50), 2: (0.56, 0.50), 3: (0.44, 0.50)}, step=0.02),
        ],
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert earlier.group_count == 1
    assert earlier.groups[0].track_ids == (1, 2)
    larger = build_visit_patterns(
        _walk(
            range(0, 22),
            {1: (0.50, 0.50), 2: (0.54, 0.50), 3: (0.58, 0.50)},
            step=0.02,
        ),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert larger.groups[0].track_ids == (1, 2, 3)


def test_a_broken_group_that_qualifies_again_is_another_episode() -> None:
    together = _walk(range(0, 22), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02)
    apart = _walk(range(22, 31), {1: (0.10, 0.50), 2: (0.70, 0.50)}, step=0.02)
    again = _walk(range(31, 54), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02)
    draft = build_visit_patterns(
        [*together, *apart, *again], [], fps=FPS, width=WIDTH, height=HEIGHT
    )
    assert draft.group_count == 2
    assert draft.groups[0].track_ids == (1, 2)
    assert draft.groups[1].track_ids == (1, 2)
    assert (
        draft.groups[1].started_video_timestamp_seconds
        > draft.groups[0].ended_video_timestamp_seconds
    )


def test_ending_the_video_keeps_a_group_only_after_two_seconds() -> None:
    early = build_visit_patterns(
        _walk(range(0, 11), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    ready = build_visit_patterns(
        _walk(range(0, 22), {1: (0.10, 0.50), 2: (0.16, 0.50)}, step=0.02),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert early.group_count == 0
    assert ready.group_count == 1
    ended = ready.groups[0].ended_video_timestamp_seconds
    started = ready.groups[0].started_video_timestamp_seconds
    assert ended > started
