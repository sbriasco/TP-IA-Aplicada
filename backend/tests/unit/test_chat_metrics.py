"""The five chat figures are the stored ones, not a new calculation."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import prepare_empty_schema

from flowsight.api.main import create_app
from flowsight.db.models import (
    JobKind,
    JobStatus,
    MeasureAvailability,
    ProcessingJob,
    SceneVersion,
    SceneVersionShop,
    Session,
    Shop,
    ShopMetric,
    ShopMetricCode,
    ShopMetricLabel,
    SourceKind,
    TrafficBucket,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.chat_metrics import AnalysisNotFinal, read_figures
from flowsight.services.scene_metrics import ShopNotInSession

BACKEND_DIR = Path(__file__).resolve().parents[2]
SIX = Decimal("0.000001")
CHAT_CODES = {
    "traffic_total",
    "entries",
    "exits",
    "store_pass",
    "entry_rate",
    "visible_occupancy",
    "dwell_mean_seconds",
    "dwell_median_seconds",
    "peak",
    "funnel_entries",
    "funnel_observed_pass",
    "funnel_exposure",
    "funnel_stop",
    "funnel_attention",
    "funnel_observed_pass_to_exposure_rate",
    "funnel_exposure_to_stop_rate",
    "funnel_stop_to_attention_rate",
    "funnel_attention_to_linked_entry_rate",
    "group_count",
    "visit_count",
}


def test_funnel_catalog_cites_all_stored_stages_and_ratios(monkeypatch) -> None:
    from flowsight.db.models import (
        ShopFunnelLabel,
        ShopFunnelRate,
        ShopFunnelRateCode,
        ShopFunnelStage,
        ShopFunnelStageCode,
    )
    from flowsight.services import chat_metrics
    from flowsight.services.funnel import FunnelView
    from flowsight.services.scene_metrics import ResultIncomplete
    from flowsight.vision.metrics import TrafficBucketValue

    session_id, shop_id, job_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    counts = {"observed_pass": 20, "exposure": 10, "stop": 5, "attention": 2, "linked_entry": 1}
    view = FunnelView(
        job_id=job_id, session_id=session_id, shop_id=shop_id,
        stop_threshold_seconds=Decimal(3), attention_threshold_seconds=Decimal(8),
        excluded_window_only=1, precision_uncommitted=True,
        stages=tuple(
            ShopFunnelStage(
                stage=ShopFunnelStageCode(code), count=count,
                availability=MeasureAvailability.AVAILABLE,
                label=ShopFunnelLabel.ATTENTION_ESTIMATE if code == "attention"
                else ShopFunnelLabel.NONE,
                unavailable_reason=None,
            ) for code, count in counts.items()
        ),
        rates=tuple(
            ShopFunnelRate(
                code=ShopFunnelRateCode(code), value=Decimal(value),
                availability=MeasureAvailability.AVAILABLE, unavailable_reason=None,
            ) for code, value in (
                ("observed_pass_to_exposure", "0.5"), ("exposure_to_stop", "0.5"),
                ("stop_to_attention", "0.4"), ("attention_to_linked_entry", "0.5"),
            )
        ),
    )
    monkeypatch.setattr(chat_metrics, "get_active_session", lambda *_: None)
    monkeypatch.setattr(
        chat_metrics, "load_shop_metrics",
        lambda *_: ([], [], TrafficBucketValue(0, Decimal(0), 0)),
    )
    monkeypatch.setattr(chat_metrics, "load_shop_funnel", lambda *_: view)

    def unavailable(*_):
        raise ResultIncomplete

    monkeypatch.setattr(chat_metrics, "load_visit_patterns", unavailable)
    monkeypatch.setattr(chat_metrics, "load_possible_purchase", unavailable)
    figures = {figure.code: figure for figure in read_figures(object(), session_id, shop_id)}
    assert figures["funnel_exposure"].value == Decimal(10)
    assert figures["funnel_stop"].value == Decimal(5)
    assert figures["funnel_attention"].value == Decimal(2)
    assert figures["funnel_attention"].label == "attention_estimate"
    assert figures["funnel_observed_pass"].value == Decimal(20)
    assert figures["funnel_entries"].value == Decimal(1)
    assert figures["funnel_stop_to_attention_rate"].value == Decimal("0.4")
    assert figures["funnel_attention_to_linked_entry_rate"].value == Decimal("0.5")
    assert figures["funnel_attention"].estimation is True

    view.stages[1].availability = MeasureAvailability.UNAVAILABLE
    view.stages[1].count = None
    view.stages[1].unavailable_reason = "no_showcase"
    view.rates[2].availability = MeasureAvailability.UNAVAILABLE
    view.rates[2].value = None
    view.rates[2].unavailable_reason = "no_previous_stage"
    missing = {figure.code: figure for figure in read_figures(object(), session_id, shop_id)}
    assert missing["funnel_exposure"].value is None
    assert missing["funnel_exposure"].unavailable_reason == "no_showcase"
    assert missing["funnel_stop_to_attention_rate"].value is None
    assert missing["funnel_stop_to_attention_rate"].unavailable_reason == "no_previous_stage"


def test_missing_funnel_keeps_every_stage_and_rate_unavailable(monkeypatch) -> None:
    from flowsight.services import chat_metrics
    from flowsight.services.scene_metrics import ResultIncomplete
    from flowsight.vision.metrics import TrafficBucketValue

    monkeypatch.setattr(chat_metrics, "get_active_session", lambda *_: None)
    monkeypatch.setattr(
        chat_metrics, "load_shop_metrics",
        lambda *_: ([], [], TrafficBucketValue(0, Decimal(0), 0)),
    )

    def unavailable(*_):
        raise ResultIncomplete

    for name in ("load_shop_funnel", "load_visit_patterns", "load_possible_purchase"):
        monkeypatch.setattr(chat_metrics, name, unavailable)
    figures = {figure.code: figure for figure in read_figures(object(), uuid.uuid4(), uuid.uuid4())}
    assert figures["funnel_exposure"].availability == "unavailable"
    assert figures["funnel_exposure"].value is None
    assert figures["funnel_observed_pass_to_exposure_rate"].availability == "unavailable"
    assert figures["funnel_observed_pass_to_exposure_rate"].value is None


@pytest.fixture()
def database():
    database_url = prepare_empty_schema()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-chat-metrics",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
        }
    )
    application = create_app()
    yield application
    application.state.engine.dispose()


def test_five_figures_match_the_stored_session_and_ignore_a_stretch(database) -> None:
    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-metrics")
        _first, first_job, first_shop = _completed_session(
            db, camera, "Primera", traffic=Decimal("17"), version_number=1
        )
        _stored(
            db,
            first_job,
            first_shop,
            ShopMetricCode.ENTRIES,
            Decimal("9"),
            ShopMetricLabel.NONE,
        )
        _stored(
            db,
            first_job,
            first_shop,
            ShopMetricCode.VISIBLE_OCCUPANCY,
            Decimal("2"),
            ShopMetricLabel.VISIBLE,
        )
        _stored(
            db,
            first_job,
            first_shop,
            ShopMetricCode.DWELL_MEAN_SECONDS,
            None,
            ShopMetricLabel.OBSERVABLE,
            reason="no_closed_dwells",
        )
        _stored(
            db,
            first_job,
            first_shop,
            ShopMetricCode.DWELL_MEDIAN_SECONDS,
            None,
            ShopMetricLabel.OBSERVABLE,
            reason="no_closed_dwells",
        )
        _stored(db, first_job, first_shop, ShopMetricCode.EXITS, Decimal("4"), ShopMetricLabel.NONE)
        _stored(
            db, first_job, first_shop, ShopMetricCode.STORE_PASS, Decimal("3"), ShopMetricLabel.NONE
        )
        _stored(
            db, first_job, first_shop, ShopMetricCode.ENTRY_RATE, Decimal("3"), ShopMetricLabel.NONE
        )
        _buckets(db, first_job, first_shop)
        second, second_job, second_shop = _completed_session(
            db, camera, "Segunda", traffic=Decimal("99"), version_number=2
        )
        _buckets(db, second_job, second_shop)
        plain = read_figures(db, first_job.session_id, first_shop)
        stretched = read_figures(
            db,
            first_job.session_id,
            first_shop,
            from_seconds=Decimal("50"),
            to_seconds=Decimal("70"),
        )
        other = read_figures(db, second.id, second_shop)

    assert stretched == plain
    by_code = {figure.code: figure for figure in plain}
    assert set(by_code) == CHAT_CODES
    assert by_code["traffic_total"].value == Decimal("17.000000")
    assert by_code["traffic_total"].label == "visit_estimate"
    assert by_code["entries"].value == Decimal("9.000000")
    assert by_code["exits"].value == Decimal("4.000000")
    assert by_code["store_pass"].value == Decimal("3.000000")
    assert by_code["entry_rate"].value == Decimal("3.000000")
    assert by_code["traffic_total"].estimation is True
    assert by_code["visible_occupancy"].value == Decimal("2.000000")
    assert by_code["visible_occupancy"].label == "visible"
    assert by_code["funnel_entries"].availability == "unavailable"
    assert by_code["group_count"].availability == "unavailable"
    assert by_code["visit_count"].availability == "unavailable"
    dwell = by_code["dwell_mean_seconds"]
    assert dwell.availability == "unavailable"
    assert dwell.value is None
    assert dwell.unavailable_reason == "no_closed_dwells"
    assert by_code["dwell_median_seconds"].label == "observable"
    assert by_code["peak"].bucket_index == 1
    assert by_code["peak"].start_seconds == Decimal("60.000000")
    assert by_code["peak"].track_count == 5
    assert by_code["peak"].value is None
    other_traffic = next(figure for figure in other if figure.code == "traffic_total")
    assert other_traffic.value == Decimal("99.000000")
    assert other_traffic.value != by_code["traffic_total"].value


def test_incomplete_latest_analysis_does_not_return_the_five(database) -> None:
    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-incomplete")
        flow, job, shop_id = _completed_session(db, camera, "Quedó vieja", traffic=Decimal("17"))
        newer = ProcessingJob(
            session_id=flow.id,
            scene_version_id=job.scene_version_id,
            registered_camera_id=camera.id,
            kind=JobKind.VIDEO_ANALYSIS,
            status=JobStatus.FAILED,
            created_at=datetime(2026, 9, 30, tzinfo=UTC),
            finished_at=datetime(2026, 9, 30, tzinfo=UTC),
            result_complete=False,
            failure_code="detector_failed",
            failure_message="no se pudo analizar",
        )
        db.add(newer)
        with pytest.raises(AnalysisNotFinal):
            read_figures(db, flow.id, shop_id)


def test_unknown_shop_is_not_in_the_session(database) -> None:
    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-shop")
        flow, _job, _shop_id = _completed_session(db, camera, "Un local", traffic=Decimal("1"))
        with pytest.raises(ShopNotInSession):
            read_figures(db, flow.id, uuid.uuid4())


def test_analysis_without_metrics_does_not_report_a_zero_peak(database) -> None:
    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-empty")
        flow, _job, shop_id = _completed_session(db, camera, "Histórico", traffic=None)
        figures = read_figures(db, flow.id, shop_id)
    assert all(figure.availability == "unavailable" for figure in figures)
    peak = next(figure for figure in figures if figure.code == "peak")
    assert peak.start_seconds is None
    assert peak.track_count is None
    assert peak.unavailable_reason == "metrics_not_generated"


def test_context_reads_historical_names_and_flow_from_only_the_selected_session(database) -> None:
    from flowsight.services.chat_context import read_analysis_context

    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-context")
        first, first_job, shop_id = _completed_session(
            db, camera, "Primera", traffic=Decimal("17"), shop_name="Zona 419"
        )
        _buckets(db, first_job, shop_id)
        second, second_job, other_shop = _completed_session(
            db, camera, "Segunda", traffic=Decimal("99"), version_number=2,
            shop_name="Otra configuración",
        )
        _buckets(db, second_job, other_shop)
        context = read_analysis_context(db, first.id, shop_id)
        assert context["source_kind"] == "synthetic"
        assert context["facts"]["zone_catalog"]["items"] == [
            {"shop_id": str(shop_id), "name": "Zona 419"}
        ]
        assert context["facts"]["flow"]["buckets"]["items"] == [
            {"start_seconds": "0.000000", "track_count": 1},
            {"start_seconds": "60.000000", "track_count": 5},
        ]
        assert context["facts"]["funnel"]["availability"] == "unavailable"
        with pytest.raises(ShopNotInSession):
            read_analysis_context(db, second.id, shop_id)


@pytest.mark.parametrize("front_configured", [False, True])
@pytest.mark.parametrize("reader", ["flow", "peak"])
def test_flow_and_peak_distinguish_missing_front_from_observed_zero(
    database, front_configured, reader
):
    from flowsight.services.chat_context import read_analysis_context
    from flowsight.services.scene_metrics import load_shop_metrics, persist_completed_scene

    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-context-front")
        flow_session, job, shop_id = _completed_session(
            db, camera, "Escena sin observaciones", traffic=None
        )
        persist_completed_scene(
            db, job_id=job.id, session_id=flow_session.id, events=[], fps=30,
            duration_seconds=65, front_by_shop={shop_id: front_configured},
            line_by_shop={shop_id: False},
        )
        rows, buckets, _peak = load_shop_metrics(db, flow_session.id, shop_id)
        traffic = next(row for row in rows if row.code == "traffic_total")
        assert traffic.availability == ("available" if front_configured else "unavailable")
        assert [row.track_count for row in buckets] == [0, 0]
        context = read_analysis_context(db, flow_session.id, shop_id)
        figures = {row.code: row for row in read_figures(db, flow_session.id, shop_id)}

    flow = context["facts"]["flow"]
    if front_configured and reader == "flow":
        assert flow["availability"] == "available"
        assert len(flow["buckets"]["items"]) == 2
        assert Decimal(0) in {Decimal(value) for value in context["numeric_values"]}
    elif front_configured:
        assert figures["peak"].availability == "available"
        assert figures["peak"].track_count == 0
    elif reader == "flow":
        assert flow["availability"] == "unavailable"
        assert flow["unavailable_reason"] == "scene_element_missing"
        assert flow["buckets"]["items"] == []
        assert context["numeric_values"] == []
    else:
        assert figures["peak"].availability == "unavailable"
        assert figures["peak"].unavailable_reason == "scene_element_missing"
        assert figures["peak"].start_seconds is None
        assert figures["peak"].track_count is None


@pytest.mark.parametrize("reader", ["flow", "peak"])
def test_orphan_buckets_cannot_back_flow_or_peak_without_traffic_metrics(database, reader):
    from flowsight.services.chat_context import read_analysis_context

    with database.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-context-no-metrics")
        flow_session, job, shop_id = _completed_session(db, camera, "Sin métricas", traffic=None)
        _stored(db, job, shop_id, ShopMetricCode.ENTRIES, Decimal(43), ShopMetricLabel.NONE)
        _buckets(db, job, shop_id)
        context = read_analysis_context(db, flow_session.id, shop_id)
        figures = {row.code: row for row in read_figures(db, flow_session.id, shop_id)}
    if reader == "flow":
        assert context["facts"]["flow"]["availability"] == "unavailable"
        assert context["facts"]["flow"]["buckets"]["items"] == []
        assert context["numeric_values"] == []
    else:
        assert figures["peak"].availability == "unavailable"
        assert figures["peak"].unavailable_reason == "metrics_not_generated"


def _completed_session(
    db, camera, name: str, *, traffic: Decimal | None,
    version_number: int = 1, shop_name: str = "Local",
):
    flow = Session(
        name=name,
        camera_id=camera.name,
        registered_camera_id=camera.id,
        source_kind=SourceKind.SYNTHETIC,
    )
    db.add(flow)
    db.flush()
    shop = Shop(camera_id=camera.id)
    version = SceneVersion(
        camera_id=camera.id,
        version_number=version_number,
        reference_session_id=flow.id,
        frame_width=320,
        frame_height=240,
    )
    db.add_all([shop, version])
    db.flush()
    db.add(
        SceneVersionShop(
            scene_version_id=version.id,
            shop_id=shop.id,
            camera_id=camera.id,
            position=0,
            name=shop_name,
            name_key=shop_name.casefold(),
        )
    )
    job = ProcessingJob(
        session_id=flow.id,
        scene_version_id=version.id,
        registered_camera_id=camera.id,
        kind=JobKind.VIDEO_ANALYSIS,
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        result_complete=True,
    )
    db.add(job)
    db.flush()
    if traffic is not None:
        _stored(
            db, job, shop.id, ShopMetricCode.TRAFFIC_TOTAL, traffic, ShopMetricLabel.VISIT_ESTIMATE
        )
    return flow, job, shop.id


def _stored(db, job, shop_id, code, value: Decimal | None, label, *, reason: str | None = None):
    db.add(
        ShopMetric(
            job_id=job.id,
            session_id=job.session_id,
            shop_id=shop_id,
            code=code,
            value=None if value is None else value.quantize(SIX),
            availability=(
                MeasureAvailability.UNAVAILABLE if value is None else MeasureAvailability.AVAILABLE
            ),
            label=label,
            unavailable_reason=reason,
        )
    )


def _buckets(db, job, shop_id) -> None:
    db.add_all(
        [
            TrafficBucket(
                job_id=job.id,
                session_id=job.session_id,
                shop_id=shop_id,
                bucket_index=0,
                start_seconds=Decimal("0.000000"),
                track_count=1,
            ),
            TrafficBucket(
                job_id=job.id,
                session_id=job.session_id,
                shop_id=shop_id,
                bucket_index=1,
                start_seconds=Decimal("60.000000"),
                track_count=5,
            ),
        ]
    )
