"""A fake detector processes a registered video without loading YOLO."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from alembic import command
from flowsight.api.main import create_app
from flowsight.api.schemas import JobResponse
from flowsight.core.config import Settings
from flowsight.db.models import (
    AnalysisMeasure,
    EntryDirection,
    JobKind,
    JobStatus,
    JobStatusTransition,
    LineCrossing,
    Observation,
    ProcessingJob,
    SceneEntryLine,
    SceneVersion,
    SceneVersionShop,
    SceneZone,
    Session,
    Shop,
    SourceKind,
    SyntheticFrame,
    VideoSource,
    ZoneRole,
)
from flowsight.preview.snapshot import snapshot_path, write_preview_snapshot
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.jobs import transition_job
from flowsight.video.fixtures import CLIP_FPS, write_clip
from flowsight.video.probe import probe_video
from flowsight.vision.detector import Detection
from flowsight.vision.fake import FakeDetector
from flowsight.worker import video_analysis as video_analysis_module
from flowsight.worker.lifecycle import (
    claim_next_job,
    process_next_job,
    recover_interrupted_jobs,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-video")
    monkeypatch.setenv("FLOWSIGHT_DETECTOR", "fake")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(tmp_path))
    monkeypatch.setenv("FLOWSIGHT_YOLO_WEIGHTS", str(tmp_path / "missing-yolov8n.pt"))
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()
    command.downgrade(config, "base")


def _register_video_job(
    factory, videos_dir: Path, name: str, created_at: datetime
) -> ProcessingJob:
    clip = write_clip(videos_dir, size=(320, 240))
    probed = probe_video(clip)
    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
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
                declared_frame_count=probed.frame_count + 11,
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
        database_session.add(version)
        database_session.flush()
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
    return job


def test_fake_detector_completes_video_jobs_without_loading_yolo(
    session_factory, tmp_path: Path
) -> None:
    assert "ultralytics" not in sys.modules
    assert "torch" not in sys.modules
    older = datetime.now(UTC) - timedelta(minutes=5)
    newer = datetime.now(UTC)
    first = _register_video_job(session_factory, tmp_path, "alpha", older)
    second = _register_video_job(session_factory, tmp_path, "beta", newer)
    settings = Settings(_env_file=None)
    samples: dict[object, str] = {}

    for _ in range(2):
        processed = process_next_job(
            session_factory,
            worker_id="worker-video",
            fixture_path=FIXTURE_PATH,
            now=lambda: datetime.now(UTC),
            settings=settings,
        )
        assert processed is not None

    assert "ultralytics" not in sys.modules
    assert "torch" not in sys.modules

    with session_factory() as database_session:
        for job_id in (first.id, second.id):
            job = database_session.get(ProcessingJob, job_id)
            assert job is not None
            source = database_session.get(VideoSource, job.session_id)
            assert source is not None
            assert job.status is JobStatus.COMPLETED
            assert job.result_complete is True
            assert job.frames_analyzed == job.frames_total == source.frame_count
            assert job.frames_total != source.declared_frame_count
            assert job.detector_name == "fake"
            assert job.tracker_name == "fake"
            payload = JobResponse.model_validate(job).model_dump(mode="json")
            encoded = json.dumps(payload)
            assert str(tmp_path) not in encoded
            assert job.trajectory_relative_path is not None
            assert not Path(job.trajectory_relative_path).is_absolute()
            sample_text = (tmp_path / job.trajectory_relative_path).read_text(encoding="utf-8")
            header = json.loads(sample_text.splitlines()[0])
            assert header["session_id"] == str(job.session_id)
            samples[job.session_id] = sample_text
            observations = database_session.scalar(
                select(func.count()).select_from(Observation).where(Observation.job_id == job.id)
            )
            frames = database_session.scalar(
                select(func.count())
                .select_from(SyntheticFrame)
                .where(SyntheticFrame.job_id == job.id)
            )
            assert observations == 0
            assert frames == 0

    assert str(second.session_id) not in samples[first.session_id]
    assert str(first.session_id) not in samples[second.session_id]
    assert CLIP_FPS == 25


def _add_shop(factory, job: ProcessingJob) -> None:
    with factory.begin() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        shop = Shop(camera_id=stored.registered_camera_id)
        database_session.add(shop)
        database_session.flush()
        version_shop = SceneVersionShop(
            scene_version_id=stored.scene_version_id,
            shop_id=shop.id,
            camera_id=stored.registered_camera_id,
            position=0,
            name="Local",
            name_key="local",
        )
        database_session.add(version_shop)
        database_session.flush()
        database_session.add(
            SceneZone(
                version_shop_id=version_shop.id,
                role=ZoneRole.FRONT,
                polygon=[[0.0, 0.2], [0.3, 0.2], [0.3, 0.5], [0.0, 0.5]],
            )
        )
        database_session.add(
            SceneZone(
                version_shop_id=version_shop.id,
                role=ZoneRole.INTERIOR,
                polygon=[[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]],
            )
        )
        database_session.add(
            SceneEntryLine(
                version_shop_id=version_shop.id,
                start_x=0.0,
                start_y=0.5,
                end_x=1.0,
                end_y=0.5,
                entry_direction=EntryDirection.A_TO_B,
            )
        )


def test_halfway_progress_and_official_measures(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _register_video_job(session_factory, tmp_path, "measures", datetime.now(UTC))
    _add_shop(session_factory, job)
    captured: dict[str, object] = {}
    original = FakeDetector.detect

    def detect(self, frame_index, width, height, frame=None):
        with session_factory() as database_session:
            stored = database_session.get(ProcessingJob, job.id)
            if (
                stored is not None
                and stored.frames_total
                and frame_index == stored.frames_total // 2
            ):
                captured["frames_analyzed"] = stored.frames_analyzed
                captured["half"] = stored.frames_total / 2
                captured["frames_total"] = stored.frames_total
                path = snapshot_path(tmp_path, job.session_id, job.id)
                payload = json.loads(path.read_text(encoding="utf-8"))
                captured["progress"] = payload["progress_percent"]
                captured["preview_partial"] = [item["partial"] for item in payload["measures"]]
        return original(self, frame_index, width, height, frame)

    monkeypatch.setattr(FakeDetector, "detect", detect)
    processed = process_next_job(
        session_factory,
        worker_id="worker-video",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
        settings=Settings(_env_file=None),
    )
    assert processed is not None
    # Frame 25 of 50: the last persisted batch is frame 15. The preview still
    # follows the frame just analyzed (index 24 → 50%).
    assert captured["frames_analyzed"] == 15
    assert captured["half"] == 25
    # The snapshot is the latest image allowed by the 5 fps cap, so it can lag
    # the frame being analyzed. It still belongs to this video and stays partial.
    assert 0 < float(captured["progress"]) <= 50
    assert captured["preview_partial"] == [True, True, True]

    application = create_app()
    try:
        with TestClient(application) as client:
            missing = client.get(f"/jobs/{uuid.uuid4()}/measures")
            assert missing.status_code == 404
            response = client.get(f"/jobs/{job.id}/measures")
    finally:
        application.state.engine.dispose()

    assert response.status_code == 200
    body = response.json()
    assert {item["code"] for item in body} == {"entries", "exits", "visible_occupancy"}
    assert all(item["partial"] is False for item in body)
    assert all(item["shop_name"] == "Local" for item in body)
    by_code = {item["code"]: item["value"] for item in body}
    assert by_code == {"entries": 0, "exits": 0, "visible_occupancy": 1}

    with session_factory() as database_session:
        rows = database_session.scalars(
            select(AnalysisMeasure).where(AnalysisMeasure.job_id == job.id)
        ).all()
    assert len(rows) == 3
    assert len({(row.job_id, row.shop_id, row.code) for row in rows}) == 3


def test_cancel_mid_video_keeps_partial_measures_and_is_not_retried(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _register_video_job(session_factory, tmp_path, "cancel", datetime.now(UTC))
    _add_shop(session_factory, job)
    original = FakeDetector.detect

    def detect(self, frame_index, width, height, frame=None):
        with session_factory() as database_session:
            stored = database_session.get(ProcessingJob, job.id)
            if (
                stored is not None
                and stored.frames_total
                and stored.status is JobStatus.PROCESSING
                and frame_index == stored.frames_total // 2
            ):
                with session_factory.begin() as writing:
                    transition_job(
                        writing,
                        job_id=job.id,
                        target=JobStatus.CANCELLED,
                        occurred_at=datetime.now(UTC),
                        reason_code="operator_cancelled",
                    )
        return original(self, frame_index, width, height, frame)

    monkeypatch.setattr(FakeDetector, "detect", detect)
    processed = process_next_job(
        session_factory,
        worker_id="worker-video",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
        settings=Settings(_env_file=None),
    )
    assert processed == job.id

    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.CANCELLED
        assert stored.result_complete is False
        assert stored.failure_code is None
        assert stored.frames_analyzed is not None
        assert stored.frames_total is not None
        assert stored.frames_analyzed < stored.frames_total
        measures = database_session.scalars(
            select(AnalysisMeasure).where(AnalysisMeasure.job_id == job.id)
        ).all()
        assert measures
        assert all(measure.partial is True for measure in measures)
        assert stored.trajectory_relative_path is not None
        assert (tmp_path / stored.trajectory_relative_path).is_file()

    with session_factory.begin() as database_session:
        assert recover_interrupted_jobs(database_session, datetime.now(UTC)) == 0
    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.CANCELLED
        assert stored.failure_code is None
        assert claim_next_job(database_session, "worker-new", datetime.now(UTC)) is None


def test_preview_snapshots_follow_five_per_second_while_every_frame_is_analyzed(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _register_video_job(session_factory, tmp_path, "preview-cap", datetime.now(UTC))
    published: list[int] = []
    clock = {"t": 0.0}

    def monotonic() -> float:
        clock["t"] += 0.01
        return clock["t"]

    def record(path, update) -> None:
        published.append(update.frame_index)
        write_preview_snapshot(path, update)

    monkeypatch.setattr(video_analysis_module, "_monotonic", monotonic)
    monkeypatch.setattr(video_analysis_module, "write_preview_snapshot", record)
    processed = process_next_job(
        session_factory,
        worker_id="worker-video",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
        settings=Settings(_env_file=None),
    )
    assert processed == job.id
    assert published == [0, 20, 40, 49]
    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.COMPLETED
        assert stored.frames_analyzed == stored.frames_total == 50


def test_measures_flush_every_fifteen_frames_and_on_each_crossing(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _register_video_job(session_factory, tmp_path, "batches", datetime.now(UTC))
    _add_shop(session_factory, job)
    progress: list[int | None] = []
    crossings_at_frame_3: list[int] = []

    def detect(self, frame_index, width, height, frame=None):
        del self, width, height, frame
        with session_factory() as database_session:
            stored = database_session.get(ProcessingJob, job.id)
            progress.append(None if stored is None else stored.frames_analyzed)
            if frame_index == 3:
                crossings_at_frame_3.append(
                    database_session.scalar(
                        select(func.count())
                        .select_from(LineCrossing)
                        .where(LineCrossing.job_id == job.id)
                    )
                    or 0
                )
        # y=72 is side B of the entry line; y=192 is side A. Frame 1 opens a
        # pending exit and frame 2 reverses it, which decides two oscillations.
        y2 = 192 if frame_index == 1 else 72
        return [Detection(track_id=1, bbox=(10, 10, 40, y2))]

    monkeypatch.setattr(FakeDetector, "detect", detect)
    processed = process_next_job(
        session_factory,
        worker_id="worker-video",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
        settings=Settings(_env_file=None),
    )
    assert processed == job.id
    assert progress[0] == 0
    assert progress[1] == 0
    assert progress[2] == 0
    assert progress[3] == 3
    assert crossings_at_frame_3 == [2]
    assert progress[14] == 3
    assert progress[15] == 15
    assert progress[29] == 15
    assert progress[30] == 30
    assert progress[45] == 45
    assert progress[49] == 45

    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.COMPLETED
        assert stored.frames_analyzed == stored.frames_total == 50
        measures = database_session.scalars(
            select(AnalysisMeasure).where(AnalysisMeasure.job_id == job.id)
        ).all()
    assert {(measure.code.value, measure.value, measure.partial) for measure in measures} == {
        ("entries", 0, False),
        ("exits", 0, False),
        ("visible_occupancy", 1, False),
    }


def test_cancel_is_persisted_on_the_next_fifteen_frame_flush(
    session_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _register_video_job(session_factory, tmp_path, "cancel-batch", datetime.now(UTC))
    _add_shop(session_factory, job)
    original = FakeDetector.detect

    def detect(self, frame_index, width, height, frame=None):
        if frame_index == 3:
            with session_factory.begin() as writing:
                transition_job(
                    writing,
                    job_id=job.id,
                    target=JobStatus.CANCELLED,
                    occurred_at=datetime.now(UTC),
                    reason_code="operator_cancelled",
                )
        return original(self, frame_index, width, height, frame)

    monkeypatch.setattr(FakeDetector, "detect", detect)
    processed = process_next_job(
        session_factory,
        worker_id="worker-video",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
        settings=Settings(_env_file=None),
    )
    assert processed == job.id
    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.CANCELLED
        assert stored.frames_analyzed == 15
        assert stored.frames_total == 50
        measures = database_session.scalars(
            select(AnalysisMeasure).where(AnalysisMeasure.job_id == job.id)
        ).all()
        assert measures
        assert all(measure.partial is True for measure in measures)


def test_orphan_processing_video_job_fails_as_interrupted(session_factory, tmp_path: Path) -> None:
    job = _register_video_job(session_factory, tmp_path, "orphan", datetime.now(UTC))
    with session_factory.begin() as database_session:
        assert claim_next_job(database_session, "worker-old", datetime.now(UTC)) is not None
        recovered = recover_interrupted_jobs(database_session, datetime.now(UTC))
    assert recovered == 1
    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, job.id)
        assert stored is not None
        assert stored.status is JobStatus.FAILED
        assert stored.failure_code == "worker_interrupted"
        assert stored.result_complete is False
        assert claim_next_job(database_session, "worker-new", datetime.now(UTC)) is None
