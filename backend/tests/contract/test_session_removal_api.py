"""Removing history hides a session without destroying immutable scene references."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from starlette.websockets import WebSocketDisconnect

from alembic import command
from flowsight.api.main import create_app
from flowsight.db.models import (
    JobKind,
    ProcessingJob,
    ReferenceFrame,
    SceneVersion,
    Session,
    SourceKind,
    VideoSource,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.jobs import create_job_for_session, transition_job

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    url = destructive_database_url()
    for key, value in {
        "FLOWSIGHT_ENV": "test",
        "FLOWSIGHT_DATABASE_URL": url,
        "FLOWSIGHT_WORKER_ID": "worker-removal-contract",
        "FLOWSIGHT_DETECTOR": "fake",
        "FLOWSIGHT_VIDEOS_DIR": str(tmp_path),
        "FLOWSIGHT_MACHINE_ID": "removal-tests",
    }.items():
        monkeypatch.setenv(key, value)
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    application = create_app()
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.state.engine.dispose()
        command.downgrade(config, "base")


def _synthetic(client: TestClient) -> str:
    response = client.post("/sessions", json={"name": "Removable", "camera_id": "cam-remove"})
    assert response.status_code == 201
    return response.json()["id"]


def _job(client: TestClient, session_id: str, status: str) -> str:
    response = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert response.status_code == 201
    job_id = response.json()["id"]
    if status != "pending":
        with client.app.state.session_factory.begin() as database:
            transition_job(
                database, job_id=job_id, target="processing", occurred_at=datetime.now(UTC)
            )
            if status != "processing":
                transition_job(
                    database,
                    job_id=job_id,
                    target=status,
                    occurred_at=datetime.now(UTC),
                    reason_code="test_failed" if status == "failed" else None,
                    failure_message="Test failure" if status == "failed" else None,
                )
    return job_id


def test_removal_is_idempotent_hides_history_and_keeps_persistent_rows(client: TestClient) -> None:
    session_id = _synthetic(client)
    job_id = _job(client, session_id, "completed")
    survivor = _synthetic(client)
    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.get(f"/sessions/{session_id}").status_code == 404
    assert [row["id"] for row in client.get("/sessions").json()] == [survivor]
    assert client.get("/processed-sessions").json() == []
    with client.app.state.session_factory() as database:
        stored = database.get(Session, uuid.UUID(session_id))
        assert stored is not None and stored.deleted_at is not None
        assert stored.deleted_at.tzinfo is not None
        assert database.get(ProcessingJob, uuid.UUID(job_id)).result_complete is True


def test_missing_session_removal_is_not_found(client: TestClient) -> None:
    assert client.delete(f"/sessions/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize("active_status", ["pending", "processing"])
def test_any_active_job_blocks_removal_even_when_latest_job_is_terminal(
    client: TestClient, active_status: str
) -> None:
    session_id = _synthetic(client)
    _job(client, session_id, active_status)
    _job(client, session_id, "completed")
    response = client.delete(f"/sessions/{session_id}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_has_active_jobs"
    assert client.get(f"/sessions/{session_id}").status_code == 200


def test_removed_session_cannot_be_used_by_public_results_or_work_endpoints(
    client: TestClient,
) -> None:
    session_id = _synthetic(client)
    job_id = _job(client, session_id, "completed")
    assert client.delete(f"/sessions/{session_id}").status_code == 204
    requests = [
        ("GET", f"/sessions/{session_id}/events", {}),
        ("GET", f"/sessions/{session_id}/shops/{uuid.uuid4()}/metrics", {}),
        ("GET", f"/sessions/{session_id}/reference-frame", {}),
        ("POST", f"/sessions/{session_id}/jobs", {"json": {"kind": "synthetic_base_flow"}}),
        ("PUT", f"/sessions/{session_id}/video", {"content": b"not read"}),
        ("POST", "/chat", {"json": {"session_id": session_id, "question": "tráfico"}}),
        ("GET", f"/jobs/{job_id}", {}),
        ("GET", f"/jobs/{job_id}/trace", {}),
        ("GET", f"/jobs/{job_id}/measures", {}),
        ("GET", f"/jobs/{job_id}/position-samples", {}),
        ("POST", f"/jobs/{job_id}/cancel", {}),
    ]
    for method, path, kwargs in requests:
        assert client.request(method, path, **kwargs).status_code == 404, path
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/ws/jobs/{job_id}/preview"):
            pass
    assert error.value.code == 4404


def _video(client: TestClient, name: str) -> tuple[str, str]:
    with client.app.state.session_factory.begin() as database:
        camera = get_or_create_camera(database, "cam-reference")
        session = Session(
            name=name,
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.VIDEO_FILE,
        )
        database.add(session)
        database.flush()
        relative = f"{session.id}.mp4"
        Path(client.app.state.settings.videos_dir, relative).write_bytes(b"retained video")
        database.add_all(
            [
                VideoSource(
                    session_id=session.id,
                    relative_path=relative,
                    original_filename="video.mp4",
                    size_bytes=14,
                    sha256="a" * 64,
                    origin_machine_id="test",
                    width=320,
                    height=240,
                    fps=10,
                    fps_is_estimated=False,
                    frame_count=10,
                    duration_seconds=1,
                ),
                ReferenceFrame(
                    session_id=session.id,
                    frame_index=0,
                    video_timestamp_seconds=0,
                    width=320,
                    height=240,
                    media_type="image/jpeg",
                    image=b"reference jpeg",
                ),
            ]
        )
        return str(session.id), str(camera.id)


def test_removal_retains_shared_scene_and_reference_frame_but_rejects_new_reference(
    client: TestClient,
) -> None:
    reference_id, camera_id = _video(client, "Reference")
    survivor, _camera_id = _video(client, "Survivor")
    with client.app.state.session_factory.begin() as database:
        version = SceneVersion(
            camera_id=uuid.UUID(camera_id),
            reference_session_id=uuid.UUID(reference_id),
            version_number=1,
            frame_width=320,
            frame_height=240,
        )
        database.add(version)
        database.flush()
        version_id = str(version.id)
    before = client.get(f"/scene-versions/{version_id}").json()
    assert client.delete(f"/sessions/{reference_id}").status_code == 204
    assert client.get(f"/scene-versions/{version_id}").json() == before
    assert client.get(f"/cameras/{camera_id}/scene-versions").json()[0]["id"] == version_id
    frame = client.get(f"/sessions/{reference_id}/reference-frame")
    assert frame.status_code == 200 and frame.content == b"reference jpeg"
    assert client.get(f"/sessions/{survivor}").json()["duplicate_session_ids"] == []
    response = client.post(
        f"/sessions/{survivor}/jobs",
        json={"kind": "video_analysis", "scene_version_id": version_id},
    )
    assert response.status_code == 201
    rejected = client.post(
        f"/cameras/{camera_id}/scene-versions",
        json={"reference_session_id": reference_id, "shops": []},
    )
    assert rejected.status_code == 422
    rules = {issue["rule"] for issue in rejected.json()["detail"]["errors"]}
    assert "reference_session_other_camera" in rules
    with client.app.state.session_factory() as database:
        source = database.get(VideoSource, uuid.UUID(reference_id))
        assert source is not None
        path = Path(client.app.state.settings.videos_dir, source.relative_path)
        assert path.read_bytes() == b"retained video"


def test_removed_unshared_reference_frame_is_hidden(client: TestClient) -> None:
    session_id, _camera_id = _video(client, "Unshared")
    assert client.delete(f"/sessions/{session_id}").status_code == 204
    assert client.get(f"/sessions/{session_id}/reference-frame").status_code == 404


def test_job_creation_waits_for_removal_and_cannot_start_after_it(client: TestClient) -> None:
    session_id = _synthetic(client)
    started = Event()

    def request_job():
        started.set()
        return client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})

    with ThreadPoolExecutor(max_workers=1) as pool:
        with client.app.state.session_factory.begin() as database:
            database.execute(
                text("UPDATE sessions SET deleted_at = now() WHERE id = :id"),
                {"id": session_id},
            )
            future = pool.submit(request_job)
            assert started.wait(timeout=2)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.2)
        assert future.result(timeout=5).status_code == 404
    with client.app.state.session_factory() as database:
        assert list(database.scalars(select(ProcessingJob))) == []


def test_removal_waits_for_job_creation_and_sees_the_new_active_job(client: TestClient) -> None:
    session_id = _synthetic(client)
    started = Event()

    def request_removal():
        started.set()
        return client.delete(f"/sessions/{session_id}")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with client.app.state.session_factory.begin() as database:
            flow_session = database.get(Session, uuid.UUID(session_id))
            create_job_for_session(database, flow_session, JobKind.SYNTHETIC_BASE_FLOW, None)
            future = pool.submit(request_removal)
            assert started.wait(timeout=2)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.2)
        assert future.result(timeout=5).status_code == 409
    assert client.get(f"/sessions/{session_id}").status_code == 200
