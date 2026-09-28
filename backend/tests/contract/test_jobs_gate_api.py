"""Contract tests for the `video_analysis` job gate (specs/004, T028).

Covers `POST /sessions/{session_id}/jobs` as extended by contracts/openapi.yaml:
`video_analysis` requires `scene_version_id` and `synthetic_base_flow` forbids it
(FR-025 to FR-028, research R12). Order of the checks (T034):
`job_kind_mismatch` → `scene_version_not_allowed` → `scene_version_required`, then the
gate `scene_not_configured` (409) → `scene_version_other_camera` (422) →
`aspect_ratio_mismatch` (409). Every error body is `{"detail": {"code", "message", ...}}`.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import func, select

from alembic import command
from flowsight.api.main import create_app
from flowsight.db.models import JobKind, JobStatus, ProcessingJob
from flowsight.video.fixtures import write_clip

BACKEND_DIR = Path(__file__).resolve().parents[2]
MACHINE_ID = "equipo-test"
HD = (1280, 720)
FULL_HD = (1920, 1080)
VGA = (640, 480)

# Valid geometry on a 1280x720 reference frame (same as test_scene_api.py).
FRONT = [[0.1, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]]
INTERIOR = [[0.1, 0.2], [0.3, 0.2], [0.3, 0.45], [0.1, 0.45]]
LINE = {"start": [0.05, 0.6], "end": [0.35, 0.6], "entry_direction": "a_to_b"}


# --- Fixtures (same setup as test_scene_api.py) -------------------------------------


@pytest.fixture(scope="module")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[int, int], Path]:
    directory = tmp_path_factory.mktemp("gate-clips")
    return {size: write_clip(directory, codec="mp4v", size=size) for size in (HD, FULL_HD, VGA)}


@pytest.fixture()
def database_url() -> Iterator[str]:
    url = destructive_database_url()
    config = Config(BACKEND_DIR / "alembic.ini")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FLOWSIGHT_DATABASE_URL", url)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    yield url
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FLOWSIGHT_DATABASE_URL", url)
        command.downgrade(config, "base")


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch, database_url: str, tmp_path: Path
) -> Iterator[TestClient]:
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FLOWSIGHT_API_PORT", "8000")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-contract")
    monkeypatch.setenv("FLOWSIGHT_PREVIEW_MAX_FPS", "5")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(videos_dir))
    monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", MACHINE_ID)
    application = create_app()
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.state.engine.dispose()


def _create_camera(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post("/cameras", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _register_video(
    client: TestClient, clips: dict[tuple[int, int], Path], camera_id: str, size: tuple[int, int]
) -> dict[str, Any]:
    response = client.post(
        "/video-sessions",
        params={
            "name": f"Sesión {size[0]}x{size[1]}",
            "registered_camera_id": camera_id,
            "filename": "a.mp4",
        },
        content=clips[size].read_bytes(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["reference_frame"]["width"], body["reference_frame"]["height"]) == size
    return body


def _create_version(
    client: TestClient,
    camera_id: str,
    reference_session: dict[str, Any],
    base_version_id: str | None = None,
) -> dict[str, Any]:
    shop = {
        "shop_id": None,
        "name": "Local A",
        "zones": {"front": copy.deepcopy(FRONT), "interior": copy.deepcopy(INTERIOR)},
        "entry_line": copy.deepcopy(LINE),
    }
    payload: dict[str, Any] = {"reference_session_id": reference_session["id"], "shops": [shop]}
    if base_version_id is not None:
        payload["base_version_id"] = base_version_id
    response = client.post(f"/cameras/{camera_id}/scene-versions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def camera(client: TestClient) -> dict[str, Any]:
    return _create_camera(client, "Entrada norte")


@pytest.fixture()
def other_camera(client: TestClient) -> dict[str, Any]:
    return _create_camera(client, "Entrada sur")


@pytest.fixture()
def hd_session(
    client: TestClient, clips: dict[tuple[int, int], Path], camera: dict[str, Any]
) -> dict[str, Any]:
    return _register_video(client, clips, camera["id"], HD)


@pytest.fixture()
def version(
    client: TestClient, camera: dict[str, Any], hd_session: dict[str, Any]
) -> dict[str, Any]:
    """Version 1 of `camera`, drawn on the 1280x720 session."""

    created = _create_version(client, camera["id"], hd_session)
    assert (created["frame_width"], created["frame_height"]) == HD
    return created


@pytest.fixture()
def other_version(
    client: TestClient, clips: dict[tuple[int, int], Path], other_camera: dict[str, Any]
) -> dict[str, Any]:
    """Version 1 of `other_camera`, drawn on its own 1280x720 session."""

    other_session = _register_video(client, clips, other_camera["id"], HD)
    return _create_version(client, other_camera["id"], other_session)


@pytest.fixture()
def synthetic_session(client: TestClient, camera: dict[str, Any]) -> dict[str, Any]:
    """Synthetic session (specs/002) of the same registered camera as `camera`."""

    response = client.post("/sessions", json={"name": "Sintética", "camera_id": camera["name"]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_kind"] == "synthetic"
    return body


# --- Helpers -----------------------------------------------------------------------


def _post_job(
    client: TestClient, session_id: str, kind: str, scene_version_id: str | None = None
) -> Response:
    payload: dict[str, Any] = {"kind": kind}
    if scene_version_id is not None:
        payload["scene_version_id"] = scene_version_id
    return client.post(f"/sessions/{session_id}/jobs", json=payload)


def _job_count(client: TestClient) -> int:
    with client.app.state.session_factory() as database_session:
        return database_session.scalar(select(func.count()).select_from(ProcessingJob))


def _assert_rejected(
    client: TestClient, response: Response, status_code: int, code: str
) -> dict[str, Any]:
    """The request is rejected with `{"detail": {"code", "message"}}` and no job is created."""

    assert response.status_code == status_code, response.text
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert isinstance(detail["message"], str) and detail["message"]
    assert _job_count(client) == 0
    return detail


def _stored_job(client: TestClient, job_id: str) -> ProcessingJob:
    with client.app.state.session_factory() as database_session:
        job = database_session.get(ProcessingJob, job_id)
        assert job is not None
        database_session.expunge(job)
        return job


def _assert_pending_video_job(
    client: TestClient,
    response: Response,
    session: dict[str, Any],
    scene_version_id: str,
    camera_id: str,
) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session_id"] == session["id"]
    assert body["kind"] == "video_analysis"
    assert body["status"] == "pending"
    assert body["scene_version_id"] == scene_version_id
    assert [item["to_status"] for item in body["transitions"]] == ["pending"]
    assert body["transitions"][0]["from_status"] is None

    # `registered_camera_id` is not part of the job response: check it in the database.
    stored = _stored_job(client, body["id"])
    assert stored.kind is JobKind.VIDEO_ANALYSIS
    assert stored.status is JobStatus.PENDING
    assert str(stored.scene_version_id) == scene_version_id
    assert str(stored.registered_camera_id) == camera_id
    return body


# --- Gate, one condition at a time -------------------------------------------------


def test_camera_without_versions_is_rejected_with_scene_not_configured(
    client: TestClient,
    camera: dict[str, Any],
    hd_session: dict[str, Any],
    other_version: dict[str, Any],
) -> None:
    # The camera of the session has no versions; the only existing one is another camera's.
    listing = client.get(f"/cameras/{camera['id']}/scene-versions")
    assert listing.json() == []

    response = _post_job(client, hd_session["id"], "video_analysis", other_version["id"])

    _assert_rejected(client, response, 409, "scene_not_configured")


def test_camera_without_versions_and_no_scene_version_id_is_scene_not_configured(
    client: TestClient, camera: dict[str, Any], hd_session: dict[str, Any]
) -> None:
    # scene_not_configured is checked before scene_version_required: with no versions
    # the UI has nothing to preselect and must point the user to the editor.
    response = _post_job(client, hd_session["id"], "video_analysis")

    _assert_rejected(client, response, 409, "scene_not_configured")


def test_unknown_scene_version_id_reads_as_other_camera(
    client: TestClient, hd_session: dict[str, Any], version: dict[str, Any]
) -> None:
    response = _post_job(
        client, hd_session["id"], "video_analysis", "00000000-0000-4000-8000-000000000000"
    )

    _assert_rejected(client, response, 422, "scene_version_other_camera")


def test_missing_scene_version_id_is_rejected_when_versions_exist(
    client: TestClient, hd_session: dict[str, Any], version: dict[str, Any]
) -> None:
    response = _post_job(client, hd_session["id"], "video_analysis")

    _assert_rejected(client, response, 422, "scene_version_required")


def test_explicit_null_scene_version_id_is_rejected_when_versions_exist(
    client: TestClient, hd_session: dict[str, Any], version: dict[str, Any]
) -> None:
    response = client.post(
        f"/sessions/{hd_session['id']}/jobs",
        json={"kind": "video_analysis", "scene_version_id": None},
    )

    _assert_rejected(client, response, 422, "scene_version_required")


def test_version_of_another_camera_is_rejected(
    client: TestClient,
    hd_session: dict[str, Any],
    version: dict[str, Any],
    other_version: dict[str, Any],
) -> None:
    response = _post_job(client, hd_session["id"], "video_analysis", other_version["id"])

    _assert_rejected(client, response, 422, "scene_version_other_camera")


def test_different_aspect_ratio_is_rejected_with_both_ratios(
    client: TestClient,
    clips: dict[tuple[int, int], Path],
    camera: dict[str, Any],
    version: dict[str, Any],
) -> None:
    vga_session = _register_video(client, clips, camera["id"], VGA)

    response = _post_job(client, vga_session["id"], "video_analysis", version["id"])

    detail = _assert_rejected(client, response, 409, "aspect_ratio_mismatch")
    assert detail["video_aspect_ratio"] == pytest.approx(640 / 480, abs=1e-3)
    assert detail["version_aspect_ratio"] == pytest.approx(1280 / 720, abs=1e-3)


def test_same_aspect_ratio_with_other_resolution_creates_pending_job(
    client: TestClient,
    clips: dict[tuple[int, int], Path],
    camera: dict[str, Any],
    version: dict[str, Any],
) -> None:
    full_hd_session = _register_video(client, clips, camera["id"], FULL_HD)

    response = _post_job(client, full_hd_session["id"], "video_analysis", version["id"])

    body = _assert_pending_video_job(client, response, full_hd_session, version["id"], camera["id"])
    fetched = client.get(f"/jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["scene_version_id"] == version["id"]
    assert fetched.json()["status"] == "pending"


def test_chosen_older_version_stays_associated_after_newer_versions(
    client: TestClient,
    camera: dict[str, Any],
    hd_session: dict[str, Any],
    version: dict[str, Any],
) -> None:
    newer = _create_version(client, camera["id"], hd_session, base_version_id=version["id"])
    assert newer["version_number"] == version["version_number"] + 1

    # FR-026: any earlier version of the same camera may be chosen, not only the latest.
    response = _post_job(client, hd_session["id"], "video_analysis", version["id"])
    body = _assert_pending_video_job(client, response, hd_session, version["id"], camera["id"])

    # FR-027: a version created afterwards does not change the association.
    _create_version(client, camera["id"], hd_session, base_version_id=newer["id"])
    assert client.get(f"/jobs/{body['id']}").json()["scene_version_id"] == version["id"]
    assert str(_stored_job(client, body["id"]).scene_version_id) == version["id"]


# --- Gate order when several conditions fail ---------------------------------------


def test_scene_not_configured_wins_over_other_camera_and_aspect_ratio(
    client: TestClient,
    clips: dict[tuple[int, int], Path],
    camera: dict[str, Any],
    other_version: dict[str, Any],
) -> None:
    # No versions on the camera, version of another camera and 4:3 against 16:9.
    vga_session = _register_video(client, clips, camera["id"], VGA)

    response = _post_job(client, vga_session["id"], "video_analysis", other_version["id"])

    _assert_rejected(client, response, 409, "scene_not_configured")


def test_other_camera_wins_over_aspect_ratio(
    client: TestClient,
    clips: dict[tuple[int, int], Path],
    camera: dict[str, Any],
    version: dict[str, Any],
    other_version: dict[str, Any],
) -> None:
    # The camera has versions, but the chosen one is another camera's and 4:3 against 16:9.
    vga_session = _register_video(client, clips, camera["id"], VGA)

    response = _post_job(client, vga_session["id"], "video_analysis", other_version["id"])

    _assert_rejected(client, response, 422, "scene_version_other_camera")


def test_job_kind_mismatch_wins_over_scene_version_not_allowed(
    client: TestClient, synthetic_session: dict[str, Any], version: dict[str, Any]
) -> None:
    response = _post_job(client, synthetic_session["id"], "video_analysis", version["id"])

    _assert_rejected(client, response, 422, "job_kind_mismatch")


def test_job_kind_mismatch_wins_over_gate_on_video_session(
    client: TestClient,
    clips: dict[tuple[int, int], Path],
    camera: dict[str, Any],
    other_version: dict[str, Any],
) -> None:
    # Wrong kind for a video session whose camera has no versions and a 4:3 video.
    vga_session = _register_video(client, clips, camera["id"], VGA)

    response = _post_job(client, vga_session["id"], "synthetic_base_flow", other_version["id"])

    _assert_rejected(client, response, 422, "job_kind_mismatch")


# --- Synthetic sessions and job kinds -----------------------------------------------


def test_synthetic_session_rejects_scene_version_id(
    client: TestClient, synthetic_session: dict[str, Any], version: dict[str, Any]
) -> None:
    # Same registered camera as the version: the only reason is that the session is synthetic.
    response = _post_job(client, synthetic_session["id"], "synthetic_base_flow", version["id"])

    _assert_rejected(client, response, 422, "scene_version_not_allowed")


def test_synthetic_base_flow_on_video_session_is_job_kind_mismatch(
    client: TestClient, hd_session: dict[str, Any], version: dict[str, Any]
) -> None:
    response = _post_job(client, hd_session["id"], "synthetic_base_flow")

    _assert_rejected(client, response, 422, "job_kind_mismatch")


def test_video_analysis_on_synthetic_session_is_job_kind_mismatch(
    client: TestClient, synthetic_session: dict[str, Any]
) -> None:
    response = _post_job(client, synthetic_session["id"], "video_analysis")

    _assert_rejected(client, response, 422, "job_kind_mismatch")


def test_synthetic_session_keeps_specs_002_behavior(
    client: TestClient, synthetic_session: dict[str, Any]
) -> None:
    response = _post_job(client, synthetic_session["id"], "synthetic_base_flow")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "synthetic_base_flow"
    assert body["status"] == "pending"
    assert body["scene_version_id"] is None
    assert [item["to_status"] for item in body["transitions"]] == ["pending"]
    assert _stored_job(client, body["id"]).scene_version_id is None
