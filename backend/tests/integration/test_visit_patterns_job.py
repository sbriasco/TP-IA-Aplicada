"""A completed file analysis stores visit patterns and leaves closed figures alone."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

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
    ShopMetric,
    ShopMetricCode,
    SourceKind,
    VideoSource,
    VisitPatternReport,
    VisitSequence,
    ZoneRole,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.jobs import transition_job
from flowsight.services.visit_patterns import persist_visit_patterns
from flowsight.video.fixtures import write_clip
from flowsight.video.probe import probe_video
from flowsight.vision.visit_patterns import VisitPatternDraft
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
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-patterns")
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


def test_a_completed_file_stores_patterns_for_that_session_only(
    session_factory, tmp_path: Path
) -> None:
    job, shop = _register(session_factory, tmp_path, "patrones")
    other, _other_shop = _register(session_factory, tmp_path, "ajena")
    settings = Settings(_env_file=None)
    for _ in range(2):
        assert (
            process_next_job(
                session_factory,
                worker_id="worker-patterns",
                fixture_path=FIXTURE_PATH,
                now=lambda: datetime.now(UTC),
                settings=settings,
            )
            is not None
        )

    with session_factory() as database_session:
        report = database_session.scalar(
            select(VisitPatternReport).where(VisitPatternReport.job_id == job.id)
        )
        assert report is not None
        assert report.session_id == job.session_id
        assert report.patterns_availability.value == "available"
        assert report.group_count == 0
        sequences = database_session.scalars(
            select(VisitSequence).where(VisitSequence.job_id == job.id)
        ).all()
        assert sequences != []
        assert sequences[0].areas[0]["shop_id"] == str(shop.id)
        assert sequences[0].areas[0]["zone_role"] == "front"
        sequence_count = len(sequences)
        sequence_tracks = sequences[0].track_count
        codes = {
            row.code
            for row in database_session.scalars(
                select(ShopMetric).where(ShopMetric.job_id == job.id, ShopMetric.shop_id == shop.id)
            )
        }
        assert codes == set(ShopMetricCode)
        assert (
            database_session.scalar(select(ShopFunnel).where(ShopFunnel.job_id == job.id))
            is not None
        )
        foreign = database_session.scalar(
            select(VisitPatternReport).where(VisitPatternReport.session_id == other.session_id)
        )
        assert foreign is not None
        assert foreign.job_id == other.id
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        relative = stored.trajectory_relative_path

    path = tmp_path / relative
    path.write_text("changed\n", encoding="utf-8")
    with session_factory() as database_session:
        again = database_session.scalars(
            select(VisitSequence).where(VisitSequence.job_id == job.id)
        ).all()
        assert len(again) == sequence_count
        assert again[0].track_count == sequence_tracks


def test_webcam_failed_and_cancelled_do_not_store_a_completed_result(
    session_factory, tmp_path: Path
) -> None:
    failed, _failed_shop = _register(session_factory, tmp_path, "fallido")
    now = datetime.now(UTC)
    empty = VisitPatternDraft(
        patterns_availability="available",
        patterns_unavailable_reason=None,
        groups_availability="available",
        group_count=0,
        area_transitions=(),
        sequences=(),
        shop_transitions=(),
        groups=(),
    )
    with session_factory.begin() as database_session:
        transition_job(
            database_session, job_id=failed.id, target="processing", occurred_at=now
        )
        transition_job(
            database_session,
            job_id=failed.id,
            target="failed",
            occurred_at=now,
            reason_code="analysis_failed",
            failure_message="El análisis falló.",
        )
        persist_visit_patterns(
            database_session,
            job_id=failed.id,
            session_id=failed.session_id,
            draft=empty,
            source_kind=SourceKind.WEBCAM.value,
        )
    with session_factory() as database_session:
        assert (
            database_session.scalar(
                select(VisitPatternReport).where(VisitPatternReport.job_id == failed.id)
            )
            is None
        )
