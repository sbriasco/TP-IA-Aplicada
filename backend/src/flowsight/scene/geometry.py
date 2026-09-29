"""Pure geometry for scene configuration (specs/004, R11).

Normalized points live in [0, 1]; pixel points are in reference-frame pixels
(image coordinates, y grows downwards). Measuring functions work on pixel points
and return plain values; the accept/reject decision against the module constants
belongs to the validation layer.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

Point = tuple[float, float]

MIN_LINE_PX = 10
MIN_AREA_PX2 = 100
MIN_VERTEX_GAP_PX = 2
MAX_VERTICES = 64
NORMALIZED_DECIMALS = 6


def in_unit_range(point: Sequence[float]) -> bool:
    """True if both coordinates are in the closed range [0, 1]."""

    return all(0.0 <= value <= 1.0 for value in point)


def to_px(point: Sequence[float], frame_width: int, frame_height: int) -> Point:
    """Convert a normalized point to frame pixels, without checking the range."""

    return (point[0] * frame_width, point[1] * frame_height)


def normalize(point_px: Sequence[float], frame_width: int, frame_height: int) -> Point:
    """Convert a pixel point to normalized coordinates rounded to 6 decimals."""

    return (
        round(point_px[0] / frame_width, NORMALIZED_DECIMALS),
        round(point_px[1] / frame_height, NORMALIZED_DECIMALS),
    )


def polygon_area_px(polygon: Sequence[Sequence[float]]) -> float:
    """Absolute Shoelace area; the orientation of the polygon does not matter."""

    count = len(polygon)
    twice_area = 0.0
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        twice_area += x1 * y2 - x2 * y1
    return abs(twice_area) / 2


def _orientation(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> bool:
    """True if ``c`` (already collinear with a-b) lies within the bounding box of a-b."""

    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])


def segments_intersect(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
) -> bool:
    """True if closed segments p1-p2 and q1-q2 cross or touch (experiment 001 logic)."""

    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if o1 == 0 and _on_segment(p1, p2, q1):
        return True
    if o2 == 0 and _on_segment(p1, p2, q2):
        return True
    if o3 == 0 and _on_segment(q1, q2, p1):
        return True
    if o4 == 0 and _on_segment(q1, q2, p2):
        return True
    return False


def _edges(polygon: Sequence[Sequence[float]]) -> list[tuple[Sequence[float], Sequence[float]]]:
    """Edges of the closed polygon, including the closing edge last -> first."""

    count = len(polygon)
    return [(polygon[index], polygon[(index + 1) % count]) for index in range(count)]


def polygon_self_intersects(polygon: Sequence[Sequence[float]]) -> bool:
    """True if two non-adjacent edges cross or touch.

    Adjacent edges (consecutive, and the closing edge with the first one) share a
    vertex and are skipped; with 3 vertices every pair is adjacent.
    """

    edges = _edges(polygon)
    count = len(edges)
    for i in range(count):
        for j in range(i + 2, count):
            if i == 0 and j == count - 1:
                continue
            if segments_intersect(*edges[i], *edges[j]):
                return True
    return False


def min_consecutive_distance_px(polygon: Sequence[Sequence[float]]) -> float:
    """Smallest distance between consecutive vertices, including the closing edge."""

    return min(math.dist(start, end) for start, end in _edges(polygon))


def line_length_px(start: Sequence[float], end: Sequence[float]) -> float:
    """Euclidean length of a segment in pixels."""

    return math.dist(start, end)


def side_of_line(
    start: Sequence[float], end: Sequence[float], point: Sequence[float]
) -> Literal["A", "B"] | None:
    """Side of ``point`` relative to the directed line start -> end.

    ``cross = dx*(py - sy) - dy*(px - sx)`` in image coordinates: ``> 0`` is A,
    ``< 0`` is B and ``0`` (on the line) is ``None``.
    """

    cross = _orientation(start, end, point)
    if cross > 0:
        return "A"
    if cross < 0:
        return "B"
    return None


def aspect_ratio_matches(
    video_width: int,
    video_height: int,
    frame_width: int,
    frame_height: int,
    tol: float = 0.01,
) -> bool:
    """True if ``|(wv / hv) / (wf / hf) - 1| <= tol``."""

    ratio = (video_width / video_height) / (frame_width / frame_height)
    return abs(ratio - 1) <= tol


def _point_in_polygon(point: Sequence[float], polygon: Sequence[Sequence[float]]) -> bool:
    """Ray casting; points on the border are not guaranteed to count as inside."""

    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _edges(polygon):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def polygons_overlap(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> bool:
    """True if any edges cross or touch, or one polygon contains a vertex of the other.

    Edges are closed segments, so polygons that only share a border also overlap.
    """

    for edge_a in _edges(first):
        for edge_b in _edges(second):
            if segments_intersect(*edge_a, *edge_b):
                return True
    return _point_in_polygon(first[0], second) or _point_in_polygon(second[0], first)


def segment_touches_polygon(
    start: Sequence[float], end: Sequence[float], polygon: Sequence[Sequence[float]]
) -> bool:
    """True if the segment touches or crosses an edge, or lies inside the polygon."""

    if any(segments_intersect(start, end, *edge) for edge in _edges(polygon)):
        return True
    return _point_in_polygon(start, polygon) or _point_in_polygon(end, polygon)
