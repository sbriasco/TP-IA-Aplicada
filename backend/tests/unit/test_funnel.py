"""Pure funnel counts. Each track is counted once, and the existing entry rate is not here."""

from __future__ import annotations

import uuid
from decimal import Decimal

from flowsight.db.models import JobKind, JobStatus, MeasureAvailability, ProcessingJob
from flowsight.services.funnel import _missing
from flowsight.vision.events import SceneEventFact
from flowsight.vision.funnel import build_funnel

SHOP = uuid.uuid4()
OTHER = uuid.uuid4()
RATE_CODES = (
    "observed_pass_to_exposure",
    "exposure_to_stop",
    "stop_to_attention",
    "attention_to_linked_entry",
)


def _fact(
    track: int,
    kind: str,
    role: str | None = None,
    frame: int = 0,
    duration: str | None = None,
    shop: uuid.UUID = SHOP,
) -> SceneEventFact:
    return SceneEventFact(
        shop_id=shop,
        track_id=track,
        kind=kind,  # type: ignore[arg-type]
        zone_role=role,  # type: ignore[arg-type]
        frame_index=frame,
        duration_seconds=None if duration is None else Decimal(duration),
        crossing=None,
    )


def _counts(draft: object) -> dict[str, int | None]:
    return {stage.stage: stage.count for stage in draft.stages}  # type: ignore[attr-defined]


def test_funnel_counts_each_track_once_and_keeps_official_entries_separate() -> None:
    events = [
        _fact(1, "zone_enter", "front"),
        _fact(1, "dwell", "front", frame=1, duration="0.5"),
        _fact(2, "zone_enter", "front"),
        _fact(2, "dwell", "front", frame=2, duration="1"),
        _fact(3, "zone_enter", "front"),
        _fact(3, "dwell", "front", frame=10, duration="2"),
        _fact(3, "store_enter", frame=9),
        _fact(4, "zone_enter", "front"),
        _fact(4, "store_enter", frame=4),
        _fact(5, "zone_enter", "window"),
        _fact(6, "zone_enter", "front"),
        _fact(6, "dwell", "front", frame=4, duration="0.4"),
        _fact(6, "dwell", "front", frame=12, duration="2"),
        _fact(6, "store_enter", frame=11),
        _fact(7, "zone_enter", "front"),
        _fact(7, "zone_enter", "window"),
        _fact(7, "showcase_stop", "window", frame=8, duration="8"),
        _fact(8, "zone_enter", "front", shop=OTHER),
        _fact(8, "store_enter", shop=OTHER),
    ]
    official_entries = sum(
        1 for event in events if event.kind == "store_enter" and event.shop_id == SHOP
    )
    draft = build_funnel(events, shop_id=SHOP, window_configured=True, fps=1)
    assert _counts(draft) == {
        "observed_pass": 6,
        "exposure": 4,
        "stop": 3,
        "attention": 2,
        "linked_entry": 2,
    }
    assert draft.excluded_window_only == 1
    assert draft.precision_uncommitted is True
    assert draft.stop_threshold_seconds == Decimal("1")
    assert draft.attention_threshold_seconds == Decimal("2")
    assert official_entries == 3
    assert sum(1 for event in events if event.kind == "store_enter" and event.shop_id == SHOP) == 3
    assert all(stage.stage != "entries" for stage in draft.stages)
    counts = _counts(draft)
    assert counts["attention"] <= counts["stop"] <= counts["exposure"] <= counts["observed_pass"]
    assert counts["linked_entry"] <= counts["attention"]
    assert counts["linked_entry"] <= official_entries
    attention = next(stage for stage in draft.stages if stage.stage == "attention")
    assert attention.label == "attention_estimate"
    assert {rate.code for rate in draft.rates} == set(RATE_CODES)
    assert "entry_rate" not in {rate.code for rate in draft.rates}
    by_code = {rate.code: rate for rate in draft.rates}
    assert by_code["observed_pass_to_exposure"].value == Decimal("0.666667")
    assert by_code["attention_to_linked_entry"].value == Decimal("1.000000")


def test_an_entry_at_or_before_the_attention_start_is_not_linked() -> None:
    events = [
        _fact(1, "zone_enter", "front"),
        _fact(1, "dwell", "front", frame=10, duration="2"),
        _fact(1, "store_enter", frame=8),
    ]
    draft = build_funnel(events, shop_id=SHOP, window_configured=True, fps=1)
    assert _counts(draft)["attention"] == 1
    assert _counts(draft)["linked_entry"] == 0


def test_a_shop_without_a_showcase_keeps_only_the_observed_pass() -> None:
    events = [
        _fact(1, "zone_enter", "front"),
        _fact(1, "store_enter", frame=1),
    ]
    draft = build_funnel(events, shop_id=SHOP, window_configured=False, fps=1)
    observed = next(stage for stage in draft.stages if stage.stage == "observed_pass")
    assert observed.availability == "available"
    assert observed.count == 1
    missing = [stage for stage in draft.stages if stage.stage != "observed_pass"]
    assert {stage.unavailable_reason for stage in missing} == {"no_showcase"}
    assert all(stage.count is None for stage in missing)
    assert {rate.unavailable_reason for rate in draft.rates} == {"no_showcase"}
    assert all(rate.value is None for rate in draft.rates)


def test_a_zero_previous_stage_makes_the_rate_unavailable() -> None:
    draft = build_funnel([], shop_id=SHOP, window_configured=True, fps=1)
    rate = next(item for item in draft.rates if item.code == "observed_pass_to_exposure")
    assert rate.availability == "unavailable"
    assert rate.unavailable_reason == "no_previous_stage"
    assert rate.value is None


def test_a_completed_job_without_funnel_rows_does_not_invent_a_stage_reason() -> None:
    job = ProcessingJob(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        kind=JobKind.VIDEO_ANALYSIS,
        status=JobStatus.COMPLETED,
    )
    view = _missing(job, uuid.uuid4())
    assert {stage.unavailable_reason for stage in view.stages} == {None}
    assert {rate.unavailable_reason for rate in view.rates} == {None}
    assert {stage.availability for stage in view.stages} == {MeasureAvailability.UNAVAILABLE}
