from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from alembic import command
from flowsight.api.main import create_app
from flowsight.services.jobs import InvalidJobTransition, transition_job

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


@pytest.fixture()
def client() -> TestClient:
    values = dotenv_values(ROOT_DIR / ".env")
    database_url = os.environ.get("FLOWSIGHT_DATABASE_URL") or values.get("FLOWSIGHT_DATABASE_URL")
    assert isinstance(database_url, str)
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
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    command.downgrade(config, "base")


def test_creates_and_gets_session(client: TestClient) -> None:
    created = client.post("/sessions", json={"name": "Local principal", "camera_id": "camera-01"})

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Local principal"
    assert body["camera_id"] == "camera-01"
    assert body["source_kind"] == "synthetic"
    assert client.get(f"/sessions/{body['id']}").json() == body


def test_health_and_input_validation(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    invalid = client.post("/sessions", json={"name": "   ", "camera_id": "camera-01"})
    assert invalid.status_code == 422
    assert invalid.json() == {
        "code": "validation_error",
        "message": "La solicitud no cumple el contrato.",
    }


def test_creates_job_with_initial_transition_and_returns_history(client: TestClient) -> None:
    session_id = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()[
        "id"
    ]

    created = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})

    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "pending"
    assert job["transitions"][0]["from_status"] is None
    assert job["transitions"][0]["to_status"] == "pending"

    application = client.app
    with application.state.session_factory() as database_session:
        transition_job(
            database_session,
            job_id=job["id"],
            target="processing",
            occurred_at=datetime.now(UTC),
        )
        transition_job(
            database_session,
            job_id=job["id"],
            target="completed",
            occurred_at=datetime.now(UTC),
        )
        database_session.commit()

    fetched = client.get(f"/jobs/{job['id']}")
    assert fetched.status_code == 200
    assert [item["to_status"] for item in fetched.json()["transitions"]] == [
        "pending",
        "processing",
        "completed",
    ]
    assert fetched.json()["started_at"] is not None
    assert fetched.json()["finished_at"] is not None


def test_rejects_invalid_transition_without_changing_job(client: TestClient) -> None:
    session_id = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()[
        "id"
    ]
    job_id = client.post(
        f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"}
    ).json()["id"]

    with client.app.state.session_factory() as database_session:
        with pytest.raises(InvalidJobTransition):
            transition_job(
                database_session,
                job_id=job_id,
                target="completed",
                occurred_at=datetime.now(UTC),
            )
        database_session.rollback()

    fetched = client.get(f"/jobs/{job_id}").json()
    assert fetched["status"] == "pending"
    assert len(fetched["transitions"]) == 1


def test_failed_job_keeps_safe_diagnostic(client: TestClient) -> None:
    session_id = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()[
        "id"
    ]
    job_id = client.post(
        f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"}
    ).json()["id"]

    with client.app.state.session_factory() as database_session:
        transition_job(
            database_session,
            job_id=job_id,
            target="processing",
            occurred_at=datetime.now(UTC),
        )
        transition_job(
            database_session,
            job_id=job_id,
            target="failed",
            occurred_at=datetime.now(UTC),
            reason_code="synthetic_failure",
            failure_message="El fixture sintético fue rechazado.",
        )
        database_session.commit()

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["failure_code"] == "synthetic_failure"
    assert job["failure_message"] == "El fixture sintético fue rechazado."


def test_returns_safe_not_found_responses(client: TestClient) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/sessions/{missing_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": {"code": "not_found", "message": "Sesión inexistente."}}
