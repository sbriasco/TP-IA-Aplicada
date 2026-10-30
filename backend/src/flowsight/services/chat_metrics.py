"""Stored figures for one session and shop. Does not calculate metrics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import SourceKind
from flowsight.services.funnel import LiveFunnelUnavailable, load_shop_funnel
from flowsight.services.possible_purchase import (
    LivePurchaseUnavailable,
    load_possible_purchase,
)
from flowsight.services.scene_metrics import ResultIncomplete, load_shop_metrics
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
_LABELS = {
    "traffic_total": "visit_estimate",
    "visible_occupancy": "visible",
    "dwell_mean_seconds": "observable",
    "dwell_median_seconds": "observable",
}
_ESTIMATION_CODES = frozenset(
    {"traffic_total", "group_count", "visit_count", "funnel_entries"}
)


class AnalysisNotFinal(Exception):
    """The latest analysis cannot be cited as a final result."""


class LiveChatUnavailable(Exception):
    """Live crossings do not expose the commercial chat tools."""


def ensure_chat_source(database_session, session_id):
    session = get_active_session(database_session, session_id)
    if session is not None and session.source_kind == SourceKind.WEBCAM:
        raise LiveChatUnavailable


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
