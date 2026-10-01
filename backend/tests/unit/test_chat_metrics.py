"""The five chat figures are the stored ones, not a new calculation."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url

from alembic import command
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
    "visible_occupancy",
    "dwell_mean_seconds",
    "dwell_median_seconds",
    "peak",
}


@pytest.fixture()
def database():
    database_url = destructive_database_url()
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
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    application = create_app()
    yield application
    application.state.engine.dispose()
    command.downgrade(config, "base")


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
    assert by_code["visible_occupancy"].value == Decimal("2.000000")
    assert by_code["visible_occupancy"].label == "visible"
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


def _completed_session(db, camera, name: str, *, traffic: Decimal, version_number: int = 1):
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
            name="Local",
            name_key="local",
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
    _stored(db, job, shop.id, ShopMetricCode.TRAFFIC_TOTAL, traffic, ShopMetricLabel.VISIT_ESTIMATE)
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
