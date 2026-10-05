"""Live preparation is distinct from a job and requires a fresh frame confirmation."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from flowsight.api.main import create_app
from flowsight.capture.contracts import CaptureError, CaptureProbeResult
from flowsight.db.models import LiveAnalysisState, LiveSource, ProcessingJob, ReferenceFrame
from flowsight.worker.lifecycle import claim_next_job
from flowsight.worker.live_control import MachineLease


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/live/devices"),
        ("get", "/jobs/00000000-0000-0000-0000-000000000001/live-results"),
        ("get", "/jobs/00000000-0000-0000-0000-000000000001/live-events"),
        ("post", "/sessions/00000000-0000-0000-0000-000000000001/live/check"),
        ("post", "/jobs/00000000-0000-0000-0000-000000000001/live/stop"),
    ],
)
def test_live_routes_return_safe_503_on_database_outage(live_client, monkeypatch, method, path):
    from unittest.mock import Mock

    from sqlalchemy.exc import SQLAlchemyError

    client, _, _ = live_client
    factory = Mock(side_effect=SQLAlchemyError("private-database-address"))
    factory.begin.side_effect = SQLAlchemyError("private-database-address")
    monkeypatch.setattr(client.app.state, "session_factory", factory)
    response = getattr(client, method)(path)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
    assert "private-database-address" not in response.text


class ProbeGateway:
    failure: str | None = None
    available = True

    async def probe(self, **_kwargs):
        if self.failure:
            raise CaptureError(self.failure)
        return CaptureProbeResult(b"jpeg-reference", 1280, 720, "fake", 0, 30)


def test_device_selector_returns_native_names_instead_of_guessed_indices(live_client, monkeypatch):
    import flowsight.api.live_routes as routes

    client, _, _ = live_client
    monkeypatch.setattr(
        routes,
        "list_webcams",
        lambda: [
            {"device_index": 0, "label": "Integrated Camera", "verified": False},
            {"device_index": 1, "label": "USB Camera", "verified": False},
        ],
        raising=False,
    )
    response = client.get("/live/devices")
    assert response.status_code == 200
    assert response.json()["candidates"] == [
        {"device_index": 0, "label": "Integrated Camera", "verified": False},
        {"device_index": 1, "label": "USB Camera", "verified": False},
    ]


def test_device_discovery_failure_returns_safe_error(live_client, monkeypatch):
    import flowsight.api.live_routes as routes

    client, _, _ = live_client

    def failed():
        raise CaptureError("device_enumeration_failed")

    monkeypatch.setattr(routes, "list_webcams", failed, raising=False)
    response = client.get("/live/devices")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "device_enumeration_failed"


@pytest.fixture
def live_client(live_engine, monkeypatch):
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv(
        "FLOWSIGHT_DATABASE_URL", live_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", "expo-test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-expo")
    monkeypatch.setenv("FLOWSIGHT_LIVE_CHANNEL_TOKEN", "test-only-local-channel")
    application = create_app()
    application.state.live_channel = ProbeGateway()
    lease = MachineLease(application.state.engine, "expo-test", "worker-expo")
    assert lease.acquire(datetime.now(UTC))
    with TestClient(application) as client:
        camera = client.post("/cameras", json={"name": "Expo"}).json()
        yield client, camera["id"], lease
    lease.release()
    application.state.engine.dispose()


def prepare(client, camera_id):
    return client.post(
        "/live/sessions",
        json={
            "name": "Stand",
            "registered_camera_id": camera_id,
            "device_index": 0,
            "label_mode": "directions",
        },
    )


def scene(client, camera_id, session_id):
    response = client.post(
        f"/cameras/{camera_id}/scene-versions",
        json={
            "reference_session_id": session_id,
            "shops": [
                {
                    "name": "Paso",
                    "zones": {
                        "front": [[0.1, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]],
                        "interior": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.45], [0.1, 0.45]],
                    },
                    "entry_line": {
                        "start": [0.05, 0.6],
                        "end": [0.35, 0.6],
                        "entry_direction": "a_to_b",
                    },
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_retry_invalidates_previous_frame_confirmation(live_client):
    client, camera_id, lease = live_client
    session_id = uuid.UUID(prepare(client, camera_id).json()["id"])
    scene_id = scene(client, camera_id, str(session_id))
    initial = client.post(f"/sessions/{session_id}/live/check").json()["check_token"]
    job_id = uuid.UUID(
        client.post(
            f"/sessions/{session_id}/live/start",
            json={
                "scene_version_id": scene_id,
                "check_token": initial,
                "frame_confirmed": True,
            },
        ).json()["id"]
    )
    factory = client.app.state.session_factory
    with factory.begin() as database:
        claim_next_job(
            database,
            "worker-expo",
            datetime.now(UTC),
            machine_id="expo-test",
            owner_epoch=lease.owner_epoch,
        )
        database.get(LiveAnalysisState, job_id).capture_status = "awaiting_confirmation"

    def token():
        return client.app.state.live_checks.issue(
            session_id=session_id,
            machine_id="expo-test",
            owner_epoch=lease.owner_epoch,
            device_index=0,
            width=1280,
            height=720,
            job_id=job_id,
            segment_index=1,
        )

    old_token = token()
    assert client.post(f"/jobs/{job_id}/live/retry").status_code == 202
    with factory.begin() as database:
        database.get(LiveAnalysisState, job_id).capture_status = "awaiting_confirmation"
    lease.heartbeat(datetime.now(UTC))
    expired = client.post(
        f"/jobs/{job_id}/live/confirm-resume",
        json={
            "check_token": old_token,
            "frame_confirmed": True,
        },
    )
    assert expired.status_code == 409 and expired.json()["detail"]["code"] == "check_expired"
    fresh = token()
    refused = client.post(
        f"/jobs/{job_id}/live/confirm-resume",
        json={
            "check_token": fresh,
            "frame_confirmed": False,
        },
    )
    assert refused.status_code == 409
    accepted = client.post(
        f"/jobs/{job_id}/live/confirm-resume",
        json={
            "check_token": fresh,
            "frame_confirmed": True,
        },
    )
    assert accepted.status_code == 202 and accepted.json()["resume_requested"]
    repeated = client.post(
        f"/jobs/{job_id}/live/confirm-resume",
        json={
            "check_token": fresh,
            "frame_confirmed": True,
        },
    )
    assert repeated.status_code == 409


def test_prepare_persists_only_reference_and_no_job(live_client):
    client, camera, _ = live_client
    response = prepare(client, camera)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["source_kind"] == "webcam" and data["video"] is None
    assert data["live_source"]["machine_id"] == "expo-test"
    session_id = uuid.UUID(data["id"])
    with client.app.state.session_factory() as database:
        assert database.get(LiveSource, session_id).width == 1280
        assert database.get(ReferenceFrame, session_id).image == b"jpeg-reference"
        assert database.scalar(select(func.count()).select_from(ProcessingJob)) == 0


def test_failed_probe_creates_no_session_and_releases_device(live_client):
    client, camera, _ = live_client
    client.app.state.live_channel.failure = "device_unavailable"
    response = prepare(client, camera)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "device_unavailable"
    client.app.state.live_channel.failure = None
    assert prepare(client, camera).status_code == 201


def test_start_requires_confirmation_and_consumes_check(live_client):
    client, camera, _ = live_client
    prepared = prepare(client, camera)
    assert prepared.status_code == 201, prepared.text
    session_id = prepared.json()["id"]
    version = scene(client, camera, session_id)
    check = client.post(f"/sessions/{session_id}/live/check")
    assert check.status_code == 200, check.text
    body = {
        "scene_version_id": version,
        "check_token": check.json()["check_token"],
        "frame_confirmed": False,
    }
    assert client.post(f"/sessions/{session_id}/live/start", json=body).status_code == 409
    body["frame_confirmed"] = True
    started = client.post(f"/sessions/{session_id}/live/start", json=body)
    assert started.status_code == 201, started.text
    job = started.json()
    assert job["kind"] == "live_analysis" and job["status"] == "pending"
    assert job["frames_total"] is None and job["progress_percent"] is None
    fetched = client.get(f"/jobs/{job['id']}").json()
    assert fetched["live_state"]["capture_status"] == "starting"
    assert fetched["live_state"]["elapsed_capture_seconds"] == 0
    refused = client.post(f"/jobs/{job['id']}/cancel")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "use_live_stop"
    assert client.post(f"/sessions/{session_id}/live/start", json=body).status_code == 409
    stopped = client.post(f"/jobs/{job['id']}/live/stop")
    assert stopped.status_code == 202, stopped.text
    assert stopped.json()["status"] == "pending"
    assert client.post(f"/jobs/{job['id']}/live/stop").json() == stopped.json()


def test_foreign_and_expired_check_cannot_start(live_client):
    client, camera, _ = live_client
    first = prepare(client, camera)
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    second_id = prepare(client, camera).json()["id"]
    version = scene(client, camera, first_id)
    token = client.post(f"/sessions/{first_id}/live/check").json()["check_token"]
    body = {"scene_version_id": version, "check_token": token, "frame_confirmed": True}
    assert client.post(f"/sessions/{second_id}/live/start", json=body).status_code == 409
    client.app.state.live_checks.expire(token)
    response = client.post(f"/sessions/{first_id}/live/start", json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "check_expired"


def test_removed_camera_is_rechecked_after_probe(live_client):
    client, camera, _ = live_client
    gateway = client.app.state.live_channel
    original = gateway.probe

    async def removing_probe(**kwargs):
        from flowsight.services.cameras import remove_camera

        with client.app.state.session_factory.begin() as database:
            remove_camera(database, uuid.UUID(camera))
        return await original(**kwargs)

    gateway.probe = removing_probe
    response = prepare(client, camera)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "camera_removed"


@pytest.mark.parametrize("index", [-1, 33, "rtsp://camera"])
def test_device_index_allowlist(live_client, index):
    client, camera, _ = live_client
    response = client.post(
        "/live/sessions",
        json={"name": "Expo", "registered_camera_id": camera, "device_index": index},
    )
    assert response.status_code == 422
