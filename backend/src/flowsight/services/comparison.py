"""Read-only multi-session comparison and deterministic insights."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    Camera,
    JobStatus,
    ProcessingJob,
    SceneVersionShop,
    Session,
    ShopFunnelStageCode,
    ShopMetricCode,
    SourceKind,
)
from flowsight.services.cameras import normalize_name_key
from flowsight.services.funnel import LiveFunnelUnavailable, load_shop_funnel
from flowsight.services.possible_purchase import (
    LivePurchaseUnavailable,
    load_possible_purchase,
)
from flowsight.services.scene_metrics import ResultIncomplete, load_shop_metrics
from flowsight.services.sessions import get_active_session
from flowsight.services.visit_patterns import LivePatternsUnavailable, load_visit_patterns

ComparisonAxis = Literal["session", "day", "time_of_day", "zone"]
Relation = Literal["greater", "less", "equal", "unavailable"]
FigureFamily = Literal[
    "shop_metrics", "peak", "funnel", "visit_patterns", "possible_purchase"
]

_METRIC_LABELS: dict[str, str] = {
    "traffic_total": "Tráfico (estimación de visitas)",
    "store_pass": "Paso frente al local",
    "entries": "Entradas",
    "exits": "Salidas",
    "entry_rate": "Tasa de ingreso",
    "dwell_mean_seconds": "Permanencia media (s)",
    "dwell_median_seconds": "Permanencia mediana (s)",
    "visible_occupancy": "Ocupación visible",
    "peak_track_count": "Horario pico (visitas en franja)",
    "group_count": "Grupos estimados",
    "visit_count": "Posible compra estimada (visitas)",
    "funnel_entries": "Funnel: entradas vinculadas",
}

# Count-like codes that may be summed across sessions in a P2 group.
_ADDITIVE_METRIC_CODES = frozenset(
    {
        ShopMetricCode.TRAFFIC_TOTAL.value,
        ShopMetricCode.STORE_PASS.value,
        ShopMetricCode.ENTRIES.value,
        ShopMetricCode.EXITS.value,
    }
)


class ComparisonInvalidRequest(ValueError):
    """Missing or invalid comparison request fields."""


class ComparisonInsufficientSessions(ValueError):
    """Fewer than two eligible completed file sessions after filtering."""


class ComparisonAxisUnavailable(ValueError):
    """P2 axis has fewer than two comparable groups."""


@dataclass(frozen=True)
class ComparisonCellData:
    availability: Literal["available", "unavailable"]
    value: float | None
    unavailable_reason: str | None
    start_seconds: float | None = None


@dataclass(frozen=True)
class ContrastedFigureData:
    family: FigureFamily
    code: str
    label: str
    cells: tuple[ComparisonCellData, ...]
    relation: Relation
    delta: float | None


@dataclass(frozen=True)
class InsightData:
    code: str
    message: str
    figure_code: str | None
    estimation: bool


@dataclass(frozen=True)
class ColumnData:
    key: str
    label: str
    session_ids: tuple[uuid.UUID, ...]
    camera_label: str | None
    resolved_shop_id: uuid.UUID | None
    registered_camera_id: uuid.UUID | None
    finished_day: date | None


@dataclass(frozen=True)
class ComparisonResult:
    axis: ComparisonAxis
    zone_name: str
    columns: tuple[ColumnData, ...]
    figures: tuple[ContrastedFigureData, ...]
    insights: tuple[InsightData, ...]


@dataclass(frozen=True)
class _EligibleSession:
    session: Session
    job: ProcessingJob
    camera_label: str | None
    shop_id: uuid.UUID | None
    peak_start_seconds: float | None


def relation_and_delta(
    left: ComparisonCellData, right: ComparisonCellData
) -> tuple[Relation, float | None]:
    """Compare the first column to the second when both values are available."""

    if (
        left.availability != "available"
        or right.availability != "available"
        or left.value is None
        or right.value is None
    ):
        return "unavailable", None
    delta = left.value - right.value
    if delta > 0:
        return "greater", delta
    if delta < 0:
        return "less", delta
    return "equal", 0.0


def build_insights(
    figures: tuple[ContrastedFigureData, ...],
    columns: tuple[ColumnData, ...],
) -> tuple[InsightData, ...]:
    """Deterministic highlights from contrasted figures. No LLM."""

    if len(columns) < 2:
        return (_no_highlights(),)
    left_label = columns[0].label
    right_label = columns[1].label
    highlights: list[InsightData] = []
    priority = ("traffic_total", "entry_rate", "visit_count", "group_count", "peak_track_count")
    by_code = {figure.code: figure for figure in figures}
    for code in priority:
        figure = by_code.get(code)
        if figure is None or figure.relation in {"unavailable", "equal"} or len(figure.cells) < 2:
            continue
        estimation = code in {"traffic_total", "visit_count", "group_count"} or figure.family in {
            "possible_purchase",
            "visit_patterns",
        }
        winner = left_label if figure.relation == "greater" else right_label
        loser = right_label if figure.relation == "greater" else left_label
        highlights.append(
            InsightData(
                code=f"higher_{code}",
                message=f"{winner} tiene mayor {figure.label} que {loser}.",
                figure_code=code,
                estimation=estimation,
            )
        )
        if len(highlights) >= 3:
            break
    return tuple(highlights) if highlights else (_no_highlights(),)


def _no_highlights() -> InsightData:
    return InsightData(
        code="no_highlights",
        message="No hay diferencias destacables o faltan datos.",
        figure_code=None,
        estimation=False,
    )


def build_comparison(
    database_session: DatabaseSession,
    *,
    session_ids: list[uuid.UUID],
    zone_name: str,
    axis: ComparisonAxis,
) -> ComparisonResult:
    if not zone_name.strip():
        raise ComparisonInvalidRequest("zone_name is required")
    if axis not in {"session", "day", "time_of_day", "zone"}:
        raise ComparisonInvalidRequest("axis is not recognized")
    if not session_ids:
        raise ComparisonInvalidRequest("session_ids is required")

    ordered_unique = list(dict.fromkeys(session_ids))
    eligible: list[_EligibleSession] = []
    for session_id in ordered_unique:
        row = _load_eligible(database_session, session_id, zone_name)
        if row is not None:
            eligible.append(row)
    if len(eligible) < 2:
        raise ComparisonInsufficientSessions("need at least two eligible sessions")

    if axis == "session":
        columns = tuple(_column_from_eligible(row) for row in eligible)
    else:
        columns = _group_columns(database_session, eligible, axis, zone_name)
        if len(columns) < 2:
            raise ComparisonAxisUnavailable(f"axis {axis} has insufficient groups")

    figures = _assemble_figures(database_session, columns, zone_name)
    insights = build_insights(figures, columns)
    return ComparisonResult(
        axis=axis,
        zone_name=zone_name.strip(),
        columns=columns,
        figures=figures,
        insights=insights,
    )


def _load_eligible(
    database_session: DatabaseSession, session_id: uuid.UUID, zone_name: str
) -> _EligibleSession | None:
    flow = get_active_session(database_session, session_id)
    if flow is None or flow.source_kind == SourceKind.WEBCAM:
        return None
    job = database_session.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.session_id == session_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    if job is None or job.status != JobStatus.COMPLETED or not job.result_complete:
        return None
    camera = database_session.get(Camera, flow.registered_camera_id)
    shop_id = _resolve_shop_id(database_session, job, zone_name)
    peak_start: float | None = None
    if shop_id is not None:
        try:
            _rows, _flow, peak = load_shop_metrics(database_session, session_id, shop_id)
            peak_start = float(peak.start_seconds)
        except ResultIncomplete:
            peak_start = None
    return _EligibleSession(
        session=flow,
        job=job,
        camera_label=None if camera is None else camera.name,
        shop_id=shop_id,
        peak_start_seconds=peak_start,
    )


def _resolve_shop_id(
    database_session: DatabaseSession, job: ProcessingJob, zone_name: str
) -> uuid.UUID | None:
    if job.scene_version_id is None:
        return None
    key = normalize_name_key(zone_name)
    return database_session.scalar(
        select(SceneVersionShop.shop_id).where(
            SceneVersionShop.scene_version_id == job.scene_version_id,
            SceneVersionShop.name_key == key,
        )
    )


def _utc_calendar_day(finished_at: datetime) -> date:
    """Calendar date of analysis close in UTC (FR-004 day axis)."""

    return finished_at.astimezone(UTC).date()


def _column_from_eligible(row: _EligibleSession) -> ColumnData:
    finished = row.job.finished_at
    day = None if finished is None else _utc_calendar_day(finished)
    return ColumnData(
        key=f"session:{row.session.id}",
        label=row.session.name,
        session_ids=(row.session.id,),
        camera_label=row.camera_label,
        resolved_shop_id=row.shop_id,
        registered_camera_id=row.session.registered_camera_id,
        finished_day=day,
    )


def _group_columns(
    database_session: DatabaseSession,
    eligible: list[_EligibleSession],
    axis: ComparisonAxis,
    zone_name: str,
) -> tuple[ColumnData, ...]:
    del database_session  # reserved for future wall-clock helpers
    buckets: dict[str, list[_EligibleSession]] = {}
    for row in eligible:
        key = _group_key(row, axis, zone_name)
        if key is None:
            continue
        buckets.setdefault(key, []).append(row)
    columns: list[ColumnData] = []
    for key, rows in buckets.items():
        first = rows[0]
        columns.append(
            ColumnData(
                key=f"{axis}:{key}",
                label=_group_label(key, axis, first),
                session_ids=tuple(item.session.id for item in rows),
                camera_label=first.camera_label,
                resolved_shop_id=first.shop_id,
                registered_camera_id=first.session.registered_camera_id,
                finished_day=None
                if first.job.finished_at is None
                else _utc_calendar_day(first.job.finished_at),
            )
        )
    return tuple(columns)


def _group_key(row: _EligibleSession, axis: ComparisonAxis, zone_name: str) -> str | None:
    if axis == "day":
        if row.job.finished_at is None:
            return None
        return _utc_calendar_day(row.job.finished_at).isoformat()
    if axis == "time_of_day":
        # Video-time fringe: hour bucket of the session peak start_seconds.
        if row.peak_start_seconds is None:
            return None
        hour = int(row.peak_start_seconds // 3600)
        return f"{hour:02d}h"
    if axis == "zone":
        if row.shop_id is None:
            return None
        # Same camera + zone name (zone_name already matched); do not merge cameras.
        return f"{row.session.registered_camera_id}:{normalize_name_key(zone_name)}"
    return None


def _group_label(key: str, axis: ComparisonAxis, first: _EligibleSession) -> str:
    if axis == "day":
        return key
    if axis == "time_of_day":
        return f"Franja {key}"
    if axis == "zone":
        return first.camera_label or key
    return key


@dataclass
class _ColumnValues:
    metrics: dict[str, ComparisonCellData]
    peak: ComparisonCellData
    funnel_entries: ComparisonCellData
    group_count: ComparisonCellData
    visit_count: ComparisonCellData


def _assemble_figures(
    database_session: DatabaseSession,
    columns: tuple[ColumnData, ...],
    zone_name: str,
) -> tuple[ContrastedFigureData, ...]:
    per_column = [_load_column_values(database_session, column, zone_name) for column in columns]
    figures: list[ContrastedFigureData] = []

    for code in ShopMetricCode:
        cells = tuple(
            values.metrics.get(code.value, _unavailable("metric_missing")) for values in per_column
        )
        figures.append(_figure("shop_metrics", code.value, _METRIC_LABELS[code.value], cells))

    peak_cells = tuple(values.peak for values in per_column)
    figures.append(
        _figure("peak", "peak_track_count", _METRIC_LABELS["peak_track_count"], peak_cells)
    )

    optional: list[tuple[FigureFamily, str, str]] = [
        ("funnel", "funnel_entries", _METRIC_LABELS["funnel_entries"]),
        ("visit_patterns", "group_count", _METRIC_LABELS["group_count"]),
        ("possible_purchase", "visit_count", _METRIC_LABELS["visit_count"]),
    ]
    for family, code, label in optional:
        cells = tuple(getattr(values, code) for values in per_column)
        if any(cell.availability == "available" for cell in cells):
            figures.append(_figure(family, code, label, cells))

    return tuple(figures)


def _load_column_values(
    database_session: DatabaseSession, column: ColumnData, zone_name: str
) -> _ColumnValues:
    if len(column.session_ids) == 1:
        session_id = column.session_ids[0]
        shop_id = column.resolved_shop_id
        if shop_id is None:
            missing = _unavailable("zone_not_in_scene")
            return _ColumnValues(
                metrics={code.value: missing for code in ShopMetricCode},
                peak=missing,
                funnel_entries=missing,
                group_count=_optional_patterns(database_session, session_id),
                visit_count=_optional_purchase(database_session, session_id),
            )
        metrics, peak = _metrics_for_session(database_session, session_id, shop_id)
        return _ColumnValues(
            metrics=metrics,
            peak=peak,
            funnel_entries=_optional_funnel(database_session, session_id, shop_id),
            group_count=_optional_patterns(database_session, session_id),
            visit_count=_optional_purchase(database_session, session_id),
        )

    metrics, peak = _aggregate_metrics(database_session, column.session_ids, zone_name)
    unavailable = _unavailable("group_optional_unavailable")
    return _ColumnValues(
        metrics=metrics,
        peak=peak,
        funnel_entries=unavailable,
        group_count=unavailable,
        visit_count=unavailable,
    )


def _metrics_for_session(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> tuple[dict[str, ComparisonCellData], ComparisonCellData]:
    try:
        rows, _flow, peak = load_shop_metrics(database_session, session_id, shop_id)
    except ResultIncomplete:
        missing = _unavailable("result_incomplete")
        return {code.value: missing for code in ShopMetricCode}, missing
    by_code = {row.code: row for row in rows}
    metrics: dict[str, ComparisonCellData] = {}
    for code in ShopMetricCode:
        row = by_code.get(code.value)
        if row is None:
            metrics[code.value] = _unavailable("metric_missing")
        elif row.availability != "available" or row.value is None:
            metrics[code.value] = _unavailable(row.unavailable_reason or "unavailable")
        else:
            metrics[code.value] = ComparisonCellData(
                availability="available",
                value=float(row.value),
                unavailable_reason=None,
            )
    return metrics, ComparisonCellData(
        availability="available",
        value=float(peak.track_count),
        unavailable_reason=None,
        start_seconds=float(peak.start_seconds),
    )


def _aggregate_metrics(
    database_session: DatabaseSession,
    session_ids: tuple[uuid.UUID, ...],
    zone_name: str,
) -> tuple[dict[str, ComparisonCellData], ComparisonCellData]:
    """Combine session metrics for a P2 group.

    Count metrics are summed only when every session in the group contributes an
    available value. Rates, means and occupancy are not additive across sessions.
    """

    expected = len(session_ids)
    sums: dict[str, float] = {code: 0.0 for code in _ADDITIVE_METRIC_CODES}
    seen_count: dict[str, int] = {code.value: 0 for code in ShopMetricCode}
    single: dict[str, ComparisonCellData] = {}
    peak_count = 0.0
    peak_start: float | None = None
    peak_seen = 0
    for session_id in session_ids:
        job = database_session.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.session_id == session_id)
            .order_by(ProcessingJob.created_at.desc())
        )
        if job is None:
            continue
        shop_id = _resolve_shop_id(database_session, job, zone_name)
        if shop_id is None:
            continue
        metrics, peak = _metrics_for_session(database_session, session_id, shop_id)
        for code, cell in metrics.items():
            if cell.availability != "available" or cell.value is None:
                continue
            seen_count[code] += 1
            if code in _ADDITIVE_METRIC_CODES:
                sums[code] += cell.value
            elif seen_count[code] == 1:
                single[code] = cell
        if peak.availability == "available" and peak.value is not None:
            peak_seen += 1
            if peak.value > peak_count:
                peak_count = peak.value
                peak_start = peak.start_seconds
    out: dict[str, ComparisonCellData] = {}
    for code in ShopMetricCode:
        key = code.value
        if key in _ADDITIVE_METRIC_CODES:
            if seen_count[key] == expected:
                out[key] = ComparisonCellData("available", sums[key], None)
            elif seen_count[key] == 0:
                out[key] = _unavailable("metric_missing")
            else:
                out[key] = _unavailable("group_incomplete")
        elif seen_count[key] == 1 and expected == 1:
            out[key] = single[key]
        elif seen_count[key] > 1 or (seen_count[key] == 1 and expected > 1):
            out[key] = _unavailable("group_non_additive")
        else:
            out[key] = _unavailable("metric_missing")
    if peak_seen == expected:
        peak_cell = ComparisonCellData("available", peak_count, None, peak_start)
    elif peak_seen == 0:
        peak_cell = _unavailable("peak_unavailable")
    else:
        peak_cell = _unavailable("group_incomplete")
    return out, peak_cell


def _optional_funnel(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> ComparisonCellData:
    try:
        view = load_shop_funnel(database_session, session_id, shop_id)
    except (ResultIncomplete, LiveFunnelUnavailable):
        return _unavailable("funnel_unavailable")
    stage = next(
        (row for row in view.stages if row.stage == ShopFunnelStageCode.LINKED_ENTRY),
        None,
    )
    if stage is None or stage.availability.value != "available" or stage.count is None:
        return _unavailable("funnel_unavailable")
    return ComparisonCellData("available", float(stage.count), None)


def _optional_patterns(
    database_session: DatabaseSession, session_id: uuid.UUID
) -> ComparisonCellData:
    try:
        view = load_visit_patterns(database_session, session_id)
    except (ResultIncomplete, LivePatternsUnavailable):
        return _unavailable("patterns_unavailable")
    if view.report.groups_availability.value != "available":
        return _unavailable(view.report.patterns_unavailable_reason or "patterns_unavailable")
    return ComparisonCellData("available", float(view.report.group_count), None)


def _optional_purchase(
    database_session: DatabaseSession, session_id: uuid.UUID
) -> ComparisonCellData:
    try:
        view = load_possible_purchase(database_session, session_id)
    except (ResultIncomplete, LivePurchaseUnavailable):
        return _unavailable("purchase_unavailable")
    return ComparisonCellData("available", float(view.report.visit_count), None)


def _unavailable(reason: str) -> ComparisonCellData:
    return ComparisonCellData(availability="unavailable", value=None, unavailable_reason=reason)


def _figure(
    family: FigureFamily,
    code: str,
    label: str,
    cells: tuple[ComparisonCellData, ...],
) -> ContrastedFigureData:
    if len(cells) >= 2:
        relation, delta = relation_and_delta(cells[0], cells[1])
    else:
        relation, delta = "unavailable", None
    return ContrastedFigureData(
        family=family,
        code=code,
        label=label,
        cells=cells,
        relation=relation,
        delta=delta,
    )
