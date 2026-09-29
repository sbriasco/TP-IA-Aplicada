"""Boundary tests for the pure scene geometry module (specs/004, R11).

Contract assumed by these tests (T029):

- Points are ``(x, y)`` tuples. Normalized points live in [0, 1]; pixel points are
  in reference-frame pixels (image coordinates, y grows downwards).
- ``in_unit_range(point)`` tells whether both coordinates are in the closed range
  [0, 1]; the validation layer (T030) turns ``False`` into an ``out_of_range`` issue.
- ``to_px(point, frame_width, frame_height)`` only converts a normalized point to
  pixels; it does not check the range.
- ``normalize(point_px, frame_width, frame_height)`` converts a pixel point to
  normalized coordinates rounded to 6 decimals.
- Every other measuring function works on pixel points and returns a plain value;
  the reject/accept decision is taken against the module constants, as the
  validation layer (T030) will do.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flowsight.scene.geometry import (
    MAX_VERTICES,
    MIN_AREA_PX2,
    MIN_LINE_PX,
    MIN_VERTEX_GAP_PX,
    aspect_ratio_matches,
    in_unit_range,
    line_length_px,
    min_consecutive_distance_px,
    normalize,
    polygon_area_px,
    polygon_self_intersects,
    segments_intersect,
    side_of_line,
    to_px,
)

FRAME_W = 1000
FRAME_H = 500
SCENE_EXAMPLE = (
    Path(__file__).resolve().parents[3]
    / "experiments"
    / "video-tracking-validation"
    / "config"
    / "scene.example.json"
)


def _n(x_px: float, y_px: float) -> tuple[float, float]:
    """Normalized point for a pixel position in the 1000x500 test frame."""

    return (x_px / FRAME_W, y_px / FRAME_H)


def _px_polygon(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [to_px(point, FRAME_W, FRAME_H) for point in points]


def _rectangle(x: float, y: float, width: float, height: float) -> list[tuple[float, float]]:
    """Normalized rectangle, clockwise on screen, from pixel position and size."""

    return [_n(x, y), _n(x + width, y), _n(x + width, y + height), _n(x, y + height)]


def test_tolerance_constants_match_the_clarification() -> None:
    assert MIN_LINE_PX == 10
    assert MIN_AREA_PX2 == 100
    assert MIN_VERTEX_GAP_PX == 2
    assert MAX_VERTICES == 64


# --- Coordinates -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        ((0.0, 0.0), (0.0, 0.0)),
        ((1.0, 1.0), (1000.0, 500.0)),
        ((0.0, 1.0), (0.0, 500.0)),
        ((1.0, 0.0), (1000.0, 0.0)),
        ((0.5, 0.25), (500.0, 125.0)),
    ],
)
def test_closed_unit_range_is_accepted_and_converted_to_px(
    point: tuple[float, float], expected: tuple[float, float]
) -> None:
    assert in_unit_range(point)
    assert to_px(point, FRAME_W, FRAME_H) == pytest.approx(expected)


@pytest.mark.parametrize(
    "point",
    [
        (-0.000001, 0.5),
        (1.000001, 0.5),
        (0.5, -0.000001),
        (0.5, 1.000001),
    ],
)
def test_coordinates_just_outside_unit_range_are_rejected(point: tuple[float, float]) -> None:
    assert not in_unit_range(point)


@pytest.mark.parametrize(
    ("point_px", "width", "height", "expected"),
    [
        ((1, 2), 3, 3, (0.333333, 0.666667)),
        ((500, 850), 1920, 1080, (0.260417, 0.787037)),
        ((1400, 850), 1920, 1080, (0.729167, 0.787037)),
        ((0, 0), 1920, 1080, (0.0, 0.0)),
        ((1920, 1080), 1920, 1080, (1.0, 1.0)),
    ],
)
def test_normalize_rounds_to_six_decimals(
    point_px: tuple[float, float], width: int, height: int, expected: tuple[float, float]
) -> None:
    result = normalize(point_px, width, height)

    assert result == expected
    for value in result:
        assert round(value, 6) == value


def test_normalize_and_to_px_round_trip_within_rounding_error() -> None:
    point_px = (1234.5678, 987.6543)

    back = to_px(normalize(point_px, 3840, 2160), 3840, 2160)

    # 6 decimals on a 3840 px frame: at most 0.5e-6 * 3840 px of error.
    assert back == pytest.approx(point_px, abs=0.5e-6 * 3840)


# --- Entry line length -----------------------------------------------------------


@pytest.mark.parametrize(
    ("end_px", "accepted"),
    [
        ((109.99, 100), False),
        ((110, 100), True),
        ((100, 110), True),
    ],
    ids=["9.99px-horizontal", "10px-horizontal", "10px-vertical"],
)
def test_line_length_boundary(end_px: tuple[float, float], accepted: bool) -> None:
    start, end = _px_polygon([_n(100, 100), _n(*end_px)])

    length = line_length_px(start, end)

    assert (length >= MIN_LINE_PX) is accepted


def test_line_length_is_measured_in_frame_pixels_not_normalized_units() -> None:
    # Same normalized delta on both axes: 0.1 * 1000 px vs 0.1 * 500 px.
    assert line_length_px(*_px_polygon([(0.1, 0.1), (0.2, 0.1)])) == pytest.approx(100)
    assert line_length_px(*_px_polygon([(0.1, 0.1), (0.1, 0.2)])) == pytest.approx(50)


# --- Polygon area ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "accepted"),
    [
        (9, 11, False),
        (10, 10, True),
    ],
    ids=["99px2", "100px2"],
)
def test_polygon_area_boundary(width: int, height: int, accepted: bool) -> None:
    polygon = _px_polygon(_rectangle(100, 100, width, height))

    area = polygon_area_px(polygon)

    assert area == pytest.approx(width * height)
    assert (area >= MIN_AREA_PX2) is accepted


def test_clockwise_and_counterclockwise_give_the_same_positive_area() -> None:
    clockwise = _px_polygon([_n(100, 100), _n(400, 100), _n(400, 300), _n(100, 300)])
    counterclockwise = list(reversed(clockwise))

    assert polygon_area_px(clockwise) == pytest.approx(60000)
    assert polygon_area_px(counterclockwise) == pytest.approx(60000)
    assert polygon_self_intersects(clockwise) is False
    assert polygon_self_intersects(counterclockwise) is False


# --- Consecutive vertex gap ------------------------------------------------------


@pytest.mark.parametrize(
    ("polygon_px", "accepted"),
    [
        ([(100, 100), (102, 100), (300, 300), (100, 300)], False),
        ([(100, 100), (102.01, 100), (300, 300), (100, 300)], True),
        # Only the closing edge (last -> first) is short.
        ([(100, 100), (300, 100), (300, 300), (100, 102)], False),
        ([(100, 100), (300, 100), (300, 300), (100, 102.01)], True),
    ],
    ids=["2px", "2.01px", "closing-edge-2px", "closing-edge-2.01px"],
)
def test_consecutive_vertex_gap_boundary(
    polygon_px: list[tuple[float, float]], accepted: bool
) -> None:
    polygon = _px_polygon([_n(*point) for point in polygon_px])

    gap = min_consecutive_distance_px(polygon)

    assert (gap > MIN_VERTEX_GAP_PX) is accepted


@pytest.mark.parametrize(
    "polygon_px",
    [
        [(100, 100), (100, 100), (300, 100), (300, 300)],
        # First and last vertex repeated: the closing edge has length 0.
        [(100, 100), (300, 100), (300, 300), (100, 100)],
    ],
    ids=["consecutive", "closing"],
)
def test_repeated_consecutive_vertices_are_rejected(
    polygon_px: list[tuple[float, float]],
) -> None:
    polygon = _px_polygon([_n(*point) for point in polygon_px])

    gap = min_consecutive_distance_px(polygon)

    assert gap == 0
    assert gap <= MIN_VERTEX_GAP_PX


# --- Self intersection -----------------------------------------------------------


@pytest.mark.parametrize(
    ("polygon_px", "expected"),
    [
        # Bow tie: edges 0 and 2 cross.
        ([(100, 100), (300, 300), (300, 100), (100, 300)], True),
        # Vertex (400, 250) lies on the non-adjacent edge (400, 100)-(400, 400).
        ([(100, 100), (400, 100), (400, 400), (250, 400), (400, 250)], True),
        # Collinear vertex (200, 100) inside the top edge is allowed.
        ([(100, 100), (200, 100), (300, 100), (300, 300), (100, 300)], False),
        # Plain convex and concave polygons.
        ([(100, 100), (300, 100), (300, 300), (100, 300)], False),
        ([(100, 100), (300, 100), (200, 150), (300, 300), (100, 300)], False),
    ],
    ids=["bow-tie", "vertex-touches-edge", "collinear-vertex", "square", "concave"],
)
def test_polygon_self_intersection(polygon_px: list[tuple[float, float]], expected: bool) -> None:
    polygon = _px_polygon([_n(*point) for point in polygon_px])

    assert polygon_self_intersects(polygon) is expected


@pytest.mark.parametrize(
    ("p1", "p2", "q1", "q2", "expected"),
    [
        ((0, 0), (10, 10), (0, 10), (10, 0), True),
        ((0, 0), (10, 0), (10, 0), (20, 5), True),
        ((0, 0), (10, 0), (5, 0), (5, 5), True),
        ((0, 0), (10, 0), (5, 0), (15, 0), True),
        ((0, 0), (10, 0), (11, 0), (20, 0), False),
        ((0, 0), (10, 0), (0, 1), (10, 1), False),
        ((0, 0), (10, 10), (20, 0), (11, 9), False),
    ],
    ids=[
        "crossing",
        "shared-endpoint",
        "endpoint-on-segment",
        "collinear-overlap",
        "collinear-disjoint",
        "parallel",
        "lines-cross-outside-segments",
    ],
)
def test_segments_intersect_closed_segments(
    p1: tuple[float, float],
    p2: tuple[float, float],
    q1: tuple[float, float],
    q2: tuple[float, float],
    expected: bool,
) -> None:
    assert segments_intersect(p1, p2, q1, q2) is expected
    assert segments_intersect(q1, q2, p1, p2) is expected


# --- Entry line sides A/B --------------------------------------------------------


def _example_scene() -> dict:
    return json.loads(SCENE_EXAMPLE.read_text(encoding="utf-8"))


def test_side_of_line_matches_experiment_001_scene_example() -> None:
    scene = _example_scene()
    line = scene["entry_line"]
    start = tuple(line["start"])
    end = tuple(line["end"])
    sample_a = tuple(line["side_A"]["sample_point"])
    sample_b = tuple(line["side_B"]["sample_point"])
    assert (start, end, sample_a) == ((500, 850), (1400, 850), (950, 1000))

    # cross = dx*(py - sy) - dy*(px - sx) = 900*150 - 0*450 = +135000 -> A.
    dx, dy = end[0] - start[0], end[1] - start[1]
    assert dx * (sample_a[1] - start[1]) - dy * (sample_a[0] - start[0]) == 135000

    assert side_of_line(start, end, sample_a) == "A"
    assert side_of_line(start, end, sample_b) == "B"
    assert side_of_line(start, end, (950, 850)) is None


def test_side_of_line_is_preserved_after_normalizing() -> None:
    scene = _example_scene()
    width = scene["frame_reference"]["width"]
    height = scene["frame_reference"]["height"]
    line = scene["entry_line"]
    start = normalize(tuple(line["start"]), width, height)
    end = normalize(tuple(line["end"]), width, height)

    assert side_of_line(start, end, normalize((950, 1000), width, height)) == "A"
    assert side_of_line(start, end, normalize((950, 700), width, height)) == "B"
    # Back in pixels, after the 6-decimal round trip, the sides do not change.
    start_px = to_px(start, width, height)
    end_px = to_px(end, width, height)
    assert side_of_line(start_px, end_px, (950, 1000)) == "A"
    assert side_of_line(start_px, end_px, (950, 700)) == "B"


def test_reversing_the_line_swaps_the_sides() -> None:
    assert side_of_line((1400, 850), (500, 850), (950, 1000)) == "B"
    assert side_of_line((1400, 850), (500, 850), (950, 700)) == "A"


# --- Aspect ratio gate -----------------------------------------------------------


@pytest.mark.parametrize(
    ("video", "frame", "expected"),
    [
        ((1920, 1080), (1280, 720), True),
        ((1280, 720), (1280, 720), True),
        ((640, 480), (1280, 720), False),
        # |ratio - 1| = 0.009375 <= 0.01 vs 0.0101... > 0.01.
        ((1292, 720), (1280, 720), True),
        ((1293, 720), (1280, 720), False),
    ],
    ids=["1920x1080-vs-1280x720", "same", "640x480-vs-1280x720", "inside-1pct", "outside-1pct"],
)
def test_aspect_ratio_matches(
    video: tuple[int, int], frame: tuple[int, int], expected: bool
) -> None:
    assert aspect_ratio_matches(video[0], video[1], frame[0], frame[1]) is expected


def test_aspect_ratio_matches_accepts_custom_tolerance() -> None:
    assert aspect_ratio_matches(1293, 720, 1280, 720, tol=0.02) is True
