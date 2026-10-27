"""Possible-purchase estimates from exclusive person–bag overlap (video time)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from flowsight.vision.detector import BagBox, Detection, boxes_overlap

MINIMUM_SECONDS = Decimal("1")
GAP_SECONDS = Decimal("1")


@dataclass(frozen=True)
class PossiblePurchaseDraft:
    visit_count: int
    track_ids: tuple[int, ...]
    availability: str = "available"
    minimum_seconds: Decimal = MINIMUM_SECONDS
    precision_uncommitted: bool = True


@dataclass
class _TrackRun:
    start_frame: int | None = None
    last_good_frame: int | None = None
    confirmed: bool = False


@dataclass
class PossiblePurchaseRecorder:
    """Accumulate exclusive bag overlaps; confirm at ≥1 s of video time."""

    fps: float
    _runs: dict[int, _TrackRun] = field(default_factory=dict)
    _confirmed: set[int] = field(default_factory=set)

    def observe(
        self,
        frame_index: int,
        persons: list[Detection],
        bags: list[BagBox],
    ) -> None:
        exclusive = _exclusive_track_ids(persons, bags)
        present = {detection.track_id for detection in persons}

        for track_id, run in list(self._runs.items()):
            if track_id in exclusive:
                continue
            if run.last_good_frame is None:
                continue
            if _seconds(run.last_good_frame, frame_index, self.fps) > GAP_SECONDS:
                self._close_run(track_id, run)

        for track_id in exclusive:
            run = self._runs.setdefault(track_id, _TrackRun())
            if run.last_good_frame is not None and _seconds(
                run.last_good_frame, frame_index, self.fps
            ) > GAP_SECONDS:
                self._close_run(track_id, run)
                run = self._runs.setdefault(track_id, _TrackRun())
            if run.start_frame is None:
                run.start_frame = frame_index
            run.last_good_frame = frame_index
            if (
                run.start_frame is not None
                and _seconds(run.start_frame, frame_index, self.fps) >= MINIMUM_SECONDS
            ):
                run.confirmed = True

        for track_id, run in list(self._runs.items()):
            if track_id in present or track_id in exclusive:
                continue
            if run.last_good_frame is None:
                continue
            if _seconds(run.last_good_frame, frame_index, self.fps) > GAP_SECONDS:
                self._close_run(track_id, run)

    def finish(self) -> PossiblePurchaseDraft:
        for track_id, run in list(self._runs.items()):
            self._close_run(track_id, run)
        ordered = tuple(sorted(self._confirmed))
        return PossiblePurchaseDraft(visit_count=len(ordered), track_ids=ordered)

    def _close_run(self, track_id: int, run: _TrackRun) -> None:
        if run.confirmed or (
            run.start_frame is not None
            and run.last_good_frame is not None
            and _seconds(run.start_frame, run.last_good_frame, self.fps) >= MINIMUM_SECONDS
        ):
            self._confirmed.add(track_id)
        self._runs.pop(track_id, None)


def _exclusive_track_ids(persons: list[Detection], bags: list[BagBox]) -> set[int]:
    exclusive: set[int] = set()
    for bag in bags:
        hits = [
            detection.track_id
            for detection in persons
            if boxes_overlap(detection.bbox, bag.bbox)
        ]
        if len(hits) == 1:
            exclusive.add(hits[0])
    return exclusive


def _seconds(start_frame: int, end_frame: int, fps: float) -> Decimal:
    if end_frame < start_frame:
        return Decimal("0")
    return (Decimal(end_frame - start_frame) / Decimal(str(fps))).quantize(
        Decimal("0.000001")
    )
