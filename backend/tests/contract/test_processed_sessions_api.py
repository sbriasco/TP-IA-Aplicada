"""Processed-session history lists the latest analysis and leaves GET /sessions alone."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient

from alembic import command
from flowsight.api.main import create_app
from flowsight.db.models import (
    JobKind,
    JobStatus,
    ProcessingJob,
    SceneVersion,
    Session,
    SourceKind,
    VideoSource,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.jobs import transition_job

BACKEND_DIR = Path(__file__).resolve().parents[2]
SESSION_KEYS = {"id", "name", "source_kind", "camera", "created_at"}


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_url = destructive_database_url()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract-history",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
            "FLOWSIGHT_VIDEOS_DIR": str(tmp_path),
        }
    )
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()
    command.downgrade(config, "base")


def test_history_uses_the_analysis_version_and_keeps_the_session_list(
    client: TestClient,
) -> None:
    untouched = client.post("/sessions", json={"name": "Sin análisis", "camera_id": "cam-history"})
    assert untouched.status_code == 201

    failed = client.post("/sessions", json={"name": "Fallida", "camera_id": "cam-history"})
    assert failed.status_code == 201
    failed_id = failed.json()["id"]
    job = client.post(f"/sessions/{failed_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 201
    moment = datetime.now(UTC)
    with client.app.state.session_factory.begin() as database_session:
        transition_job(
            database_session,
            job_id=job.json()["id"],
            target="processing",
            occurred_at=moment,
        )
        transition_job(
            database_session,
            job_id=job.json()["id"],
            target="failed",
            occurred_at=moment,
            reason_code="detector_failed",
            failure_message="no se pudo analizar",
        )

    completed_id = _completed_with_later_version(client)
    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert set(listed.json()[0]) == SESSION_KEYS

    history = client.get("/processed-sessions")
    assert history.status_code == 200
    rows = {row["session_id"]: row for row in history.json()}
    assert untouched.json()["id"] not in rows
    assert rows[failed_id]["failure_message"] == "no se pudo analizar"
    assert rows[failed_id]["result_complete"] is False
    assert rows[failed_id]["status"] == "failed"
    assert rows[completed_id]["name"] == "Completada"
    assert rows[completed_id]["video_filename"] == "clip.avi"
    assert rows[completed_id]["status"] == "completed"
    assert rows[completed_id]["finished_at"] is not None
    assert rows[completed_id]["version_number"] == 1
    assert rows[completed_id]["result_complete"] is True
    assert rows[failed_id]["session_id"] != rows[completed_id]["session_id"]


def _completed_with_later_version(client: TestClient) -> str:
    with client.app.state.session_factory.begin() as database_session:
        camera = get_or_create_camera(database_session, "cam-completed")
        flow_session = Session(
            name="Completada",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.VIDEO_FILE,
        )
        database_session.add(flow_session)
        database_session.flush()
        database_session.add(
            VideoSource(
                session_id=flow_session.id,
                relative_path=f"{flow_session.id}.avi",
                original_filename="clip.avi",
                size_bytes=8,
                sha256="a" * 64,
                origin_machine_id="equipo-test",
                width=320,
                height=240,
                fps=10,
                fps_is_estimated=False,
                frame_count=10,
                declared_frame_count=10,
                duration_seconds=1,
            )
        )
        used = SceneVersion(
            camera_id=camera.id,
            version_number=1,
            reference_session_id=flow_session.id,
            frame_width=320,
            frame_height=240,
        )
        later = SceneVersion(
            camera_id=camera.id,
            version_number=2,
            reference_session_id=flow_session.id,
            frame_width=320,
            frame_height=240,
        )
        database_session.add_all([used, later])
        database_session.flush()
        finished = datetime.now(UTC)
        database_session.add(
            ProcessingJob(
                session_id=flow_session.id,
                scene_version_id=used.id,
                registered_camera_id=camera.id,
                kind=JobKind.VIDEO_ANALYSIS,
                status=JobStatus.COMPLETED,
                finished_at=finished,
                result_complete=True,
            )
        )
        session_id = str(flow_session.id)
    return session_id
