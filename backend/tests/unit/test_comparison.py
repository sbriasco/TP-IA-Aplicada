"""Pure comparison helpers: relations, insights, no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone

from flowsight.services.comparison import (
    ColumnData,
    ComparisonCellData,
    ContrastedFigureData,
    _utc_calendar_day,
    build_insights,
    relation_and_delta,
)


def _cell(value: float | None, *, available: bool = True, reason: str | None = None):
    if available and value is not None:
        return ComparisonCellData("available", value, None)
    return ComparisonCellData("unavailable", None, reason or "unavailable")


def _figure(code: str, left: float | None, right: float | None, *, family="shop_metrics"):
    cells = (_cell(left, available=left is not None), _cell(right, available=right is not None))
    relation, delta = relation_and_delta(cells[0], cells[1])
    return ContrastedFigureData(family, code, code, cells, relation, delta)


def _columns() -> tuple[ColumnData, ColumnData]:
    return (
        ColumnData(
            key="a",
            label="Sesión A",
            session_ids=(uuid.uuid4(),),
            camera_label="Cam",
            resolved_shop_id=None,
            registered_camera_id=None,
            finished_day=None,
        ),
        ColumnData(
            key="b",
            label="Sesión B",
            session_ids=(uuid.uuid4(),),
            camera_label="Cam",
            resolved_shop_id=None,
            registered_camera_id=None,
            finished_day=None,
        ),
    )


def test_relation_both_available():
    assert relation_and_delta(_cell(10), _cell(3)) == ("greater", 7.0)
    assert relation_and_delta(_cell(2), _cell(5)) == ("less", -3.0)
    assert relation_and_delta(_cell(4), _cell(4)) == ("equal", 0.0)


def test_relation_unavailable_not_zero():
    relation, delta = relation_and_delta(_cell(None, available=False), _cell(0))
    assert relation == "unavailable"
    assert delta is None


def test_zero_available_is_real_zero():
    relation, delta = relation_and_delta(_cell(0), _cell(5))
    assert relation == "less"
    assert delta == -5.0


def test_insights_higher_traffic():
    figures = (_figure("traffic_total", 20, 5),)
    insights = build_insights(figures, _columns())
    assert insights[0].code == "higher_traffic_total"
    assert "Sesión A" in insights[0].message
    assert insights[0].estimation is True


def test_insights_no_highlights_when_tied_or_missing():
    figures = (_figure("traffic_total", 5, 5), _figure("entry_rate", None, 1))
    insights = build_insights(figures, _columns())
    assert insights[0].code == "no_highlights"


def test_day_axis_uses_utc_calendar_not_local():
    # 02:00 UTC on 1 Sep is still 31 Aug in UTC−3; grouping must keep UTC date.
    finished = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
    assert _utc_calendar_day(finished).isoformat() == "2026-09-01"
    local_minus_three = timezone(timedelta(hours=-3))
    as_local = finished.astimezone(local_minus_three)
    assert as_local.date().isoformat() == "2026-08-31"
    assert _utc_calendar_day(as_local).isoformat() == "2026-09-01"


def test_additive_metric_codes_exclude_rates():
    from flowsight.services.comparison import _ADDITIVE_METRIC_CODES

    assert "traffic_total" in _ADDITIVE_METRIC_CODES
    assert "entries" in _ADDITIVE_METRIC_CODES
    assert "entry_rate" not in _ADDITIVE_METRIC_CODES
    assert "dwell_mean_seconds" not in _ADDITIVE_METRIC_CODES
    assert "visible_occupancy" not in _ADDITIVE_METRIC_CODES


def test_funnel_stage_uses_linked_entry_enum():
    import inspect

    from flowsight.db.models import ShopFunnelStageCode
    from flowsight.services import comparison as comparison_mod

    source = inspect.getsource(comparison_mod._optional_funnel)
    assert "ShopFunnelStageCode.LINKED_ENTRY" in source
    assert ShopFunnelStageCode.LINKED_ENTRY.value == "linked_entry"
