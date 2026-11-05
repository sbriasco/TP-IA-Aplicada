"""Conversation facts retain source, availability and session scope."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from flowsight.db.models import (
    JobStatus,
    MeasureAvailability,
    PossiblePurchaseReport,
    ProcessingJob,
    SceneVersionShop,
    SceneZoneRole,
    Session,
    ShopFunnelLabel,
    ShopFunnelRate,
    ShopFunnelRateCode,
    ShopFunnelStage,
    ShopFunnelStageCode,
    SourceKind,
    VisitAreaTransition,
    VisitGroup,
    VisitGroupLabel,
    VisitPatternReport,
    VisitSequence,
    VisitShopTransition,
)
from flowsight.services.chat_metrics import AnalysisNotFinal, LiveChatUnavailable
from flowsight.services.funnel import FunnelView
from flowsight.services.possible_purchase import PossiblePurchaseView
from flowsight.services.scene_metrics import ResultIncomplete, ShopNotInSession
from flowsight.services.visit_patterns import VisitPatternsView
from flowsight.vision.metrics import MetricValue, TrafficBucketValue


def _stored(monkeypatch):
    from flowsight.services import chat_context

    sid, shop_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    job = ProcessingJob(id=uuid.uuid4(), session_id=sid, scene_version_id=uuid.uuid4())
    session = Session(id=sid, source_kind=SourceKind.VIDEO_FILE)
    zones = [
        SceneVersionShop(shop_id=shop_id, name="Zona 419", position=0),
        SceneVersionShop(shop_id=other_id, name="Pasillo", position=1),
    ]
    database = SimpleNamespace(scalars=lambda _: iter(zones))
    flow = [TrafficBucketValue(991, Decimal("12.5"), 17)]
    funnel = FunnelView(
        job_id=job.id,
        session_id=sid,
        shop_id=shop_id,
        stop_threshold_seconds=Decimal(3),
        attention_threshold_seconds=Decimal(8),
        excluded_window_only=1,
        precision_uncommitted=True,
        stages=(
            ShopFunnelStage(
                stage=ShopFunnelStageCode.EXPOSURE,
                count=11,
                availability=MeasureAvailability.AVAILABLE,
                label=ShopFunnelLabel.NONE,
                unavailable_reason=None,
            ),
            ShopFunnelStage(
                stage=ShopFunnelStageCode.STOP,
                count=None,
                availability=MeasureAvailability.UNAVAILABLE,
                label=ShopFunnelLabel.NONE,
                unavailable_reason="no_showcase",
            ),
        ),
        rates=(
            ShopFunnelRate(
                code=ShopFunnelRateCode.OBSERVED_PASS_TO_EXPOSURE,
                value=Decimal("0.25"),
                availability=MeasureAvailability.AVAILABLE,
                unavailable_reason=None,
            ),
        ),
    )
    group = VisitGroup(
        ordinal=872,
        started_video_timestamp_seconds=Decimal("31.4"),
        ended_video_timestamp_seconds=Decimal("37.7"),
        label=VisitGroupLabel.GROUP_ESTIMATE,
    )
    patterns = VisitPatternsView(
        report=VisitPatternReport(
            patterns_availability=MeasureAvailability.AVAILABLE,
            groups_availability=MeasureAvailability.AVAILABLE,
            patterns_unavailable_reason=None,
            group_count=1,
            proximity_width_fraction=Decimal("0.08"),
            direction_degrees=Decimal(45),
            minimum_seconds=Decimal(2),
            precision_uncommitted=True,
        ),
        area_transitions=(
            VisitAreaTransition(
                from_shop_id=shop_id,
                to_shop_id=other_id,
                from_zone_role=SceneZoneRole.FRONT,
                to_zone_role=SceneZoneRole.INTERIOR,
                track_count=13,
            ),
        ),
        sequences=(
            VisitSequence(
                areas=[
                    {"shop_id": str(shop_id), "zone_role": "front"},
                    {"shop_id": str(other_id), "zone_role": "interior"},
                ],
                track_count=6,
            ),
        ),
        shop_transitions=(
            VisitShopTransition(
                from_shop_id=shop_id,
                to_shop_id=other_id,
                track_count=9,
            ),
        ),
        groups=((group, (781, 782, 783)),),
    )
    purchase = PossiblePurchaseView(
        report=PossiblePurchaseReport(
            availability=MeasureAvailability.AVAILABLE,
            visit_count=4,
            minimum_seconds=Decimal(1),
            precision_uncommitted=True,
        ),
        track_ids=(441, 442, 443, 444),
    )

    def only_session(database_arg, session_arg):
        assert database_arg is database and session_arg == sid
        return session

    def shop_metrics(database_arg, session_arg, selected_arg):
        assert database_arg is database and session_arg == sid
        if selected_arg != shop_id:
            raise ShopNotInSession
        rows = [MetricValue("traffic_total", Decimal(17), "available", "visit_estimate", None)]
        return rows, flow, flow[0]

    monkeypatch.setattr(chat_context, "get_active_session", only_session)
    monkeypatch.setattr(chat_context, "_completed_job", lambda *_: job)
    monkeypatch.setattr(chat_context, "load_shop_metrics", shop_metrics)
    monkeypatch.setattr(chat_context, "load_shop_funnel", lambda *_: funnel)
    monkeypatch.setattr(chat_context, "load_visit_patterns", lambda *_: patterns)
    monkeypatch.setattr(chat_context, "load_possible_purchase", lambda *_: purchase)
    return SimpleNamespace(
        module=chat_context,
        database=database,
        sid=sid,
        shop_id=shop_id,
        session=session,
        job=job,
        flow=flow,
        funnel=funnel,
        patterns=patterns,
        purchase=purchase,
    )


def test_video_context_includes_session_details_and_only_backed_numbers(monkeypatch):
    stored = _stored(monkeypatch)
    context = stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    json.dumps(context, allow_nan=False)
    assert context["source_kind"] == "video_file"
    facts = context["facts"]
    assert facts["scope"]["time_basis"] == "video"
    assert facts["flow"]["buckets"]["items"] == [{"start_seconds": "12.5", "track_count": 17}]
    assert facts["funnel"]["stages"][1]["count"] is None
    assert facts["funnel"]["stages"][1]["unavailable_reason"] == "no_showcase"
    assert facts["funnel"]["rates"][0]["value"] == "0.25"
    assert facts["patterns"]["scope"] == "session"
    assert facts["patterns"]["area_transitions"]["items"][0]["to"]["name"] == "Pasillo"
    assert facts["patterns"]["sequences"]["items"][0]["track_count"] == 6
    assert facts["groups"]["scope"] == "session"
    assert facts["groups"]["episodes"]["items"][0]["member_count"] == 3
    assert facts["possible_purchase"]["scope"] == "session"
    assert facts["possible_purchase"]["visit_count"] == 4
    assert facts["possible_purchase"]["estimation"] is True
    numbers = set(context["numeric_values"])
    assert {"12.5", "17", "11", "0.25", "13", "6", "9", "31.4", "37.7", "4"} <= numbers
    assert not {"991", "872", "781", "441", "419", "100", "25"} & numbers
    assert str(stored.sid) not in numbers
    assert context["truncated"] is False


def test_large_flow_is_explicitly_truncated_without_losing_summary_scope(monkeypatch):
    stored = _stored(monkeypatch)
    stored.flow[:] = [TrafficBucketValue(i, Decimal(i * 60), i + 1) for i in range(130)]
    context = stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    buckets = context["facts"]["flow"]["buckets"]
    assert len(buckets["items"]) == 100
    assert buckets["total"] == 130
    assert buckets["omitted"] == 30
    assert context["truncated"] is True
    assert "7740" not in context["numeric_values"]


def test_missing_optional_reports_remain_unavailable(monkeypatch):
    stored = _stored(monkeypatch)

    def unavailable(*_):
        raise ResultIncomplete

    for name in ("load_shop_funnel", "load_visit_patterns", "load_possible_purchase"):
        monkeypatch.setattr(stored.module, name, unavailable)
    context = stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    for key in ("funnel", "patterns", "groups", "possible_purchase"):
        assert context["facts"][key]["availability"] == "unavailable"
    assert "visit_count" not in context["facts"]["possible_purchase"]
    assert "0" not in context["numeric_values"]


def test_unavailable_patterns_do_not_hide_available_group_episodes(monkeypatch):
    stored = _stored(monkeypatch)
    stored.patterns.report.patterns_availability = MeasureAvailability.UNAVAILABLE
    stored.patterns.report.patterns_unavailable_reason = "no_areas"
    context = stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    assert context["facts"]["patterns"]["availability"] == "unavailable"
    assert "13" not in context["numeric_values"]
    assert context["facts"]["groups"]["group_count"] == 1
    assert "37.7" in context["numeric_values"]


def test_context_rejects_unknown_zone_and_missing_or_incomplete_session(monkeypatch):
    stored = _stored(monkeypatch)
    with pytest.raises(ShopNotInSession):
        stored.module.read_analysis_context(stored.database, stored.sid, uuid.uuid4())
    monkeypatch.setattr(stored.module, "get_active_session", lambda *_: None)
    with pytest.raises(AnalysisNotFinal):
        stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    monkeypatch.setattr(stored.module, "get_active_session", lambda *_: stored.session)

    def incomplete(*_):
        raise ResultIncomplete

    monkeypatch.setattr(stored.module, "load_shop_metrics", incomplete)
    with pytest.raises(AnalysisNotFinal):
        stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)


def test_webcam_context_uses_saved_live_summary_without_video_reports(monkeypatch):
    stored = _stored(monkeypatch)
    stored.session.source_kind = SourceKind.WEBCAM
    stored.job.status = JobStatus.FAILED
    live = {
        "session_id": str(stored.sid),
        "source_kind": "webcam",
        "status": "failed",
        "capture_status": "ended",
        "result_complete": False,
        "coverage_complete": False,
        "unknown_tail": True,
        "capture_started_at": datetime(2026, 11, 4, tzinfo=UTC),
        "elapsed_capture_seconds": 90.5,
        "observed_seconds": 80.5,
        "missing_seconds": 10,
        "unconfirmed_crossings": 2,
        "revision": 981,
        "summary": {
            "shop_id": str(stored.shop_id),
            "shop_name": "Zona 419",
            "entry_count": 8,
            "exit_count": 5,
            "total_crossings": 13,
            "partial": True,
            "label_mode": "directions",
        },
        "minutes": [
            {
                "bucket_index": 989,
                "start_seconds": 0.0,
                "end_seconds": 60.0,
                "entries": 8,
                "exits": 5,
                "observed_seconds": 50.0,
                "missing_seconds": 10.0,
                "coverage_incomplete": True,
                "unknown_tail": False,
                "revision": 981,
            }
        ],
        "next_bucket_cursor": 250,
        "interruptions": [
            {
                "id": str(uuid.uuid4()),
                "start_seconds": 90.5,
                "end_seconds": None,
                "end_known": False,
                "reason": "capture_lost",
            }
        ],
        "zone_dwell": {
            str(stored.shop_id): {
                "front_average_seconds": 4.7,
                "front_sample_count": 3,
                "interior_average_seconds": None,
                "interior_sample_count": 0,
            }
        },
    }
    monkeypatch.setattr(stored.module, "_latest_live_job", lambda *_: stored.job)

    def only_live(database_arg, job_arg, *, shop_id):
        assert database_arg is stored.database and job_arg == stored.job.id
        assert shop_id == stored.shop_id
        return live

    def never_video(*_):
        pytest.fail("Webcam must not read a video report")

    monkeypatch.setattr(stored.module, "load_live_results", only_live)
    for name in (
        "load_shop_metrics",
        "load_shop_funnel",
        "load_visit_patterns",
        "load_possible_purchase",
        "_completed_job",
    ):
        monkeypatch.setattr(stored.module, name, never_video)
    context = stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
    json.dumps(context, allow_nan=False)
    assert context["source_kind"] == "webcam"
    facts = context["facts"]
    assert facts["scope"]["time_basis"] == "capture"
    assert facts["live"]["coverage_complete"] is False
    assert facts["live"]["unknown_tail"] is True
    assert facts["live"]["interruptions"]["items"][0]["end_seconds"] is None
    assert facts["live"]["minutes"]["total"] is None
    assert context["truncated"] is True
    assert "4.7" in context["numeric_values"]
    assert not {"981", "989", "250", "419"} & set(context["numeric_values"])
    assert not {"funnel", "patterns", "groups", "possible_purchase"} & set(facts)

    stored.job.status = JobStatus.PROCESSING
    with pytest.raises(LiveChatUnavailable):
        stored.module.read_analysis_context(stored.database, stored.sid, stored.shop_id)
