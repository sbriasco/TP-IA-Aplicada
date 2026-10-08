"""Cancel a video analysis without treating it as a failure."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient

from flowsight.api.main import create_app
from flowsight.services.jobs import transition_job

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client() -> TestClient:
    database_url = prepare_empty_schema()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
        }
    )
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()


def _pending_job(client: TestClient) -> str:
    session_id = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()[
        "id"
    ]
    created = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert created.status_code == 201
    return str(created.json()["id"])


def _move(client: TestClient, job_id: str, target: str, *, reason: str | None = None) -> None:
    with client.app.state.session_factory.begin() as database_session:
        transition_job(
            database_session,
            job_id=job_id,
            target=target,
            occurred_at=datetime.now(UTC),
            reason_code=reason,
            failure_message="Mensaje de prueba." if reason else None,
        )


def test_cancel_pending_or_processing_returns_cancelled(client: TestClient) -> None:
    pending_id = _pending_job(client)
    pending = client.post(f"/jobs/{pending_id}/cancel")
    assert pending.status_code == 200
    body = pending.json()
    assert body["status"] == "cancelled"
    assert body["result_complete"] is False
    assert body["failure_code"] is None
    assert body["transitions"][-1]["reason_code"] == "operator_cancelled"

    processing_id = _pending_job(client)
    _move(client, processing_id, "processing")
    processing = client.post(f"/jobs/{processing_id}/cancel")
    assert processing.status_code == 200
    assert processing.json()["status"] == "cancelled"
    assert processing.json()["result_complete"] is False
    assert processing.json()["failure_code"] is None


def test_cancel_terminal_job_conflicts_and_missing_job_is_not_found(client: TestClient) -> None:
    missing = client.post(f"/jobs/{uuid.uuid4()}/cancel")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"

    for target, reason in (
        ("completed", None),
        ("failed", "analysis_failed"),
        ("cancelled", "operator_cancelled"),
    ):
        job_id = _pending_job(client)
        _move(client, job_id, "processing")
        _move(client, job_id, target, reason=reason)
        refused = client.post(f"/jobs/{job_id}/cancel")
        assert refused.status_code == 409
        assert set(refused.json()["detail"]) >= {"code", "message"}
