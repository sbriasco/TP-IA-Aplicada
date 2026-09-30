from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from alembic import command
from flowsight.db.models import (
    Event,
    JobKind,
    JobStatus,
    JobStatusTransition,
    Observation,
    ProcessingJob,
    SceneVersion,
    Session,
    SourceKind,
    SyntheticFrame,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.worker.lifecycle import (
    claim_next_job,
    load_synthetic_fixture,
    process_next_job,
    recover_interrupted_jobs,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch):
    database_url = destructive_database_url()
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()
    command.downgrade(config, "base")


def create_pending_job(factory, suffix: str = "1") -> uuid.UUID:
    with factory.begin() as database_session:
        flow_session = Session(
            name=f"Session {suffix}",
            camera_id=f"camera-{suffix}",
            registered_camera_id=get_or_create_camera(database_session, f"camera-{suffix}").id,
            source_kind=SourceKind.SYNTHETIC,
        )
        job = ProcessingJob(
            session=flow_session,
            kind=JobKind.SYNTHETIC_BASE_FLOW,
            status=JobStatus.PENDING,
            transitions=[
                JobStatusTransition(
                    from_status=None,
                    to_status=JobStatus.PENDING,
                    occurred_at=datetime.now(UTC),
                )
            ],
        )
        database_session.add(job)
    return job.id


def test_two_workers_claim_distinct_jobs_atomically(session_factory) -> None:
    expected = {create_pending_job(session_factory, "a"), create_pending_job(session_factory, "b")}

    def claim(worker_id: str) -> uuid.UUID | None:
        with session_factory.begin() as database_session:
            job = claim_next_job(database_session, worker_id, datetime.now(UTC))
            return None if job is None else job.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = set(executor.map(claim, ["worker-a", "worker-b"]))

    assert claimed == expected


def test_loading_fixture_twice_does_not_duplicate_trace(session_factory) -> None:
    job_id = create_pending_job(session_factory)
    with session_factory.begin() as database_session:
        job = claim_next_job(database_session, "worker-a", datetime.now(UTC))
        assert job is not None
        first = load_synthetic_fixture(database_session, job, FIXTURE_PATH)
        second = load_synthetic_fixture(database_session, job, FIXTURE_PATH)

    assert second == first
    with session_factory() as database_session:
        assert database_session.scalar(select(func.count()).select_from(SyntheticFrame)) == 3
        assert database_session.scalar(select(func.count()).select_from(Observation)) == 3
        assert database_session.scalar(select(func.count()).select_from(Event)) == 2
        assert database_session.get(ProcessingJob, job_id) is not None


def test_process_next_job_completes_and_persists_fixture(session_factory) -> None:
    job_id = create_pending_job(session_factory)

    processed = process_next_job(
        session_factory,
        worker_id="worker-a",
        fixture_path=FIXTURE_PATH,
        now=lambda: datetime.now(UTC),
    )

    assert processed == job_id
    with session_factory() as database_session:
        job = database_session.get(ProcessingJob, job_id)
        assert job is not None
        assert job.status is JobStatus.COMPLETED
        assert [transition.to_status for transition in job.transitions] == [
            JobStatus.PENDING,
            JobStatus.PROCESSING,
            JobStatus.COMPLETED,
        ]


def test_interrupted_job_becomes_failed_and_is_not_retried(session_factory) -> None:
    job_id = create_pending_job(session_factory)
    with session_factory.begin() as database_session:
        assert claim_next_job(database_session, "worker-old", datetime.now(UTC)) is not None

    with session_factory.begin() as database_session:
        recovered = recover_interrupted_jobs(database_session, datetime.now(UTC))
    assert recovered == 1

    with session_factory.begin() as database_session:
        assert claim_next_job(database_session, "worker-new", datetime.now(UTC)) is None
        job = database_session.get(ProcessingJob, job_id)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.failure_code == "worker_interrupted"
        assert job.failure_message == "El worker anterior se interrumpió durante el procesamiento."
        assert job.result_complete is False


def test_claim_takes_older_video_analysis_before_synthetic(session_factory) -> None:
    """The worker claims the oldest pending job, including `video_analysis` (US1)."""

    older = datetime.now(UTC) - timedelta(minutes=5)
    with session_factory.begin() as database_session:
        camera = get_or_create_camera(database_session, "camera-video")
        video_session = Session(
            name="Video session",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.VIDEO_FILE,
        )
        database_session.add(video_session)
        database_session.flush()
        version = SceneVersion(
            camera_id=camera.id,
            version_number=1,
            reference_session_id=video_session.id,
            frame_width=1280,
            frame_height=720,
        )
        database_session.add(version)
        database_session.flush()
        video_job = ProcessingJob(
            session=video_session,
            kind=JobKind.VIDEO_ANALYSIS,
            scene_version_id=version.id,
            registered_camera_id=camera.id,
            status=JobStatus.PENDING,
            created_at=older,
            transitions=[
                JobStatusTransition(
                    from_status=None, to_status=JobStatus.PENDING, occurred_at=older
                )
            ],
        )
        database_session.add(video_job)
    synthetic_job_id = create_pending_job(session_factory, "synthetic")

    with session_factory.begin() as database_session:
        claimed = claim_next_job(database_session, "worker-a", datetime.now(UTC))
        assert claimed is not None
        assert claimed.id == video_job.id
        assert claimed.kind is JobKind.VIDEO_ANALYSIS
        assert claimed.status is JobStatus.PROCESSING

    with session_factory() as database_session:
        stored = database_session.get(ProcessingJob, synthetic_job_id)
        assert stored is not None
        assert stored.status is JobStatus.PENDING
        assert stored.claimed_by is None
