from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from alembic import command
from flowsight.api.main import create_app
from flowsight.db.models import ProcessingJob
from flowsight.worker.lifecycle import load_synthetic_fixture

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent
FIXTURE_PATH = ROOT_DIR / "fixtures" / "synthetic" / "base-flow.json"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    values = dotenv_values(ROOT_DIR / ".env")
    database_url = os.environ.get("FLOWSIGHT_DATABASE_URL") or values.get("FLOWSIGHT_DATABASE_URL")
    assert isinstance(database_url, str)
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FLOWSIGHT_API_PORT", "8000")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-isolation")
    monkeypatch.setenv("FLOWSIGHT_PREVIEW_MAX_FPS", "5")
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    with TestClient(create_app()) as test_client:
        yield test_client
    command.downgrade(config, "base")


def create_trace(client: TestClient, name: str, duration_ms: int) -> dict:
    session = client.post("/sessions", json={"name": name, "camera_id": "shared-camera"}).json()
    job = client.post(
        f"/sessions/{session['id']}/jobs", json={"kind": "synthetic_base_flow"}
    ).json()
    with client.app.state.session_factory.begin() as database_session:
        record = database_session.get(ProcessingJob, uuid.UUID(job["id"]))
        assert record is not None
        record.processing_duration_ms = duration_ms
        load_synthetic_fixture(database_session, record, FIXTURE_PATH)
    return client.get(f"/jobs/{job['id']}/trace").json()


def test_trace_keeps_repeated_keys_isolated_by_session_and_job(client: TestClient) -> None:
    first = create_trace(client, "Primera", 101)
    second = create_trace(client, "Segunda", 202)

    assert first["job"]["session_id"] != second["job"]["session_id"]
    assert first["job"]["id"] != second["job"]["id"]
    assert first["job"]["processing_duration_ms"] == 101
    assert second["job"]["processing_duration_ms"] == 202
    assert [item["frame_index"] for item in first["frames"]] == [0, 1, 2]
    assert [item["frame_index"] for item in second["frames"]] == [0, 1, 2]
    assert [item["track_id"] for item in first["observations"]] == [1, 1, 1]
    assert [item["track_id"] for item in second["observations"]] == [1, 1, 1]

    for trace in (first, second):
        session_id = trace["job"]["session_id"]
        job_id = trace["job"]["id"]
        frames = {frame["id"]: frame for frame in trace["frames"]}
        observations = {item["id"]: item for item in trace["observations"]}
        assert all(frame["session_id"] == session_id for frame in frames.values())
        assert all(frame["job_id"] == job_id for frame in frames.values())
        assert all(item["session_id"] == session_id for item in observations.values())
        for event in trace["events"]:
            frame = frames[event["frame_id"]]
            assert event["session_id"] == session_id
            assert event["job_id"] == job_id
            assert event["video_timestamp_seconds"] == frame["video_timestamp_seconds"]
            assert event["observation_id"] in observations

    assert {item["id"] for item in first["frames"]}.isdisjoint(
        item["id"] for item in second["frames"]
    )


def test_trace_returns_safe_not_found(client: TestClient) -> None:
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000/trace")

    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Trabajo inexistente."
