"""Migration 0004 adds cancelled, progress columns and the measure tables."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from alembic import command
from flowsight.db.models import (
    AnalysisMeasure,
    JobKind,
    JobStatus,
    JobStatusTransition,
    MeasureAvailability,
    MeasureCode,
    ProcessingJob,
    Session,
    Shop,
    SourceKind,
)
from flowsight.services.cameras import get_or_create_camera

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def database_url() -> str:
    return destructive_database_url()


def test_upgrade_from_0003_adds_video_analysis_schema_and_downgrade_keeps_cancelled(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "0003_video_declared_frame_count")

    engine = create_engine(database_url)
    tables_before = set(inspect(engine).get_table_names())
    assert "analysis_measures" not in tables_before
    assert "line_crossings" not in tables_before

    command.upgrade(config, "head")
    inspector = inspect(engine)
    job_columns = {column["name"] for column in inspector.get_columns("processing_jobs")}
    assert {
        "frames_analyzed",
        "frames_total",
        "analyzed_video_timestamp_seconds",
        "result_complete",
        "detector_name",
        "detector_version",
        "tracker_name",
        "tracker_version",
        "trajectory_relative_path",
    }.issubset(job_columns)
    unique = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("analysis_measures")
    }
    assert ("job_id", "shop_id", "code") in unique
    indexes = {tuple(index["column_names"]) for index in inspector.get_indexes("line_crossings")}
    assert ("session_id", "shop_id", "track_id") in indexes

    factory = sessionmaker(bind=engine)
    with factory.begin() as database_session:
        camera = get_or_create_camera(database_session, "camera-0004")
        flow_session = Session(
            name="Session 0004",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.SYNTHETIC,
        )
        database_session.add(flow_session)
        database_session.flush()
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
        database_session.flush()
        assert job.result_complete is False
        job_id = job.id
        session_id = flow_session.id
        shop = Shop(camera_id=camera.id)
        database_session.add(shop)
        database_session.flush()
        database_session.add(
            AnalysisMeasure(
                job_id=job_id,
                session_id=session_id,
                shop_id=shop.id,
                code=MeasureCode.ENTRIES,
                value=1,
                availability=MeasureAvailability.AVAILABLE,
                partial=True,
                video_timestamp_seconds=0,
            )
        )

    with pytest.raises(IntegrityError):
        with factory.begin() as database_session:
            stored = database_session.get(ProcessingJob, job_id)
            assert stored is not None
            stored.result_complete = True

    with pytest.raises(IntegrityError):
        with factory.begin() as database_session:
            database_session.add(
                ProcessingJob(
                    session_id=session_id,
                    kind=JobKind.VIDEO_ANALYSIS,
                    status=JobStatus.PENDING,
                )
            )

    with engine.connect() as connection:
        labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum AS e "
                    "JOIN pg_type AS t ON t.oid = e.enumtypid "
                    "WHERE t.typname = 'job_status'"
                )
            ).scalars()
        )
    assert "cancelled" in labels

    command.downgrade(config, "0003_video_declared_frame_count")
    inspector = inspect(engine)
    assert "analysis_measures" not in inspector.get_table_names()
    assert "frames_analyzed" not in {
        column["name"] for column in inspector.get_columns("processing_jobs")
    }
    with engine.connect() as connection:
        labels = set(
            connection.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum AS e "
                    "JOIN pg_type AS t ON t.oid = e.enumtypid "
                    "WHERE t.typname = 'job_status'"
                )
            ).scalars()
        )
    assert "cancelled" in labels

    command.downgrade(config, "base")
    engine.dispose()
