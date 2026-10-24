"""The funnel endpoint is whole-session and file-only.

It stays out of the eight metrics and the chat.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
    ShopFunnel,
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
WINDOW = [[0.0, 0.2], [0.25, 0.2], [0.25, 0.5], [0.0, 0.5]]
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
FUNNEL_CODES = {
    "observed_pass",
    "exposure",
    "stop",
    "attention",
    "linked_entry",
    "observed_pass_to_exposure",
    "exposure_to_stop",
    "stop_to_attention",
    "attention_to_linked_entry",
}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-funnel")
    monkeypatch.setenv("FLOWSIGHT_DETECTOR", "fake")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWSIGHT_YOLO_WEIGHTS", str(tmp_path / "missing.pt"))
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()


def _register(factory, videos_dir: Path, name: str) -> tuple[ProcessingJob, Shop]:
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
            source_kind=SourceKind.VIDEO_FILE,
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
            SceneZone(version_shop_id=version_shop.id, role=ZoneRole.SHOWCASE, polygon=WINDOW)
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


def test_completed_funnel_is_whole_session_and_metrics_stay_unchanged(
    client: TestClient, tmp_path: Path
) -> None:
    factory = client.app.state.session_factory
    job, shop = _register(factory, tmp_path, "funnel")
    other, other_shop = _register(factory, tmp_path, "aislada")
    settings = Settings(_env_file=None)
    for _ in range(2):
        assert (
            process_next_job(
                factory,
                worker_id="worker-funnel",
                fixture_path=FIXTURE_PATH,
                now=lambda: datetime.now(UTC),
                settings=settings,
            )
            is not None
        )

    funnel = client.get(f"/sessions/{job.session_id}/shops/{shop.id}/funnel")
    ranged = client.get(
        f"/sessions/{job.session_id}/shops/{shop.id}/funnel",
        params={"from_seconds": 0, "to_seconds": 1},
    )
    assert funnel.status_code == 200
    assert ranged.json() == funnel.json()
    body = funnel.json()
    assert body["precision_uncommitted"] is True
    assert body["stop_threshold_seconds"] == "3"
    assert body["attention_threshold_seconds"] == "8"
    assert [stage["stage"] for stage in body["stages"]] == [
        "observed_pass",
        "exposure",
        "stop",
        "attention",
        "linked_entry",
    ]
    assert [rate["code"] for rate in body["rates"]] == [
        "observed_pass_to_exposure",
        "exposure_to_stop",
        "stop_to_attention",
        "attention_to_linked_entry",
    ]
    assert "entry_rate" not in {rate["code"] for rate in body["rates"]}
    by_stage = {stage["stage"]: stage for stage in body["stages"]}
    assert by_stage["observed_pass"]["count"] == 1
    assert by_stage["exposure"]["count"] == 1
    assert by_stage["stop"]["count"] == 0
    assert by_stage["attention"]["label"] == "attention_estimate"
    by_rate = {rate["code"]: rate for rate in body["rates"]}
    assert by_rate["observed_pass_to_exposure"]["value"] == "1.000000"
    assert by_rate["stop_to_attention"]["availability"] == "unavailable"
    assert by_rate["stop_to_attention"]["value"] is None
    assert by_rate["stop_to_attention"]["unavailable_reason"] == "no_previous_stage"

    metrics = client.get(f"/sessions/{job.session_id}/shops/{shop.id}/metrics")
    assert metrics.status_code == 200
    assert {row["code"] for row in metrics.json()["metrics"]} == METRIC_CODES
    assert FUNNEL_CODES.isdisjoint({row["code"] for row in metrics.json()["metrics"]})
    foreign = client.get(f"/sessions/{other.session_id}/shops/{shop.id}/funnel")
    assert foreign.status_code == 404
    own = client.get(f"/sessions/{other.session_id}/shops/{other_shop.id}/funnel")
    assert own.status_code == 200
    assert own.json()["session_id"] == str(other.session_id)


def test_incomplete_and_webcam_funnels_are_rejected(client: TestClient) -> None:
    created = client.post("/sessions", json={"name": "Pendiente", "camera_id": "camera-funnel"})
    assert created.status_code == 201
    session_id = created.json()["id"]
    job = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 201
    shop_id = uuid.uuid4()
    pending = client.get(f"/sessions/{session_id}/shops/{shop_id}/funnel")
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "result_incomplete"

    with client.app.state.session_factory.begin() as database_session:
        transition_job(
            database_session,
            job_id=job.json()["id"],
            target="cancelled",
            occurred_at=datetime.now(UTC),
            reason_code="operator_cancelled",
        )
    cancelled = client.get(f"/sessions/{session_id}/shops/{shop_id}/funnel")
    assert cancelled.status_code == 409
    assert cancelled.json()["detail"]["code"] == "result_incomplete"
    missing = client.get(f"/sessions/{uuid.uuid4()}/shops/{shop_id}/funnel")
    assert missing.status_code == 404

    with client.app.state.session_factory.begin() as database_session:
        camera = get_or_create_camera(database_session, "camera-webcam-funnel")
        live = Session(
            name="Vivo",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.WEBCAM,
            created_at=datetime.now(UTC),
        )
        database_session.add(live)
        database_session.flush()
        live_id = live.id
    webcam = client.get(f"/sessions/{live_id}/shops/{shop_id}/funnel")
    assert webcam.status_code == 409
    assert webcam.json()["detail"]["code"] == "live_funnel_unavailable"
    engine = create_engine(os.environ["FLOWSIGHT_DATABASE_URL"])
    factory = sessionmaker(bind=engine)
    with factory() as database_session:
        rows = database_session.scalars(
            select(ShopFunnel).where(ShopFunnel.session_id == live_id)
        ).all()
        assert rows == []
    engine.dispose()


def test_chat_figures_do_not_offer_funnel_stages() -> None:
    assert FUNNEL_CODES.isdisjoint(_FIGURE_NAMES)
    assert {
        "traffic_total",
        "entries",
        "visible_occupancy",
        "dwell_mean_seconds",
        "peak",
    }.issubset(_FIGURE_NAMES)
