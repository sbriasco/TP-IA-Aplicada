"""Stored figures for one session and shop. Does not calculate metrics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    JobKind,
    JobStatus,
    LiveAnalysisState,
    LiveCrossingBucket,
    ProcessingJob,
    SceneVersionShop,
    SourceKind,
)
from flowsight.services.funnel import LiveFunnelUnavailable, load_shop_funnel
from flowsight.services.possible_purchase import (
    LivePurchaseUnavailable,
    load_possible_purchase,
)
from flowsight.services.scene_metrics import ResultIncomplete, ShopNotInSession, load_shop_metrics
from flowsight.services.sessions import get_active_session
from flowsight.services.visit_patterns import LivePatternsUnavailable, load_visit_patterns
from flowsight.vision.metrics import MetricValue

FIGURE_CODES = (
    "traffic_total",
    "entries",
    "exits",
    "store_pass",
    "entry_rate",
    "visible_occupancy",
    "dwell_mean_seconds",
    "dwell_median_seconds",
)
LIVE_FIGURE_CODES = (
    "total_crossings",
    "entries",
    "exits",
    "dwell_interior_mean_seconds",
    "dwell_front_mean_seconds",
    "coverage_percent",
    "elapsed_capture_seconds",
)
_TERMINAL_LIVE = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)
_LABELS = {
    "traffic_total": "visit_estimate",
    "visible_occupancy": "visible",
    "dwell_mean_seconds": "observable",
    "dwell_median_seconds": "observable",
    "dwell_interior_mean_seconds": "observable",
    "dwell_front_mean_seconds": "observable",
}
_ESTIMATION_CODES = frozenset(
    {"traffic_total", "group_count", "visit_count", "funnel_entries"}
)


class AnalysisNotFinal(Exception):
    """The latest analysis cannot be cited as a final result."""


class LiveChatUnavailable(Exception):
    """Live chat is only available for a saved webcam report."""


@dataclass(frozen=True)
class ChatFigure:
    code: str
    label: str
    availability: str
    value: Decimal | None
    unavailable_reason: str | None
    start_seconds: Decimal | None = None
    track_count: int | None = None
    bucket_index: int | None = None
    estimation: bool = False


def ensure_chat_source(database_session, session_id):
    """Allow video always; webcam only when the live job has a saved report."""

    session = get_active_session(database_session, session_id)
    if session is None or session.source_kind != SourceKind.WEBCAM:
        return
    job = _latest_live_job(database_session, session_id)
    if job is None or job.status not in _TERMINAL_LIVE:
        raise LiveChatUnavailable


def read_figures(
    database_session: DatabaseSession,
    session_id: uuid.UUID,
    shop_id: uuid.UUID,
    *,
    from_seconds: Decimal | None = None,
    to_seconds: Decimal | None = None,
) -> list[ChatFigure]:
    """Return the closed catalog for the whole session (stretch ignored)."""

    del from_seconds, to_seconds
    ensure_chat_source(database_session, session_id)
    session = get_active_session(database_session, session_id)
    if session is not None and session.source_kind == SourceKind.WEBCAM:
        return _read_live_figures(database_session, session_id, shop_id)
    try:
        rows, flow, peak = load_shop_metrics(database_session, session_id, shop_id)
    except ResultIncomplete as error:
        raise AnalysisNotFinal from error
    by_code = {row.code: row for row in rows}
    figures = [
        _figure(by_code[code]) if code in by_code else _missing(code) for code in FIGURE_CODES
    ]
    figures.append(
        ChatFigure(
            code="peak",
            label="none",
            availability="available" if flow else "unavailable",
            value=None,
            unavailable_reason=None if flow else "metrics_not_generated",
            start_seconds=peak.start_seconds if flow else None,
            track_count=peak.track_count if flow else None,
            bucket_index=peak.bucket_index if flow else None,
        )
    )
    figures.append(_optional_funnel(database_session, session_id, shop_id))
    figures.append(_optional_patterns(database_session, session_id))
    figures.append(_optional_purchase(database_session, session_id))
    return figures


def _read_live_figures(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> list[ChatFigure]:
    job = _latest_live_job(database_session, session_id)
    if job is None or job.status not in _TERMINAL_LIVE:
        raise LiveChatUnavailable
    state = database_session.get(LiveAnalysisState, job.id)
    if state is None:
        raise AnalysisNotFinal
    version_shop = database_session.scalar(
        select(SceneVersionShop).where(
            SceneVersionShop.scene_version_id == job.scene_version_id,
            SceneVersionShop.shop_id == shop_id,
        )
    )
    if version_shop is None:
        raise ShopNotInSession
    entries, exits = database_session.execute(
        select(
            func.coalesce(func.sum(LiveCrossingBucket.entries), 0),
            func.coalesce(func.sum(LiveCrossingBucket.exits), 0),
        ).where(LiveCrossingBucket.job_id == job.id, LiveCrossingBucket.shop_id == shop_id)
    ).one()
    buckets = list(
        database_session.scalars(
            select(LiveCrossingBucket)
            .where(
                LiveCrossingBucket.job_id == job.id,
                LiveCrossingBucket.shop_id == shop_id,
            )
            .order_by(LiveCrossingBucket.bucket_index)
        )
    )
    dwell = _zone_dwell_for_shop(state.zone_dwell, shop_id)
    elapsed = Decimal(str(state.elapsed_capture_seconds))
    observed = Decimal(str(state.observed_seconds))
    figures = [
        _count_figure("total_crossings", int(entries) + int(exits)),
        _count_figure("entries", int(entries)),
        _count_figure("exits", int(exits)),
        _dwell_figure("dwell_interior_mean_seconds", dwell, "interior"),
        _dwell_figure("dwell_front_mean_seconds", dwell, "front"),
        _coverage_figure(observed, elapsed),
        ChatFigure(
            code="elapsed_capture_seconds",
            label="none",
            availability="available",
            value=elapsed,
            unavailable_reason=None,
        ),
        _live_peak(buckets),
        _missing("funnel_entries", estimation=True),
        _missing("group_count", estimation=True),
        _missing("visit_count", estimation=True),
    ]
    return figures


def _latest_live_job(
    database_session: DatabaseSession, session_id: uuid.UUID
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.session_id == session_id,
            ProcessingJob.kind == JobKind.LIVE_ANALYSIS,
        )
        .order_by(ProcessingJob.created_at.desc())
    )


def _zone_dwell_for_shop(zone_dwell: object, shop_id: uuid.UUID) -> dict[str, object]:
    if not isinstance(zone_dwell, dict):
        return {}
    raw = zone_dwell.get(str(shop_id))
    return raw if isinstance(raw, dict) else {}


def _count_figure(code: str, value: int) -> ChatFigure:
    return ChatFigure(
        code=code,
        label="none",
        availability="available",
        value=Decimal(value),
        unavailable_reason=None,
    )


def _dwell_figure(code: str, dwell: dict[str, object], side: str) -> ChatFigure:
    average_key = f"{side}_average_seconds"
    sample_key = f"{side}_sample_count"
    average = dwell.get(average_key)
    samples = dwell.get(sample_key)
    if average is None or samples is None or int(samples) <= 0:
        return ChatFigure(
            code=code,
            label=_LABELS.get(code, "observable"),
            availability="unavailable",
            value=None,
            unavailable_reason="no_closed_dwells",
        )
    return ChatFigure(
        code=code,
        label=_LABELS.get(code, "observable"),
        availability="available",
        value=Decimal(str(average)),
        unavailable_reason=None,
        track_count=int(samples),
    )


def _coverage_figure(observed: Decimal, elapsed: Decimal) -> ChatFigure:
    if elapsed <= 0:
        return ChatFigure(
            code="coverage_percent",
            label="none",
            availability="unavailable",
            value=None,
            unavailable_reason="metrics_not_generated",
        )
    percent = (observed / elapsed * Decimal(100)).quantize(Decimal("0.1"))
    return ChatFigure(
        code="coverage_percent",
        label="none",
        availability="available",
        value=percent,
        unavailable_reason=None,
    )


def _live_peak(buckets: list[LiveCrossingBucket]) -> ChatFigure:
    if not buckets:
        return ChatFigure(
            code="peak",
            label="none",
            availability="unavailable",
            value=None,
            unavailable_reason="metrics_not_generated",
        )
    peak = max(buckets, key=lambda row: (row.entries + row.exits, -row.bucket_index))
    crossings = peak.entries + peak.exits
    if crossings <= 0:
        return ChatFigure(
            code="peak",
            label="none",
            availability="unavailable",
            value=None,
            unavailable_reason="metrics_not_generated",
        )
    return ChatFigure(
        code="peak",
        label="none",
        availability="available",
        value=None,
        unavailable_reason=None,
        start_seconds=Decimal(str(peak.start_seconds)),
        track_count=crossings,
        bucket_index=peak.bucket_index,
    )


def _optional_funnel(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> ChatFigure:
    try:
        view = load_shop_funnel(database_session, session_id, shop_id)
    except (ResultIncomplete, LiveFunnelUnavailable):
        return _missing("funnel_entries", estimation=True)
    from flowsight.db.models import ShopFunnelStageCode

    stage = next(
        (row for row in view.stages if row.stage == ShopFunnelStageCode.LINKED_ENTRY),
        None,
    )
    if stage is None or stage.availability.value != "available" or stage.count is None:
        return ChatFigure(
            code="funnel_entries",
            label="none",
            availability="unavailable",
            value=None,
            unavailable_reason="funnel_unavailable",
            estimation=True,
        )
    return ChatFigure(
        code="funnel_entries",
        label="none",
        availability="available",
        value=Decimal(stage.count),
        unavailable_reason=None,
        estimation=True,
    )


def _optional_patterns(database_session: DatabaseSession, session_id: uuid.UUID) -> ChatFigure:
    try:
        view = load_visit_patterns(database_session, session_id)
    except (ResultIncomplete, LivePatternsUnavailable):
        return _missing("group_count", estimation=True)
    if view.report.groups_availability.value != "available":
        return ChatFigure(
            code="group_count",
            label="none",
            availability="unavailable",
            value=None,
            unavailable_reason=view.report.patterns_unavailable_reason or "patterns_unavailable",
            estimation=True,
        )
    return ChatFigure(
        code="group_count",
        label="none",
        availability="available",
        value=Decimal(view.report.group_count),
        unavailable_reason=None,
        estimation=True,
    )


def _optional_purchase(database_session: DatabaseSession, session_id: uuid.UUID) -> ChatFigure:
    try:
        view = load_possible_purchase(database_session, session_id)
    except (ResultIncomplete, LivePurchaseUnavailable):
        return _missing("visit_count", estimation=True)
    return ChatFigure(
        code="visit_count",
        label="none",
        availability="available",
        value=Decimal(view.report.visit_count),
        unavailable_reason=None,
        estimation=True,
    )


def _missing(code: str, *, estimation: bool | None = None) -> ChatFigure:
    return ChatFigure(
        code=code,
        label=_LABELS.get(code, "none"),
        availability="unavailable",
        value=None,
        unavailable_reason="metrics_not_generated",
        estimation=code in _ESTIMATION_CODES if estimation is None else estimation,
    )


def _figure(row: MetricValue) -> ChatFigure:
    return ChatFigure(
        code=row.code,
        label=row.label,
        availability=row.availability,
        value=row.value,
        unavailable_reason=row.unavailable_reason,
        estimation=row.code in _ESTIMATION_CODES or row.label == "visit_estimate",
    )
