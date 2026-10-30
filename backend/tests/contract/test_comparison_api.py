"""POST /comparisons is read-only multi-session contrast."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from flowsight.services.chat import _FIGURE_NAMES

SIX = Decimal("0.000001")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-comparison-api")
    monkeypatch.setenv("FLOWSIGHT_DETECTOR", "fake")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWSIGHT_YOLO_WEIGHTS", str(tmp_path / "missing.pt"))
    application = create_app()
    engine = create_engine(database_url)
    application.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()
    engine.dispose()


def _seed_session(
    client: TestClient,
    *,
    name: str,
    traffic: int,
    version_number: int,
    finished_at: datetime,
    camera_name: str = "cam-comparison",
    zone_name: str = "Local",
    source: SourceKind = SourceKind.SYNTHETIC,
    result_complete: bool = True,
    status: JobStatus = JobStatus.COMPLETED,
    include_metrics: bool = True,
) -> str:
    with client.app.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, camera_name)
        flow = Session(
            name=name,
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=source,
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
                name=zone_name,
                name_key=zone_name.casefold(),
            )
        )
        job = ProcessingJob(
            session_id=flow.id,
            scene_version_id=version.id,
            registered_camera_id=camera.id,
            kind=JobKind.VIDEO_ANALYSIS,
            status=status,
            created_at=finished_at,
            finished_at=finished_at,
            result_complete=result_complete and status == JobStatus.COMPLETED,
        )
        db.add(job)
        db.flush()
        if include_metrics and status == JobStatus.COMPLETED and result_complete:
            for code in ShopMetricCode:
                value = Decimal(traffic).quantize(SIX)
                if code == ShopMetricCode.ENTRY_RATE:
                    value = Decimal("0.500000")
                label = ShopMetricLabel.NONE
                if code == ShopMetricCode.TRAFFIC_TOTAL:
                    label = ShopMetricLabel.VISIT_ESTIMATE
                elif code == ShopMetricCode.VISIBLE_OCCUPANCY:
                    label = ShopMetricLabel.VISIBLE
                elif code.value.startswith("dwell_"):
                    label = ShopMetricLabel.OBSERVABLE
                db.add(
                    ShopMetric(
                        job_id=job.id,
                        session_id=flow.id,
                        shop_id=shop.id,
                        code=code,
                        value=value,
                        availability=MeasureAvailability.AVAILABLE,
                        label=label,
                        unavailable_reason=None,
                    )
                )
            db.add(
                TrafficBucket(
                    job_id=job.id,
                    session_id=flow.id,
                    shop_id=shop.id,
                    bucket_index=0,
                    start_seconds=Decimal(str(traffic * 60)).quantize(SIX),
                    track_count=traffic,
                )
            )
        return str(flow.id)


def test_compare_two_sessions(client: TestClient):
    a = _seed_session(
        client, name="A", traffic=20, version_number=1, finished_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    b = _seed_session(
        client, name="B", traffic=5, version_number=2, finished_at=datetime(2026, 9, 2, tzinfo=UTC)
    )
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, b], "zone_name": "Local", "axis": "session"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["axis"] == "session"
    assert len(body["columns"]) == 2
    traffic = next(figure for figure in body["figures"] if figure["code"] == "traffic_total")
    assert traffic["cells"][0]["value"] == 20.0
    assert traffic["cells"][1]["value"] == 5.0
    assert traffic["relation"] == "greater"
    assert traffic["delta"] == 15.0
    assert body["insights"]
    assert any(item["code"] == "higher_traffic_total" for item in body["insights"])


def test_same_request_is_stable(client: TestClient):
    a = _seed_session(
        client, name="A", traffic=8, version_number=1, finished_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    b = _seed_session(
        client, name="B", traffic=3, version_number=2, finished_at=datetime(2026, 9, 2, tzinfo=UTC)
    )
    payload = {"session_ids": [a, b], "zone_name": "Local", "axis": "session"}
    first = client.post("/comparisons", json=payload).json()
    second = client.post("/comparisons", json=payload).json()
    assert first == second


def test_insufficient_sessions(client: TestClient):
    a = _seed_session(
        client, name="A", traffic=8, version_number=1, finished_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, a], "zone_name": "Local", "axis": "session"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "comparison_insufficient_sessions"


def test_webcam_excluded(client: TestClient):
    file_session = _seed_session(
        client,
        name="File",
        traffic=4,
        version_number=1,
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    live = _seed_session(
        client,
        name="Live",
        traffic=4,
        version_number=2,
        finished_at=datetime(2026, 9, 2, tzinfo=UTC),
        source=SourceKind.WEBCAM,
        include_metrics=False,
    )
    response = client.post(
        "/comparisons",
        json={"session_ids": [file_session, live], "zone_name": "Local", "axis": "session"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "comparison_insufficient_sessions"


def test_missing_zone_is_unavailable_not_zero(client: TestClient):
    a = _seed_session(
        client, name="A", traffic=9, version_number=1, finished_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    b = _seed_session(
        client,
        name="B",
        traffic=2,
        version_number=2,
        finished_at=datetime(2026, 9, 2, tzinfo=UTC),
        zone_name="Otro",
    )
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, b], "zone_name": "Local", "axis": "session"},
    )
    assert response.status_code == 200
    figures = response.json()["figures"]
    traffic = next(figure for figure in figures if figure["code"] == "traffic_total")
    assert traffic["cells"][0]["availability"] == "available"
    assert traffic["cells"][1]["availability"] == "unavailable"
    assert traffic["cells"][1]["value"] is None
    assert traffic["relation"] == "unavailable"
    assert traffic["delta"] is None


def test_day_axis(client: TestClient):
    # Early UTC morning would be previous calendar day in UTC−3 hosts.
    day1 = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
    day2 = datetime(2026, 9, 2, 2, 0, tzinfo=UTC)
    a = _seed_session(client, name="A", traffic=10, version_number=1, finished_at=day1)
    b = _seed_session(client, name="B", traffic=4, version_number=2, finished_at=day2)
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, b], "zone_name": "Local", "axis": "day"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["axis"] == "day"
    labels = {column["label"] for column in body["columns"]}
    assert labels == {"2026-09-01", "2026-09-02"}


def test_day_axis_sums_counts_not_rates(client: TestClient):
    day1 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    day2 = datetime(2026, 9, 2, 10, 0, tzinfo=UTC)
    a = _seed_session(
        client, name="A1", traffic=10, version_number=1, finished_at=day1
    )
    b = _seed_session(
        client,
        name="A2",
        traffic=7,
        version_number=2,
        finished_at=day1 + timedelta(hours=2),
    )
    c = _seed_session(client, name="B", traffic=3, version_number=3, finished_at=day2)
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, b, c], "zone_name": "Local", "axis": "day"},
    )
    assert response.status_code == 200
    body = response.json()
    by_label = {column["label"]: index for index, column in enumerate(body["columns"])}
    assert set(by_label) == {"2026-09-01", "2026-09-02"}
    traffic = next(figure for figure in body["figures"] if figure["code"] == "traffic_total")
    assert traffic["cells"][by_label["2026-09-01"]]["value"] == 17.0
    assert traffic["cells"][by_label["2026-09-02"]]["value"] == 3.0
    rate = next(figure for figure in body["figures"] if figure["code"] == "entry_rate")
    assert rate["cells"][by_label["2026-09-01"]]["availability"] == "unavailable"
    assert rate["cells"][by_label["2026-09-01"]]["unavailable_reason"] == "group_non_additive"
    assert rate["cells"][by_label["2026-09-02"]]["availability"] == "available"


def test_axis_unavailable(client: TestClient):
    day = datetime(2026, 9, 1, tzinfo=UTC)
    a = _seed_session(client, name="A", traffic=10, version_number=1, finished_at=day)
    b = _seed_session(
        client, name="B", traffic=4, version_number=2, finished_at=day + timedelta(hours=1)
    )
    response = client.post(
        "/comparisons",
        json={"session_ids": [a, b], "zone_name": "Local", "axis": "day"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "comparison_axis_unavailable"


def test_invalid_request(client: TestClient):
    response = client.post(
        "/comparisons",
        json={"session_ids": [str(uuid.uuid4())], "zone_name": " ", "axis": "session"},
    )
    assert response.status_code in {400, 422}


def test_existing_reads_unchanged(client: TestClient):
    a = _seed_session(
        client, name="A", traffic=11, version_number=1, finished_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    b = _seed_session(
        client, name="B", traffic=6, version_number=2, finished_at=datetime(2026, 9, 2, tzinfo=UTC)
    )
    client.post(
        "/comparisons",
        json={"session_ids": [a, b], "zone_name": "Local", "axis": "session"},
    )
    with client.app.state.session_factory() as db:
        from sqlalchemy import select

        from flowsight.db.models import SceneVersionShop

        shop_id = db.scalar(
            select(SceneVersionShop.shop_id)
            .join(
                ProcessingJob,
                ProcessingJob.scene_version_id == SceneVersionShop.scene_version_id,
            )
            .where(ProcessingJob.session_id == uuid.UUID(a))
        )
    metrics = client.get(f"/sessions/{a}/shops/{shop_id}/metrics")
    assert metrics.status_code == 200
    codes = {row["code"] for row in metrics.json()["metrics"]}
    assert "traffic_total" in codes
    # Closed chat catalog (specs/014); comparison/insight must not appear as figure codes.
    assert set(_FIGURE_NAMES) == {
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
        "group_count",
        "visit_count",
    }
    assert "comparison" not in _FIGURE_NAMES
    assert "insight" not in _FIGURE_NAMES

