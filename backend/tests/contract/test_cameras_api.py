from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from sqlalchemy import select

from flowsight.api.main import create_app
from flowsight.db.models import Camera
from flowsight.services import cameras

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


def test_rename_keeps_session_reference_and_checks_duplicate_names(client: TestClient) -> None:
    session = client.post("/sessions", json={"name": "Local", "camera_id": "Entrada"}).json()
    camera_id = session["camera"]["id"]
    other = client.post("/cameras", json={"name": "Otra"}).json()
    renamed = client.patch(f"/cameras/{camera_id}", json={"name": " Norte "})
    assert renamed.status_code == 200
    assert renamed.json()["id"] == camera_id
    assert renamed.json()["name"] == "Norte"
    assert client.get(f"/sessions/{session['id']}").json()["camera"]["name"] == "Norte"
    duplicate = client.patch(f"/cameras/{camera_id}", json={"name": "otra"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "camera_exists"
    assert client.get(f"/sessions/{session['id']}").json()["camera"]["name"] == "Norte"
    assert any(item["id"] == other["id"] for item in client.get("/cameras").json())


def test_remove_camera_keeps_history_and_reserves_name(client: TestClient) -> None:
    session = client.post("/sessions", json={"name": "Local", "camera_id": "Entrada"}).json()
    camera_id = session["camera"]["id"]
    assert client.delete(f"/cameras/{camera_id}").status_code == 204
    assert client.delete(f"/cameras/{camera_id}").status_code == 204
    assert client.get("/cameras").json() == []
    assert client.get(f"/sessions/{session['id']}").status_code == 200
    assert client.post("/cameras", json={"name": " entrada "}).status_code == 409
    assert (
        client.post("/sessions", json={"name": "Nuevo", "camera_id": "Entrada"}).status_code == 409
    )
    job = client.post(f"/sessions/{session['id']}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 409
    assert job.json()["detail"]["code"] == "camera_removed"
    assert client.patch(f"/cameras/{camera_id}", json={"name": "Nueva"}).status_code == 404


def test_active_job_blocks_camera_removal(client: TestClient) -> None:
    session = client.post("/sessions", json={"name": "Local", "camera_id": "Entrada"}).json()
    job = client.post(f"/sessions/{session['id']}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 201
    response = client.delete(f"/cameras/{session['camera']['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "camera_has_active_jobs"
    assert len(client.get("/cameras").json()) == 1


@pytest.mark.parametrize("endpoint", ["/cameras", "/sessions"])
def test_resolves_name_after_rename_between_insert_and_lookup(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    existing = client.post("/cameras", json={"name": "Entrada"}).json()
    original = cameras._get_by_name
    renamed = False

    def lookup(database, name):
        nonlocal renamed
        if not renamed:
            renamed = True
            camera = database.scalar(select(Camera).where(Camera.id == uuid.UUID(existing["id"])))
            camera.name = "Renombrada"
            camera.name_key = "renombrada"
            database.flush()
        return original(database, name)

    monkeypatch.setattr(cameras, "_get_by_name", lookup)
    payload = (
        {"name": "Entrada"} if endpoint == "/cameras" else {"name": "Local", "camera_id": "Entrada"}
    )
    response = client.post(endpoint, json=payload)
    assert response.status_code == 201
    resolved = response.json() if endpoint == "/cameras" else response.json()["camera"]
    assert resolved["id"] != existing["id"]
    assert resolved["name"] == "Entrada"
