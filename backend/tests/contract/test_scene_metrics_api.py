"""Session metrics and events stay out of the session list and reject incomplete jobs."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient

from alembic import command
from flowsight.api.main import create_app
from flowsight.services.jobs import transition_job

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client() -> TestClient:
    database_url = destructive_database_url()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract-metrics",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
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


def test_session_list_has_no_metrics_and_incomplete_analysis_is_409(client: TestClient) -> None:
    created = client.post("/sessions", json={"name": "Local", "camera_id": "camera-metrics"})
    assert created.status_code == 201
    session_id = created.json()["id"]
    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert all("metrics" not in item and "events" not in item for item in listed.json())

    job = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 201
    shop_id = uuid.uuid4()
    pending = client.get(f"/sessions/{session_id}/shops/{shop_id}/metrics")
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "result_incomplete"

    with client.app.state.session_factory.begin() as database_session:
        transition_job(
            database_session,
            job_id=job.json()["id"],
            target="cancelled",
            occurred_at=datetime.now(UTC),
            reason_code="operator_cancelled",
        )
    cancelled = client.get(f"/sessions/{session_id}/events")
    assert cancelled.status_code == 409
    assert cancelled.json()["detail"]["code"] == "result_incomplete"
    missing = client.get(f"/sessions/{uuid.uuid4()}/events")
    assert missing.status_code == 404
