from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient

from alembic import command
from flowsight.api.main import create_app

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


def _assert_camera(body: dict, name: str) -> None:
    assert set(body) >= {"id", "name", "created_at"}
    uuid.UUID(body["id"])
    assert body["name"] == name
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_creates_camera(client: TestClient) -> None:
    response = client.post("/cameras", json={"name": "Cam 01"})

    assert response.status_code == 201
    _assert_camera(response.json(), "Cam 01")


def test_stores_name_without_surrounding_whitespace(client: TestClient) -> None:
    response = client.post("/cameras", json={"name": "  Entrada norte \t"})

    assert response.status_code == 201
    assert response.json()["name"] == "Entrada norte"


@pytest.mark.parametrize(
    "name", ["x" * 120, "  " + "x" * 120 + "  "], ids=["120", "120-con-espacios"]
)
def test_accepts_names_up_to_120_characters_after_strip(client: TestClient, name: str) -> None:
    response = client.post("/cameras", json={"name": name})

    assert response.status_code == 201
    assert response.json()["name"] == "x" * 120


@pytest.mark.parametrize(
    "payload",
    [{"name": ""}, {"name": "   \t\n"}, {"name": "x" * 121}, {}],
    ids=["vacio", "solo-espacios", "121", "sin-name"],
)
def test_rejects_invalid_names(client: TestClient, payload: dict) -> None:
    response = client.post("/cameras", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert client.get("/cameras").json() == []


@pytest.mark.parametrize(
    ("first", "second"),
    [("Cam 01", " cam 01 "), ("Straße", "STRASSE")],
    ids=["espacios-y-mayusculas", "casefold"],
)
def test_rejects_duplicate_normalized_name_with_existing_camera(
    client: TestClient, first: str, second: str
) -> None:
    existing = client.post("/cameras", json={"name": first}).json()

    response = client.post("/cameras", json={"name": second})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "camera_exists"
    assert detail["message"]
    assert detail["existing_camera"] == existing
    assert client.get("/cameras").json() == [existing]


def test_lists_created_and_synthetic_session_cameras_ordered_by_name(
    client: TestClient,
) -> None:
    created = client.post("/cameras", json={"name": "Pasillo"}).json()
    session = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"})
    assert session.status_code == 201

    response = client.get("/cameras")

    assert response.status_code == 200
    cameras = response.json()
    # Case-insensitive order, whatever the database collation.
    assert [camera["name"] for camera in cameras] == ["camera-01", "Pasillo"]
    assert cameras[1] == created
    _assert_camera(cameras[0], "camera-01")
