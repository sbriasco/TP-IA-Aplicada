"""Whole-session shop funnel from facts already closed. No video and no database."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from flowsight.vision.events import SceneEventFact

STOP_THRESHOLD_SECONDS = Decimal("3")
ATTENTION_THRESHOLD_SECONDS = Decimal("8")
_STAGE_ORDER = (
    "observed_pass",
    "exposure",
    "stop",
    "attention",
    "linked_entry",
)
_RATE_PAIRS = (
    ("observed_pass_to_exposure", "observed_pass", "exposure"),
    ("exposure_to_stop", "exposure", "stop"),
    ("stop_to_attention", "stop", "attention"),
    ("attention_to_linked_entry", "attention", "linked_entry"),
)
_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class FunnelStageDraft:
    stage: str
    count: int | None
    availability: str
    label: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class FunnelRateDraft:
    code: str
    value: Decimal | None
    availability: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class FunnelDraft:
    stop_threshold_seconds: Decimal
    attention_threshold_seconds: Decimal
    excluded_window_only: int
    precision_uncommitted: bool
    stages: tuple[FunnelStageDraft, ...]
    rates: tuple[FunnelRateDraft, ...]


def build_funnel(
    events: Sequence[SceneEventFact],
    *,
    shop_id: uuid.UUID,
    window_configured: bool,
    fps: float,
) -> FunnelDraft:
    """Count each track once per stage. Rates are named by the two stages they join."""

    own = [event for event in events if event.shop_id == shop_id]
    front = {
        event.track_id
        for event in own
        if event.kind == "zone_enter" and event.zone_role == "front"
    }
    window = {
        event.track_id
        for event in own
        if event.kind == "zone_enter" and event.zone_role == "window"
    }
    excluded = len(window - front)
    observed = len(front)
    if window_configured:
        exposure_ids = front & window
        stops = [
            event
            for event in own
            if event.kind == "showcase_stop"
            and event.track_id in exposure_ids
            and event.duration_seconds is not None
            and event.duration_seconds >= STOP_THRESHOLD_SECONDS
        ]
        stop_ids = {event.track_id for event in stops}
        attention_starts = _attention_starts(stops, fps)
        linked = _linked_entries(own, attention_starts, fps)
        stages = (
            _available("observed_pass", observed),
            _available("exposure", len(exposure_ids)),
            _available("stop", len(stop_ids)),
            _available(
                "attention",
                len(attention_starts),
                label="attention_estimate",
            ),
            _available("linked_entry", len(linked)),
        )
    else:
        stages = (
            _available("observed_pass", observed),
            _missing("exposure"),
            _missing("stop"),
            _missing("attention"),
            _missing("linked_entry"),
        )
    by_stage = {stage.stage: stage for stage in stages}
    rates = tuple(
        _rate(code, by_stage[previous], by_stage[later]) for code, previous, later in _RATE_PAIRS
    )
    return FunnelDraft(
        stop_threshold_seconds=STOP_THRESHOLD_SECONDS,
        attention_threshold_seconds=ATTENTION_THRESHOLD_SECONDS,
        excluded_window_only=excluded,
        precision_uncommitted=True,
        stages=stages,
        rates=rates,
    )


def _attention_starts(stops: Sequence[SceneEventFact], fps: float) -> dict[int, Decimal]:
    starts: dict[int, Decimal] = {}
    scale = Decimal(str(fps))
    for event in stops:
        if event.duration_seconds is None or event.duration_seconds < ATTENTION_THRESHOLD_SECONDS:
            continue
        start = Decimal(event.frame_index) / scale - event.duration_seconds
        current = starts.get(event.track_id)
        if current is None or start < current:
            starts[event.track_id] = start
    return starts


def _linked_entries(
    events: Sequence[SceneEventFact], starts: dict[int, Decimal], fps: float
) -> set[int]:
    if not starts:
        return set()
    scale = Decimal(str(fps))
    linked: set[int] = set()
    for event in events:
        start = starts.get(event.track_id)
        if event.kind != "store_enter" or start is None:
            continue
        if Decimal(event.frame_index) / scale > start:
            linked.add(event.track_id)
    return linked


def _available(stage: str, count: int, *, label: str = "none") -> FunnelStageDraft:
    return FunnelStageDraft(stage, count, "available", label, None)


def _missing(stage: str) -> FunnelStageDraft:
    return FunnelStageDraft(stage, None, "unavailable", "none", "no_showcase")


def _rate(code: str, previous: FunnelStageDraft, later: FunnelStageDraft) -> FunnelRateDraft:
    if previous.availability != "available" or later.availability != "available":
        return FunnelRateDraft(code, None, "unavailable", "no_showcase")
    if previous.count == 0:
        return FunnelRateDraft(code, None, "unavailable", "no_previous_stage")
    value = (Decimal(later.count or 0) / Decimal(previous.count)).quantize(_QUANTUM)
    return FunnelRateDraft(code, value, "available", None)
