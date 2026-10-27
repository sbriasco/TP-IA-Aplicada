"""The possible-purchases endpoint is whole-session and file-only."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flowsight.api.main import create_app
from flowsight.core.config import Settings
from flowsight.db.models import (
    EntryDirection,
    JobKind,
    JobStatus,
    JobStatusTransition,
    ProcessingJob,
    SceneEntryLine,
    SceneVersion,
    SceneVersionShop,
    SceneZone,
    Session,
    Shop,
    SourceKind,
    VideoSource,
    ZoneRole,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.chat import _FIGURE_NAMES
from flowsight.services.jobs import transition_job
from flowsight.video.fixtures import write_clip
from flowsight.video.probe import probe_video
from flowsight.worker.lifecycle import process_next_job

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"
FRONT = [[0.0, 0.2], [0.4, 0.2], [0.4, 0.5], [0.0, 0.5]]
METRIC_CODES = {
    "traffic_total",
    "store_pass",
    "entries",
    "exits",
    "entry_rate",
    "dwell_mean_seconds",
    "dwell_median_seconds",
    "visible_occupancy",
}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-purchase-api")
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


def _register(
    factory, videos_dir: Path, name: str, *, source: SourceKind
) -> tuple[ProcessingJob, Shop]:
    clip = write_clip(videos_dir, size=(320, 240))
    probed = probe_video(clip)
    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
    created_at = datetime.now(UTC)
    with factory.begin() as database_session:
        camera = get_or_create_camera(database_session, f"camera-{name}")
        flow_session = Session(
            name=name,
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=source,
            created_at=created_at,
        )
        database_session.add(flow_session)
        database_session.flush()
        database_session.add(
            VideoSource(
                session_id=flow_session.id,
                relative_path=clip.name,
                original_filename=clip.name,
                size_bytes=clip.stat().st_size,
                sha256=digest,
                origin_machine_id="equipo-test",
                width=probed.width,
                height=probed.height,
                fps=probed.fps,
                fps_is_estimated=probed.fps_is_estimated,
                frame_count=probed.frame_count,
                declared_frame_count=probed.frame_count,
                duration_seconds=probed.duration_seconds,
            )
        )
        version = SceneVersion(
            camera_id=camera.id,
            version_number=1,
            reference_session_id=flow_session.id,
            frame_width=probed.width,
            frame_height=probed.height,
        )
        shop = Shop(camera_id=camera.id)
        database_session.add_all([version, shop])
        database_session.flush()
        version_shop = SceneVersionShop(
            scene_version_id=version.id,
            shop_id=shop.id,
            camera_id=camera.id,
            position=0,
            name="Local",
            name_key="local",
        )
        database_session.add(version_shop)
        database_session.flush()
        database_session.add(
            SceneZone(version_shop_id=version_shop.id, role=ZoneRole.FRONT, polygon=FRONT)
        )
        database_session.add(
            SceneEntryLine(
                version_shop_id=version_shop.id,
                start_x=0.0,
                start_y=0.9,
                end_x=1.0,
                end_y=0.9,
                entry_direction=EntryDirection.A_TO_B,
            )
        )
        job = ProcessingJob(
            session=flow_session,
            kind=JobKind.VIDEO_ANALYSIS,
            scene_version_id=version.id,
            registered_camera_id=camera.id,
            status=JobStatus.PENDING,
            created_at=created_at,
            transitions=[
                JobStatusTransition(
                    from_status=None, to_status=JobStatus.PENDING, occurred_at=created_at
                )
            ],
        )
        database_session.add(job)
        database_session.flush()
        return job, shop


def test_completed_purchases_ignore_range_and_leave_closed_figures(
    client: TestClient, tmp_path: Path
) -> None:
    factory = client.app.state.session_factory
    job, shop = _register(factory, tmp_path, "archivo", source=SourceKind.VIDEO_FILE)
    other, _other_shop = _register(factory, tmp_path, "otra", source=SourceKind.VIDEO_FILE)
    settings = Settings(_env_file=None)
    for _ in range(2):
        assert (
            process_next_job(
                factory,
                worker_id="worker-purchase-api",
                fixture_path=FIXTURE_PATH,
                now=lambda: datetime.now(UTC),
                settings=settings,
            )
            is not None
        )
    response = client.get(
        f"/sessions/{job.session_id}/possible-purchases",
        params={"from_seconds": 1, "shop_id": str(shop.id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "available"
    assert body["visit_count"] == 0
    assert body["minimum_seconds"] == "1"
    assert body["precision_uncommitted"] is True
    assert body["track_ids"] == []
    other_body = client.get(f"/sessions/{other.session_id}/possible-purchases").json()
    assert other_body["visit_count"] == 0
    assert other_body["track_ids"] == []
    metrics = client.get(f"/sessions/{job.session_id}/shops/{shop.id}/metrics")
    assert metrics.status_code == 200
    assert {row["code"] for row in metrics.json()["metrics"]} == METRIC_CODES
    funnel = client.get(f"/sessions/{job.session_id}/shops/{shop.id}/funnel")
    assert funnel.status_code == 200
    assert {row["stage"] for row in funnel.json()["stages"]} == {
        "observed_pass",
        "exposure",
        "stop",
        "attention",
        "linked_entry",
    }
    patterns = client.get(f"/sessions/{job.session_id}/visit-patterns")
    assert patterns.status_code == 200
    assert patterns.json()["precision_uncommitted"] is True
    assert "possible_purchase" not in _FIGURE_NAMES
    assert "posible_compra" not in _FIGURE_NAMES
    assert set(_FIGURE_NAMES) == {
        "traffic_total",
        "entries",
        "visible_occupancy",
        "dwell_mean_seconds",
        "dwell_median_seconds",
        "peak",
    }
    missing = client.get(f"/sessions/{uuid.uuid4()}/possible-purchases")
    assert missing.status_code == 404


def test_incomplete_and_webcam_are_rejected(client: TestClient, tmp_path: Path) -> None:
    factory = client.app.state.session_factory
    failed, _shop = _register(factory, tmp_path, "fallido", source=SourceKind.VIDEO_FILE)
    webcam, _webcam_shop = _register(factory, tmp_path, "vivo", source=SourceKind.WEBCAM)
    now = datetime.now(UTC)
    with factory.begin() as database_session:
        transition_job(database_session, job_id=failed.id, target="processing", occurred_at=now)
        transition_job(
            database_session,
            job_id=failed.id,
            target="failed",
            occurred_at=now,
            reason_code="analysis_failed",
            failure_message="El análisis falló.",
        )
    failed_response = client.get(f"/sessions/{failed.session_id}/possible-purchases")
    assert failed_response.status_code == 409
    assert failed_response.json()["detail"]["code"] == "result_incomplete"
    live = client.get(f"/sessions/{webcam.session_id}/possible-purchases")
    assert live.status_code == 409
    assert live.json()["detail"]["code"] == "live_purchase_unavailable"
