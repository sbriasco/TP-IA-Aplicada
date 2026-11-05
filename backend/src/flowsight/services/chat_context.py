"""Bounded, source-specific conversation facts from existing analytics readers.

Only explicitly selected measures enter ``numeric_values``. Identifiers, names,
pagination metadata and technical counters never authorize an answer's numbers.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import SceneVersionShop, SourceKind
from flowsight.services.chat_metrics import (
    _TERMINAL_LIVE,
    AnalysisNotFinal,
    LiveChatUnavailable,
    _latest_live_job,
    _traffic_flow_unavailable_reason,
)
from flowsight.services.funnel import LiveFunnelUnavailable, load_shop_funnel
from flowsight.services.live_results import load_live_results
from flowsight.services.possible_purchase import LivePurchaseUnavailable, load_possible_purchase
from flowsight.services.scene_metrics import ResultIncomplete, _completed_job, load_shop_metrics
from flowsight.services.sessions import get_active_session
from flowsight.services.visit_patterns import LivePatternsUnavailable, load_visit_patterns

_LIST_LIMIT = 100
_T = TypeVar("_T")


class _Snapshot:
    def __init__(self) -> None:
        self.numeric_values: set[str] = set()
        self.truncated = False

    def number(self, value: Decimal | int | float | None) -> str | int | None:
        if value is None:
            return None
        text = format(Decimal(str(value)), "f")
        self.numeric_values.add(text)
        return value if type(value) is int else text

    def bounded(
        self, values: Sequence[_T], render: Callable[[_T], object], *, has_more: bool = False
    ) -> dict[str, object]:
        items = [render(value) for value in values[:_LIST_LIMIT]]
        more = has_more or len(values) > len(items)
        self.truncated = self.truncated or more
        return {
            "items": items,
            "total": None if has_more else len(values),
            "included": len(items),
            "omitted": None if has_more else len(values) - len(items),
            "has_more": more,
        }


def read_analysis_context(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> dict[str, object]:
    """Read whole-session facts; zone metrics and session estimates keep their scopes.

    Lists contain at most 100 items. Each list reports known total/omitted counts;
    paginated webcam lists use null counts when the total is not known. Missing
    optional reports remain unavailable, and no missing count is changed to zero.
    """

    session = get_active_session(database_session, session_id)
    if session is None:
        raise AnalysisNotFinal
    snapshot = _Snapshot()
    live = session.source_kind == SourceKind.WEBCAM
    facts: dict[str, object] = {
        "scope": {
            "session_id": str(session_id),
            "selected_shop_id": str(shop_id),
            "time_range": "whole_session",
            "time_basis": "capture" if live else "video",
            "track_identity": "temporary_per_session_camera",
        }
    }
    if live:
        facts["live"] = _read_live(database_session, session_id, shop_id, snapshot)
    else:
        facts.update(_read_video(database_session, session_id, shop_id, snapshot))
    return {
        "source_kind": session.source_kind.value,
        "facts": facts,
        "numeric_values": sorted(snapshot.numeric_values),
        "truncated": snapshot.truncated,
    }


def _unavailable(scope: str, reason: str = "metrics_not_generated") -> dict[str, object]:
    return {"scope": scope, "availability": "unavailable", "unavailable_reason": reason}


def _read_video(database, session_id, shop_id, snapshot: _Snapshot) -> dict[str, object]:
    try:
        metrics, flow, _peak = load_shop_metrics(database, session_id, shop_id)
        job = _completed_job(database, session_id)
    except ResultIncomplete as error:
        raise AnalysisNotFinal from error
    names = (
        {
            str(row.shop_id): row.name
            for row in database.scalars(
                select(SceneVersionShop)
                .where(SceneVersionShop.scene_version_id == job.scene_version_id)
                .order_by(SceneVersionShop.position)
            )
        }
        if job.scene_version_id is not None
        else {}
    )

    def area(area_shop_id, role=None):
        result = {"shop_id": str(area_shop_id), "name": names.get(str(area_shop_id))}
        if role is not None:
            result["zone_role"] = role
        return result

    flow_reason = _traffic_flow_unavailable_reason(metrics, has_buckets=bool(flow))
    facts: dict[str, object] = {
        "zone_catalog": snapshot.bounded(
            list(names), lambda key: {"shop_id": key, "name": names[key]}
        ),
        "flow": {
            "scope": "selected_zone",
            "availability": "available" if flow_reason is None else "unavailable",
            "unavailable_reason": flow_reason,
            "unit": "observed_tracks_per_bucket",
            "buckets": snapshot.bounded(
                flow if flow_reason is None else [],
                lambda row: {
                    "start_seconds": snapshot.number(row.start_seconds),
                    "track_count": snapshot.number(row.track_count),
                },
            ),
        },
        "funnel": _read_funnel(database, session_id, shop_id, snapshot),
    }
    try:
        view = load_visit_patterns(database, session_id)
    except (ResultIncomplete, LivePatternsUnavailable):
        facts["patterns"] = _unavailable("session")
        facts["groups"] = _unavailable("session")
    else:
        report = view.report
        if report.patterns_availability.value != "available":
            facts["patterns"] = _unavailable("session", report.patterns_unavailable_reason)
        else:
            facts["patterns"] = {
                "scope": "session",
                "availability": "available",
                "precision_uncommitted": report.precision_uncommitted,
                "area_transitions": snapshot.bounded(
                    view.area_transitions,
                    lambda row: {
                        "from": area(row.from_shop_id, row.from_zone_role.value),
                        "to": area(row.to_shop_id, row.to_zone_role.value),
                        "track_count": snapshot.number(row.track_count),
                    },
                ),
                "shop_transitions": snapshot.bounded(
                    view.shop_transitions,
                    lambda row: {
                        "from": area(row.from_shop_id),
                        "to": area(row.to_shop_id),
                        "track_count": snapshot.number(row.track_count),
                    },
                ),
                "sequences": snapshot.bounded(
                    view.sequences,
                    lambda row: {
                        "areas": snapshot.bounded(
                            row.areas, lambda value: area(value["shop_id"], value["zone_role"])
                        ),
                        "track_count": snapshot.number(row.track_count),
                    },
                ),
            }
        if report.groups_availability.value != "available":
            facts["groups"] = _unavailable("session", "groups_unavailable")
        else:
            facts["groups"] = {
                "scope": "session",
                "availability": "available",
                "estimation": True,
                "precision_uncommitted": report.precision_uncommitted,
                "group_count": snapshot.number(report.group_count),
                "proximity_width_fraction": snapshot.number(report.proximity_width_fraction),
                "direction_degrees": snapshot.number(report.direction_degrees),
                "minimum_seconds": snapshot.number(report.minimum_seconds),
                "episodes": snapshot.bounded(
                    view.groups,
                    lambda value: {
                        "started_video_timestamp_seconds": snapshot.number(
                            value[0].started_video_timestamp_seconds
                        ),
                        "ended_video_timestamp_seconds": snapshot.number(
                            value[0].ended_video_timestamp_seconds
                        ),
                        "label": value[0].label.value,
                        "member_count": snapshot.number(len(value[1])),
                    },
                ),
            }
    facts["possible_purchase"] = _read_purchase(database, session_id, snapshot)
    return facts


def _read_funnel(database, session_id, shop_id, snapshot: _Snapshot) -> dict[str, object]:
    try:
        view = load_shop_funnel(database, session_id, shop_id)
    except (ResultIncomplete, LiveFunnelUnavailable):
        return _unavailable("selected_zone")
    available = any(row.availability.value == "available" for row in view.stages)
    if not available:
        return _unavailable("selected_zone", "funnel_unavailable")
    return {
        "scope": "selected_zone",
        "availability": "available",
        "estimation": True,
        "precision_uncommitted": view.precision_uncommitted,
        "stop_threshold_seconds": snapshot.number(view.stop_threshold_seconds),
        "attention_threshold_seconds": snapshot.number(view.attention_threshold_seconds),
        "excluded_window_only": snapshot.number(view.excluded_window_only),
        "stages": [
            {
                "stage": row.stage.value,
                "availability": row.availability.value,
                "count": snapshot.number(row.count)
                if row.availability.value == "available"
                else None,
                "label": row.label.value,
                "unavailable_reason": row.unavailable_reason,
            }
            for row in view.stages
        ],
        "rates": [
            {
                "code": row.code.value,
                "availability": row.availability.value,
                "value": snapshot.number(row.value)
                if row.availability.value == "available"
                else None,
                "unit": "ratio",
                "unavailable_reason": row.unavailable_reason,
            }
            for row in view.rates
        ],
    }


def _read_purchase(database, session_id, snapshot: _Snapshot) -> dict[str, object]:
    try:
        view = load_possible_purchase(database, session_id)
    except (ResultIncomplete, LivePurchaseUnavailable):
        return _unavailable("session")
    report = view.report
    if report.availability.value != "available":
        return _unavailable("session", "possible_purchase_unavailable")
    return {
        "scope": "session",
        "availability": "available",
        "estimation": True,
        "precision_uncommitted": report.precision_uncommitted,
        "visit_count": snapshot.number(report.visit_count),
        "minimum_seconds": snapshot.number(report.minimum_seconds),
        "meaning": "bag_signal_not_confirmed_purchase",
    }


def _read_live(database, session_id, shop_id, snapshot: _Snapshot) -> dict[str, object]:
    job = _latest_live_job(database, session_id)
    if job is None or job.status not in _TERMINAL_LIVE:
        raise LiveChatUnavailable
    view = load_live_results(database, job.id, shop_id=shop_id)
    facts = {
        key: view[key]
        for key in (
            "status",
            "capture_status",
            "result_complete",
            "coverage_complete",
            "unknown_tail",
        )
    }
    facts["scope"] = "selected_zone"
    for key in (
        "elapsed_capture_seconds",
        "observed_seconds",
        "missing_seconds",
        "unconfirmed_crossings",
    ):
        facts[key] = snapshot.number(view[key])
    summary = view.get("summary")
    if summary is not None:
        facts["summary"] = {
            key: snapshot.number(summary[key])
            for key in (
                "entry_count",
                "exit_count",
                "a_to_b_count",
                "b_to_a_count",
                "total_crossings",
            )
            if key in summary
        } | {
            key: summary[key]
            for key in ("shop_id", "shop_name", "partial", "label_mode", "entry_direction")
            if key in summary
        }
    else:
        facts["summary"] = None
    zone_dwell = view.get("zone_dwell") or {}
    selected_dwell = zone_dwell.get(str(shop_id), {})
    facts["zone_dwell"] = {
        key: snapshot.number(selected_dwell[key])
        for key in (
            "interior_average_seconds",
            "interior_sample_count",
            "front_average_seconds",
            "front_sample_count",
        )
        if key in selected_dwell
    }

    def minute(row):
        return {
            key: snapshot.number(row[key])
            for key in (
                "start_seconds",
                "end_seconds",
                "entries",
                "exits",
                "observed_seconds",
                "missing_seconds",
                "pending_count",
            )
            if key in row
        } | {
            key: row[key]
            for key in ("is_open", "coverage_incomplete", "unknown_tail")
            if key in row
        }

    facts["minutes"] = snapshot.bounded(
        view["minutes"], minute, has_more=view.get("next_bucket_cursor") is not None
    )
    facts["interruptions"] = snapshot.bounded(
        view["interruptions"],
        lambda row: {
            "start_seconds": snapshot.number(row["start_seconds"]),
            "end_seconds": snapshot.number(row["end_seconds"]),
            "end_known": row["end_known"],
            "reason": row["reason"],
        },
    )
    return facts
