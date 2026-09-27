from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from alembic import command
from flowsight.db.models import JobKind, JobStatus, ProcessingJob, Session, SourceKind
from flowsight.services.cameras import get_or_create_camera

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def database_url() -> str:
    return destructive_database_url()


@pytest.fixture()
def migrated_database(database_url: str):
    os.environ["FLOWSIGHT_DATABASE_URL"] = database_url
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield create_engine(database_url)
    command.downgrade(config, "base")


def test_migration_is_repeatable_and_creates_expected_tables(
    database_url: str, migrated_database
) -> None:
    config = Config(BACKEND_DIR / "alembic.ini")
    command.upgrade(config, "head")

    tables = set(inspect(migrated_database).get_table_names())
    assert {
        "sessions",
        "processing_jobs",
        "job_status_transitions",
        "synthetic_frames",
        "observations",
        "events",
    }.issubset(tables)


def test_database_rejects_cross_session_frame_reference(migrated_database) -> None:
    session_a = uuid4()
    session_b = uuid4()
    job_a = uuid4()
    frame_id = uuid4()

    camera_a = uuid4()
    camera_b = uuid4()

    with migrated_database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cameras (id, name, name_key) "
                "VALUES (:a, 'camera-a', 'camera-a'), (:b, 'camera-b', 'camera-b')"
            ),
            {"a": camera_a, "b": camera_b},
        )
        connection.execute(
            text(
                "INSERT INTO sessions (id, name, camera_id, registered_camera_id, source_kind) "
                "VALUES (:a, 'A', 'camera-a', :camera_a, 'synthetic'), "
                "(:b, 'B', 'camera-b', :camera_b, 'synthetic')"
            ),
            {"a": session_a, "b": session_b, "camera_a": camera_a, "camera_b": camera_b},
        )
        connection.execute(
            text(
                "INSERT INTO processing_jobs (id, session_id, kind, status) "
                "VALUES (:job, :session, 'synthetic_base_flow', 'pending')"
            ),
            {"job": job_a, "session": session_a},
        )

    with pytest.raises(IntegrityError):
        with migrated_database.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO synthetic_frames "
                    "(id, session_id, job_id, camera_id, frame_index, video_timestamp_seconds) "
                    "VALUES (:frame, :wrong_session, :job, 'camera-b', 0, 0)"
                ),
                {"frame": frame_id, "wrong_session": session_b, "job": job_a},
            )

    with migrated_database.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM synthetic_frames"))
    assert count == 0


def test_orm_enums_match_database_values(migrated_database) -> None:
    session_id = uuid4()
    job_id = uuid4()

    with OrmSession(migrated_database) as database_session:
        flow_session = Session(
            id=session_id,
            name="Sesión ORM",
            camera_id="camera-orm",
            registered_camera_id=get_or_create_camera(database_session, "camera-orm").id,
            source_kind=SourceKind.SYNTHETIC,
        )
        database_session.add(
            ProcessingJob(
                id=job_id,
                session=flow_session,
                kind=JobKind.SYNTHETIC_BASE_FLOW,
                status=JobStatus.PENDING,
            )
        )
        database_session.commit()

    with migrated_database.connect() as connection:
        values = connection.execute(
            text("SELECT kind::text, status::text FROM processing_jobs WHERE id = :id"),
            {"id": job_id},
        ).one()
    assert values == ("synthetic_base_flow", "pending")
