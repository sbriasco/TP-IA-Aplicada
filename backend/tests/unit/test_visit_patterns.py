"""Area sequences and estimated groups from known feet, without a database."""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from itertools import combinations

from flowsight.vision.visit_patterns import (
    Area,
    ConfiguredArea,
    _cliques,
    _edges,
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


def test_all_seven_separate_pairs_are_groups_without_a_twelve_person_limit() -> None:
    tracks = {
        2 * pair + offset + 1: (0.1 + offset * 0.02, 0.1 + pair * 0.12)
        for pair in range(7)
        for offset in range(2)
    }
    draft = build_visit_patterns(
        _walk(range(22), tracks, step=0.01), [], fps=FPS, width=WIDTH, height=HEIGHT
    )
    assert [group.track_ids for group in draft.groups] == [
        (1, 2),
        (3, 4),
        (5, 6),
        (7, 8),
        (9, 10),
        (11, 12),
        (13, 14),
    ]


def test_a_dense_group_keeps_all_thirty_two_candidates() -> None:
    draft = build_visit_patterns(
        _walk(range(22), {track: (0.1, 0.5) for track in range(1, 33)}, step=0.01),
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.group_count == 1
    assert draft.groups[0].track_ids == tuple(range(1, 33))


def test_an_established_pair_keeps_priority_when_a_third_person_joins() -> None:
    draft = build_visit_patterns(
        [
            *_walk(range(6), {1: (0.1, 0.5), 2: (0.12, 0.5)}, step=0.01),
            *_walk(range(6, 28), {1: (0.1, 0.5), 2: (0.12, 0.5), 3: (0.14, 0.5)}, step=0.01),
        ],
        [],
        fps=FPS,
        width=WIDTH,
        height=HEIGHT,
    )
    assert draft.group_count == 1
    assert draft.groups[0].track_ids == (1, 2)
    assert draft.groups[0].started_video_timestamp_seconds == Decimal("0.1")


def _opposite_pairs_circle(size: int) -> dict[int, tuple[float, float]]:
    radius = 80 / (1 + math.cos(math.pi / size))
    return {
        index + 1: (
            400 + radius * math.cos(2 * math.pi * index / size),
            500 + radius * math.sin(2 * math.pi * index / size),
        )
        for index in range(size)
    }


def test_adversarial_geometry_has_bounded_candidates_without_dropping_ids() -> None:
    pixels = _opposite_pairs_circle(24)
    edges = _edges(pixels, {track: (10, 0) for track in pixels}, proximity_px=80)
    # All pairs satisfy the actual geometry except the twelve opposite pairs:
    # enumerating every maximal clique would materialize 2**12 candidates.
    assert len(edges) == 264
    candidates = _cliques(list(pixels), edges)
    assert len(candidates) <= 24
    assert set().union(*candidates) == set(pixels)
    assert all(
        len(members) >= 2 and all(frozenset(pair) in edges for pair in combinations(members, 2))
        for members in candidates
    )


def test_adversarial_geometry_groups_all_fifty_six_ids_including_the_residual() -> None:
    tracks = {track: (x / 1000, y / 1000) for track, (x, y) in _opposite_pairs_circle(56).items()}
    observations = _walk(range(22), tracks, step=0.01)
    draft = build_visit_patterns(observations, [], fps=FPS, width=1000, height=1000)
    assert [group.track_ids for group in draft.groups] == [
        tuple(range(1, 29)),
        tuple(range(29, 57)),
    ]
    assert build_visit_patterns(observations, [], fps=FPS, width=1000, height=1000) == draft
