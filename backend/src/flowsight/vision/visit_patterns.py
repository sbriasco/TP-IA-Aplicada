"""Area sequences and estimated groups from the feet already used for scene facts.

This module does not read SQL, the video, or the heatmap sample.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from flowsight.scene.geometry import _point_in_polygon

ZoneRoleName = Literal["front", "interior", "window"]
PROXIMITY_WIDTH_FRACTION = Decimal("0.08")
DIRECTION_DEGREES = Decimal("45")
MINIMUM_SECONDS = Decimal("2")
MOTION_EPSILON_WIDTH_FRACTION = Decimal("0.005")
_COS_45 = math.cos(math.radians(45))


@dataclass(frozen=True)
class Area:
    shop_id: uuid.UUID
    zone_role: ZoneRoleName


@dataclass(frozen=True)
class ConfiguredArea:
    shop_id: uuid.UUID
    zone_role: ZoneRoleName
    polygon: Sequence[Sequence[float]]


@dataclass(frozen=True)
class AreaTransition:
    from_shop_id: uuid.UUID
    from_zone_role: ZoneRoleName
    to_shop_id: uuid.UUID
    to_zone_role: ZoneRoleName
    track_count: int


@dataclass(frozen=True)
class SequenceCount:
    areas: tuple[Area, ...]
    track_count: int


@dataclass(frozen=True)
class ShopTransition:
    from_shop_id: uuid.UUID
    to_shop_id: uuid.UUID
    track_count: int


@dataclass(frozen=True)
class GroupEpisode:
    ordinal: int
    started_video_timestamp_seconds: Decimal
    ended_video_timestamp_seconds: Decimal
    label: Literal["group_estimate"]
    track_ids: tuple[int, ...]


@dataclass(frozen=True)
class VisitPatternDraft:
    patterns_availability: Literal["available", "unavailable"]
    patterns_unavailable_reason: Literal["no_areas"] | None
    groups_availability: Literal["available"]
    group_count: int
    area_transitions: tuple[AreaTransition, ...]
    sequences: tuple[SequenceCount, ...]
    shop_transitions: tuple[ShopTransition, ...]
    groups: tuple[GroupEpisode, ...]


@dataclass
class _TrackState:
    last_frame: int | None = None
    sequence: list[Area] = field(default_factory=list)
    outside_since: int | None = None
    closed: list[tuple[Area, ...]] = field(default_factory=list)
    last_pixel: tuple[float, float] | None = None
    last_pixel_frame: int | None = None
    vector: tuple[float, float] | None = None


@dataclass
class _GroupRun:
    start: int
    last: int


class VisitPatternRecorder:
    """One file analysis. State stays in memory and is discarded after finish()."""

    def __init__(
        self,
        areas: Sequence[ConfiguredArea],
        *,
        fps: float,
        width: int,
        height: int,
    ) -> None:
        self._areas = list(areas)
        self._fps = fps
        self._width = width
        self._height = height
        self._tracks: dict[int, _TrackState] = {}
        self._groups: dict[frozenset[int], _GroupRun] = {}
        self._closed_groups: list[tuple[frozenset[int], _GroupRun]] = []

    def observe(
        self, frame_index: int, feet: Sequence[tuple[int, tuple[float, float]]]
    ) -> None:
        for track_id, foot in feet:
            state = self._tracks.setdefault(track_id, _TrackState())
            self._advance_track(state, frame_index, foot)
        self._advance_groups(frame_index, feet)

    def finish(self) -> VisitPatternDraft:
        for members, run in list(self._groups.items()):
            self._emit_group(members, run)
        self._groups.clear()
        sequences: dict[tuple[Area, ...], set[int]] = defaultdict(set)
        for track_id, state in self._tracks.items():
            self._close_sequence(state)
            for chain in state.closed:
                sequences[chain].add(track_id)
        return _draft(self._areas, sequences, self._closed_groups, self._seconds)

    def _advance_track(self, state: _TrackState, frame: int, foot: tuple[float, float]) -> None:
        occupied = self._occupied(foot)
        gap = (
            state.last_frame is not None
            and self._seconds(state.last_frame, frame) > Decimal("1")
        )
        if gap:
            self._close_sequence(state)
        if state.last_frame is None or gap:
            state.outside_since = None
            state.sequence = [next(iter(occupied))] if len(occupied) == 1 else []
        else:
            self._continue_track(state, frame, occupied)
        self._update_vector(state, frame, foot)
        state.last_frame = frame

    def _continue_track(self, state: _TrackState, frame: int, occupied: set[Area]) -> None:
        if not occupied:
            if state.outside_since is None:
                state.outside_since = frame
            elif self._seconds(state.outside_since, frame) > Decimal("1"):
                self._close_sequence(state)
            return
        state.outside_since = None
        if not state.sequence:
            if len(occupied) == 1:
                state.sequence = [next(iter(occupied))]
            return
        tail = state.sequence[-1]
        if tail in occupied or len(occupied) != 1:
            return
        nxt = next(iter(occupied))
        if nxt != tail:
            state.sequence.append(nxt)

    def _close_sequence(self, state: _TrackState) -> None:
        if state.sequence:
            state.closed.append(tuple(state.sequence))
            state.sequence = []
        state.outside_since = None

    def _occupied(self, foot: tuple[float, float]) -> set[Area]:
        found: set[Area] = set()
        for area in self._areas:
            if _point_in_polygon(foot, area.polygon):
                found.add(Area(area.shop_id, area.zone_role))
        return found

    def _update_vector(self, state: _TrackState, frame: int, foot: tuple[float, float]) -> None:
        pixel = (foot[0] * self._width, foot[1] * self._height)
        vector = None
        if (
            state.last_pixel is not None
            and state.last_pixel_frame is not None
            and self._seconds(state.last_pixel_frame, frame) <= Decimal("1")
        ):
            delta = (pixel[0] - state.last_pixel[0], pixel[1] - state.last_pixel[1])
            if math.hypot(*delta) >= float(MOTION_EPSILON_WIDTH_FRACTION) * self._width:
                vector = delta
        state.vector = vector
        state.last_pixel = pixel
        state.last_pixel_frame = frame

    def _advance_groups(
        self, frame: int, feet: Sequence[tuple[int, tuple[float, float]]]
    ) -> None:
        present = {track_id for track_id, _foot in feet}
        held: dict[frozenset[int], _GroupRun] = {}
        for members, run in list(self._groups.items()):
            if members <= present:
                continue
            if self._seconds(run.last, frame) <= Decimal("1"):
                held[members] = run
            else:
                self._emit_group(members, run)
                self._groups.pop(members, None)
        blocked = {track_id for members in held for track_id in members}
        vectors = {
            track_id: self._tracks[track_id].vector
            for track_id in present
            if track_id not in blocked and track_id in self._tracks
        }
        pixels = {
            track_id: self._tracks[track_id].last_pixel
            for track_id in vectors
            if self._tracks[track_id].last_pixel is not None
        }
        edges = _edges(pixels, vectors, float(PROXIMITY_WIDTH_FRACTION) * self._width)
        qualifying = _cliques([track for track in pixels if vectors.get(track) is not None], edges)
        ranked = sorted(
            qualifying,
            key=lambda members: (
                self._start_of(members, frame),
                -len(members),
                tuple(sorted(members)),
            ),
        )
        assigned: set[int] = set(blocked)
        survivors: dict[frozenset[int], _GroupRun] = dict(held)
        for members in ranked:
            kept = frozenset(track for track in members if track not in assigned)
            if len(kept) < 2:
                continue
            start = self._start_of(kept, frame)
            survivors[kept] = _GroupRun(start=start, last=frame)
            assigned.update(kept)
        for members, run in list(self._groups.items()):
            continued = members in survivors and survivors[members].start == run.start
            if not continued:
                self._emit_group(members, run)
        self._groups = survivors

    def _start_of(self, members: frozenset[int], frame: int) -> int:
        current = self._groups.get(members)
        if current is not None and self._seconds(current.last, frame) <= Decimal("1"):
            return current.start
        return frame

    def _emit_group(self, members: frozenset[int], run: _GroupRun) -> None:
        if self._seconds(run.start, run.last) < MINIMUM_SECONDS:
            return
        self._closed_groups.append((members, run))

    def _seconds(self, start: int, end: int) -> Decimal:
        if self._fps <= 0:
            return Decimal("0")
        return (Decimal(end - start) / Decimal(str(self._fps))).quantize(Decimal("0.000001"))


def build_visit_patterns(
    observations: Sequence[tuple[int, Sequence[tuple[int, tuple[float, float]]]]],
    areas: Sequence[ConfiguredArea],
    *,
    fps: float,
    width: int,
    height: int,
) -> VisitPatternDraft:
    recorder = VisitPatternRecorder(areas, fps=fps, width=width, height=height)
    for frame_index, feet in observations:
        recorder.observe(frame_index, feet)
    return recorder.finish()


def _draft(
    areas: Sequence[ConfiguredArea],
    sequences: dict[tuple[Area, ...], set[int]],
    groups: list[tuple[frozenset[int], _GroupRun]],
    seconds,
) -> VisitPatternDraft:
    area_tracks: dict[tuple[Area, Area], set[int]] = defaultdict(set)
    shop_tracks: dict[tuple[uuid.UUID, uuid.UUID], set[int]] = defaultdict(set)
    for chain, tracks in sequences.items():
        for left, right in zip(chain, chain[1:], strict=False):
            area_tracks[(left, right)].update(tracks)
            if left.shop_id != right.shop_id:
                shop_tracks[(left.shop_id, right.shop_id)].update(tracks)
    ordered_groups = sorted(
        groups, key=lambda item: (item[1].start, min(item[0]), tuple(sorted(item[0])))
    )
    episodes = tuple(
        GroupEpisode(
            ordinal=index,
            started_video_timestamp_seconds=seconds(0, run.start),
            ended_video_timestamp_seconds=seconds(0, run.last),
            label="group_estimate",
            track_ids=tuple(sorted(members)),
        )
        for index, (members, run) in enumerate(ordered_groups, start=1)
    )
    if not areas:
        availability: Literal["available", "unavailable"] = "unavailable"
        reason: Literal["no_areas"] | None = "no_areas"
        transitions: tuple[AreaTransition, ...] = ()
        sequence_rows: tuple[SequenceCount, ...] = ()
        shops: tuple[ShopTransition, ...] = ()
    else:
        availability = "available"
        reason = None
        transitions = tuple(
            AreaTransition(
                left.shop_id,
                left.zone_role,
                right.shop_id,
                right.zone_role,
                len(tracks),
            )
            for (left, right), tracks in sorted(
                area_tracks.items(),
                key=lambda item: (
                    str(item[0][0].shop_id),
                    item[0][0].zone_role,
                    str(item[0][1].shop_id),
                    item[0][1].zone_role,
                ),
            )
        )
        sequence_rows = tuple(
            SequenceCount(chain, len(tracks))
            for chain, tracks in sorted(
                sequences.items(),
                key=lambda item: tuple((str(area.shop_id), area.zone_role) for area in item[0]),
            )
        )
        shops = tuple(
            ShopTransition(left, right, len(tracks))
            for (left, right), tracks in sorted(
                shop_tracks.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
            )
        )
    return VisitPatternDraft(
        patterns_availability=availability,
        patterns_unavailable_reason=reason,
        groups_availability="available",
        group_count=len(episodes),
        area_transitions=transitions,
        sequences=sequence_rows,
        shop_transitions=shops,
        groups=episodes,
    )


def _edges(
    pixels: dict[int, tuple[float, float] | None],
    vectors: dict[int, tuple[float, float] | None],
    proximity_px: float,
) -> set[frozenset[int]]:
    edges: set[frozenset[int]] = set()
    ids = [track for track, pixel in pixels.items() if pixel is not None and vectors.get(track)]
    for index, left in enumerate(ids):
        left_pixel = pixels[left]
        left_vector = vectors[left]
        if left_pixel is None or left_vector is None:
            continue
        for right in ids[index + 1 :]:
            right_pixel = pixels[right]
            right_vector = vectors[right]
            if right_pixel is None or right_vector is None:
                continue
            distance = math.hypot(
                left_pixel[0] - right_pixel[0], left_pixel[1] - right_pixel[1]
            )
            if distance > proximity_px:
                continue
            if _angle_within(left_vector, right_vector):
                edges.add(frozenset((left, right)))
    return edges


def _angle_within(left: tuple[float, float], right: tuple[float, float]) -> bool:
    left_norm = math.hypot(*left)
    right_norm = math.hypot(*right)
    if left_norm == 0 or right_norm == 0:
        return False
    cosine = (left[0] * right[0] + left[1] * right[1]) / (left_norm * right_norm)
    return cosine >= _COS_45 - 1e-9


def _cliques(nodes: list[int], edges: set[frozenset[int]]) -> list[frozenset[int]]:
    linked = sorted({track for edge in edges for track in edge if track in set(nodes)})
    if len(linked) > 12:
        linked = linked[:12]
    found: list[frozenset[int]] = []
    total = len(linked)
    for mask in range(1, 1 << total):
        members = [linked[bit] for bit in range(total) if mask & (1 << bit)]
        if len(members) < 2:
            continue
        pairs = (
            frozenset((members[i], members[j]))
            for i in range(len(members))
            for j in range(i + 1, len(members))
        )
        if all(pair in edges for pair in pairs):
            found.append(frozenset(members))
    return found
