from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from dotenv import dotenv_values
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
    Session,
    SourceKind,
    SyntheticFrame,
)
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
    values = dotenv_values(ROOT_DIR / ".env")
    database_url = os.environ.get("FLOWSIGHT_DATABASE_URL") or values.get("FLOWSIGHT_DATABASE_URL")
    assert isinstance(database_url, str)
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
