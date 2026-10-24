"""Completed analysis persists facts and the eight metrics for that session only."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from flowsight.api.main import create_app
from flowsight.core.config import Settings
from flowsight.db.models import (
    AnalysisMeasure,
    EntryDirection,
    JobKind,
    JobStatus,
    JobStatusTransition,
    MeasureCode,
    ProcessingJob,
    SceneEntryLine,
    SceneEvent,
    SceneVersion,
    SceneVersionShop,
    SceneZone,
    Session,
    Shop,
    ShopMetric,
    SourceKind,
    VideoSource,
    ZoneRole,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.video.fixtures import write_clip
from flowsight.video.probe import probe_video
from flowsight.worker.lifecycle import process_next_job

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"
FRONT = [[0.0, 0.2], [0.4, 0.2], [0.4, 0.5], [0.0, 0.5]]


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-metrics")
    monkeypatch.setenv("FLOWSIGHT_DETECTOR", "fake")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWSIGHT_YOLO_WEIGHTS", str(tmp_path / "missing.pt"))
    engine = create_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


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


def test_completed_job_copies_official_measures_and_isolates_sessions(
    session_factory, tmp_path: Path
) -> None:
    first_job, first_shop = _register(session_factory, tmp_path, "alpha")
    second_job, _second_shop = _register(session_factory, tmp_path, "beta")
    settings = Settings(_env_file=None)
    for _ in range(2):
        assert (
            process_next_job(
                session_factory,
                worker_id="worker-metrics",
                fixture_path=FIXTURE_PATH,
                now=lambda: datetime.now(UTC),
                settings=settings,
            )
            is not None
        )

    with session_factory() as database_session:
        official = {
            row.code: row.value
            for row in database_session.scalars(
                select(AnalysisMeasure).where(AnalysisMeasure.job_id == first_job.id)
            )
        }
        copied = {
            row.code.value: row.value
            for row in database_session.scalars(
                select(ShopMetric).where(ShopMetric.job_id == first_job.id)
            )
        }
        assert official[MeasureCode.ENTRIES] == int(copied["entries"])
        assert official[MeasureCode.EXITS] == int(copied["exits"])
        assert official[MeasureCode.VISIBLE_OCCUPANCY] == int(copied["visible_occupancy"])
        assert copied["traffic_total"] == Decimal(1)
        assert copied["entry_rate"] == Decimal(0)
        kinds = {
            row.kind.value
            for row in database_session.scalars(
                select(SceneEvent).where(SceneEvent.job_id == first_job.id)
            )
        }
        assert "zone_enter" in kinds
        assert "store_pass" in kinds
        assert "dwell" not in kinds
        other = database_session.scalars(
            select(SceneEvent).where(SceneEvent.session_id == second_job.session_id)
        ).all()
        assert all(row.job_id == second_job.id for row in other)

    application = create_app()
    with TestClient(application) as client:
        metrics = client.get(f"/sessions/{first_job.session_id}/shops/{first_shop.id}/metrics")
        assert metrics.status_code == 200
        body = metrics.json()
        assert len(body["metrics"]) == 8
        assert "flow" in body and "peak" in body
        measures = client.get(f"/jobs/{first_job.id}/measures")
        official_body = {row["code"]: row["value"] for row in measures.json() if not row["partial"]}
        copied_body = {row["code"]: row["value"] for row in body["metrics"]}
        for code in ("entries", "exits", "visible_occupancy"):
            assert Decimal(str(copied_body[code])) == Decimal(official_body[code])
        foreign = client.get(f"/sessions/{second_job.session_id}/shops/{first_shop.id}/metrics")
        assert foreign.status_code == 404
        window = client.get(
            f"/sessions/{first_job.session_id}/events",
            params={"from_seconds": 0, "to_seconds": 0},
        )
        assert window.status_code == 200
        assert window.json() == []
        opened = client.get(
            f"/sessions/{first_job.session_id}/events",
            params={"from_seconds": 0, "to_seconds": 1},
        )
        assert opened.status_code == 200
        assert opened.json()
    application.state.engine.dispose()
