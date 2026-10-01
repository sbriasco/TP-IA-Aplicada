"""Five stored figures for one session and shop. Does not calculate metrics."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session as DatabaseSession

from flowsight.services.scene_metrics import ResultIncomplete, load_shop_metrics
from flowsight.vision.metrics import MetricValue

FIGURE_CODES = (
    "traffic_total",
    "entries",
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


class AnalysisNotFinal(Exception):
    """The latest analysis cannot be cited as a final result."""


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


def read_figures(
    database_session: DatabaseSession,
    session_id: uuid.UUID,
    shop_id: uuid.UUID,
    *,
    from_seconds: Decimal | None = None,
    to_seconds: Decimal | None = None,
) -> list[ChatFigure]:
    """Return the five stored figures plus the stored peak.

    A requested stretch is ignored: every figure is the whole session.
    """

    del from_seconds, to_seconds
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
    return figures


def _missing(code: str) -> ChatFigure:
    return ChatFigure(
        code=code,
        label=_LABELS.get(code, "none"),
        availability="unavailable",
        value=None,
        unavailable_reason="metrics_not_generated",
    )


def _figure(row: MetricValue) -> ChatFigure:
    return ChatFigure(
        code=row.code,
        label=row.label,
        availability=row.availability,
        value=row.value,
        unavailable_reason=row.unavailable_reason,
    )
