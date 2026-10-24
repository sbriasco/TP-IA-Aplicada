"""A completed file analysis stores a qualifying showcase stop and leaves the eight metrics."""

from __future__ import annotations

import hashlib
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
    SceneEvent,
    SceneEventKind,
    SceneVersion,
    SceneVersionShop,
    SceneZone,
    SceneZoneRole,
    Session,
    Shop,
    ShopMetric,
    ShopMetricCode,
    SourceKind,
    VideoSource,
    ZoneRole,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.jobs import transition_job
from flowsight.services.scene_metrics import persist_completed_scene
from flowsight.video.fixtures import write_clip
from flowsight.video.probe import probe_video
from flowsight.vision.events import SceneEventRecorder
from flowsight.vision.spatial import ShopGeometry
from flowsight.worker.lifecycle import process_next_job

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"
FRONT = [[0.0, 0.2], [0.4, 0.2], [0.4, 0.5], [0.0, 0.5]]
WINDOW = [[0.0, 0.2], [0.25, 0.2], [0.25, 0.5], [0.0, 0.5]]


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-showcase")
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


def test_open_window_stay_is_not_closed_and_the_zone_entry_remains(
    session_factory, tmp_path: Path
) -> None:
    job, shop = _register(session_factory, tmp_path, "abierta")
    other, _other_shop = _register(session_factory, tmp_path, "otra")
    settings = Settings(_env_file=None)
    for _ in range(2):
        assert (
            process_next_job(
                session_factory,
                worker_id="worker-showcase",
                fixture_path=FIXTURE_PATH,
                now=lambda: datetime.now(UTC),
                settings=settings,
            )
            is not None
        )

    with session_factory() as database_session:
        kinds = {
            (row.kind, row.zone_role)
            for row in database_session.scalars(
                select(SceneEvent).where(SceneEvent.job_id == job.id)
            )
        }
        assert (SceneEventKind.ZONE_ENTER, SceneZoneRole.WINDOW) in kinds
        assert SceneEventKind.SHOWCASE_STOP not in {kind for kind, _role in kinds}
        codes = {
            row.code
            for row in database_session.scalars(
                select(ShopMetric).where(ShopMetric.job_id == job.id, ShopMetric.shop_id == shop.id)
            )
        }
        assert codes == set(ShopMetricCode)
        foreign = database_session.scalars(
            select(SceneEvent).where(SceneEvent.session_id == other.session_id)
        ).all()
        assert all(row.job_id == other.id for row in foreign)


def test_a_qualifying_stop_is_stored_for_that_session_only(session_factory, tmp_path: Path) -> None:
    job, shop = _register(session_factory, tmp_path, "detencion")
    other, _other_shop = _register(session_factory, tmp_path, "ajena")
    geometry = ShopGeometry(
        shop_id=shop.id,
        shop_name="Local",
        front_polygon=tuple(tuple(point) for point in FRONT),
        interior_polygon=None,
        line_start=None,
        line_end=None,
        entry_direction=None,
        window_polygon=tuple(tuple(point) for point in WINDOW),
    )
    recorder = SceneEventRecorder([geometry], fps=1)
    recorder.observe(0, [(1, (0.1, 0.3))], [])
    recorder.observe(3, [(1, (0.9, 0.9))], [])
    with session_factory.begin() as database_session:
        persist_completed_scene(
            database_session,
            job_id=job.id,
            session_id=job.session_id,
            events=recorder.finish(),
            fps=1,
            duration_seconds=4,
            front_by_shop={shop.id: True},
            line_by_shop={shop.id: True},
        )
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        stored.status = JobStatus.COMPLETED
        stored.result_complete = True

    with session_factory() as database_session:
        stops = database_session.scalars(
            select(SceneEvent).where(
                SceneEvent.session_id == job.session_id,
                SceneEvent.kind == SceneEventKind.SHOWCASE_STOP,
            )
        ).all()
        assert len(stops) == 1
        assert stops[0].job_id == job.id
        assert stops[0].zone_role is SceneZoneRole.WINDOW
        enters = database_session.scalars(
            select(SceneEvent).where(
                SceneEvent.job_id == job.id,
                SceneEvent.kind == SceneEventKind.ZONE_ENTER,
                SceneEvent.zone_role == SceneZoneRole.WINDOW,
            )
        ).all()
        assert len(enters) == 1
        assert (
            database_session.scalars(
                select(SceneEvent).where(SceneEvent.session_id == other.session_id)
            ).all()
            == []
        )


def test_failed_and_cancelled_jobs_are_not_a_completed_funnel(
    session_factory, tmp_path: Path
) -> None:
    failed, failed_shop = _register(session_factory, tmp_path, "fallido")
    cancelled, cancelled_shop = _register(session_factory, tmp_path, "cancelado")
    now = datetime.now(UTC)
    with session_factory.begin() as database_session:
        transition_job(
            database_session,
            job_id=failed.id,
            target="processing",
            occurred_at=now,
        )
        transition_job(
            database_session,
            job_id=failed.id,
            target="failed",
            occurred_at=now,
            reason_code="analysis_failed",
            failure_message="El análisis falló.",
        )
        transition_job(
            database_session,
            job_id=cancelled.id,
            target="cancelled",
            occurred_at=now,
            reason_code="operator_cancelled",
        )

    application = create_app()
    with TestClient(application) as client:
        for session_id, shop_id in (
            (failed.session_id, failed_shop.id),
            (cancelled.session_id, cancelled_shop.id),
        ):
            response = client.get(f"/sessions/{session_id}/shops/{shop_id}/funnel")
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "result_incomplete"
    application.state.engine.dispose()
