from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text

from alembic import command
from flowsight.api.main import create_app
from flowsight.video.fixtures import CLIP_FPS, CLIP_FRAMES, MpegUnavailable, write_clip
from flowsight.video.fixtures import write_mpeg_clip as _write_mpeg_clip

BACKEND_DIR = Path(__file__).resolve().parents[2]
MACHINE_ID = "equipo-test"
REFERENCE_FRAME_CACHE = "private, max-age=86400, immutable"
SUMMARY_FIELDS = {"id", "name", "source_kind", "camera", "created_at"}

ClientFactory = Callable[..., Any]


@pytest.fixture(scope="module")
def clips(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    directory = tmp_path_factory.mktemp("video-sessions-clips")
    clip_720 = write_clip(directory, codec="mp4v", size=(1280, 720))
    clip_480 = write_clip(directory, codec="mjpg", size=(640, 480))
    data = clip_480.read_bytes()
    truncated = directory / "truncado.avi"
    # AVI headers plus the start of the first frame: opens but decodes nothing.
    truncated.write_bytes(data[: data.index(b"movi") + 64])
    text_file = directory / "notas.mp4"
    text_file.write_text("esto no es un video\n" * 100, encoding="utf-8")
    avi_720 = write_clip(directory, codec="mjpg", size=(1280, 720)).read_bytes()
    half = directory / "mitad.avi"
    # T049, scenario 1.4: half of the bytes; the header still declares every frame.
    half.write_bytes(avi_720[: len(avi_720) // 2])
    return {
        "mp4": clip_720,
        "avi": clip_480,
        "truncated": truncated,
        "half": half,
        "text": text_file,
    }


@pytest.fixture(scope="module")
def mpeg_clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    try:
        return _write_mpeg_clip(tmp_path_factory.mktemp("video-sessions-mpeg"))
    except MpegUnavailable as error:
        pytest.skip(f"el OpenCV instalado no escribe MPEG-1 decodificable: {error}")


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
def videos_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "videos"
    directory.mkdir()
    return directory


@pytest.fixture()
def make_client(
    monkeypatch: pytest.MonkeyPatch, database_url: str, videos_dir: Path
) -> Iterator[ClientFactory]:
    """Start the API with the given per-machine settings; several may coexist."""

    stack: list[Any] = []

    def factory(videos: Path | None = videos_dir, machine_id: str | None = MACHINE_ID):
        monkeypatch.setenv("FLOWSIGHT_ENV", "test")
        monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
        monkeypatch.setenv("FLOWSIGHT_API_HOST", "127.0.0.1")
        monkeypatch.setenv("FLOWSIGHT_API_PORT", "8000")
        monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-contract")
        monkeypatch.setenv("FLOWSIGHT_PREVIEW_MAX_FPS", "5")
        # Empty values count as "not configured" and override any local `.env`.
        monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", "" if videos is None else str(videos))
        monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", machine_id or "")
        context = _running_client()
        stack.append(context)
        return context.__enter__()

    yield factory
    for context in reversed(stack):
        context.__exit__(None, None, None)


@contextmanager
def _running_client() -> Iterator[TestClient]:
    application = create_app()
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.state.engine.dispose()


@pytest.fixture()
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


@pytest.fixture()
def camera(client: TestClient) -> dict[str, Any]:
    response = client.post("/cameras", json={"name": "Entrada norte"})
    assert response.status_code == 201
    return response.json()


def _register(
    client: TestClient,
    content: bytes,
    camera_id: str,
    filename: str = "toma.avi",
    name: str = "Sesión de video",
) -> Response:
    return client.post(
        "/video-sessions",
        params={"name": name, "registered_camera_id": camera_id, "filename": filename},
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )


def _relink(client: TestClient, session_id: str, content: bytes) -> Response:
    return client.put(
        f"/sessions/{session_id}/video",
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )


def _stored_files(videos_dir: Path) -> list[str]:
    return sorted(
        path.relative_to(videos_dir).as_posix() for path in videos_dir.rglob("*") if path.is_file()
    )


def _count(client: TestClient, table: str) -> int:
    with client.app.state.session_factory() as database_session:
        return database_session.scalar(text(f"SELECT count(*) FROM {table}"))


def _assert_nothing_created(client: TestClient, videos_dir: Path) -> None:
    assert client.get("/sessions").json() == []
    assert _count(client, "video_sources") == 0
    assert _count(client, "reference_frames") == 0
    assert _stored_files(videos_dir) == []


def _assert_safe_error(response: Response, tmp_path: Path, database_url: str) -> None:
    """FR-013: no absolute path of this machine and no connection string."""

    body = response.text
    assert str(tmp_path) not in body
    assert tmp_path.as_posix() not in body
    assert database_url not in body
    detail = response.json()["detail"]
    assert detail["code"]
    assert detail["message"]


def _without_availability(detail: dict[str, Any]) -> dict[str, Any]:
    video = {key: value for key, value in detail["video"].items() if key != "availability"}
    return {**detail, "video": video}


def test_registers_video_session_with_full_detail(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, clips: dict[str, Path]
) -> None:
    content = clips["mp4"].read_bytes()

    response = _register(
        client, content, camera["id"], filename="C:\\fakepath\\toma 1.mp4", name="  Tarde  "
    )

    assert response.status_code == 201
    body = response.json()
    session_id = body["id"]
    assert body["name"] == "Tarde"
    assert body["source_kind"] == "video_file"
    assert body["camera"] == camera
    assert body["camera_id"] == camera["name"]
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert body["duplicate_session_ids"] == []

    video = body["video"]
    assert video["relative_path"] == f"{session_id}.mp4"
    assert video["original_filename"] == "toma 1.mp4"
    assert video["size_bytes"] == len(content)
    assert video["sha256"] == hashlib.sha256(content).hexdigest()
    assert video["origin_machine_id"] == MACHINE_ID
    assert (video["width"], video["height"]) == (1280, 720)
    assert video["fps"] == CLIP_FPS
    assert video["fps_is_estimated"] is False
    assert video["frame_count"] == CLIP_FRAMES
    assert video["declared_frame_count"] == CLIP_FRAMES
    assert video["appears_incomplete"] is False
    assert video["duration_seconds"] == CLIP_FRAMES / CLIP_FPS
    assert datetime.fromisoformat(video["registered_at"]).tzinfo is not None
    assert video["availability"] == "available"

    assert body["reference_frame"] == {
        "frame_index": 0,
        "video_timestamp_seconds": 0,
        "width": 1280,
        "height": 720,
        "url": f"/sessions/{session_id}/reference-frame",
    }

    assert (videos_dir / video["relative_path"]).read_bytes() == content
    assert _stored_files(videos_dir) == [video["relative_path"]]
    assert client.get(f"/sessions/{session_id}").json() == body


def test_registers_mpeg_video(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, mpeg_clip: Path
) -> None:
    response = _register(client, mpeg_clip.read_bytes(), camera["id"], filename="toma.mpg")

    assert response.status_code == 201
    video = response.json()["video"]
    assert video["relative_path"].endswith(".mpg")
    assert video["frame_count"] == CLIP_FRAMES
    assert video["duration_seconds"] == pytest.approx(video["frame_count"] / video["fps"])
    # The MPEG header is not trusted: no declared count and no warning.
    assert video["declared_frame_count"] is None
    assert video["appears_incomplete"] is False
    assert _stored_files(videos_dir) == [video["relative_path"]]
    session_id = response.json()["id"]
    assert client.get(f"/sessions/{session_id}").json()["video"] == video


@pytest.mark.parametrize("filename", ["toma.mpg", "toma.mpeg"])
def test_mpeg_extension_never_stores_the_declared_frame_count(
    client: TestClient, camera: dict[str, Any], clips: dict[str, Path], filename: str
) -> None:
    # An AVI renamed to .mpg still decodes; its declared count must be dropped anyway.
    response = _register(client, clips["half"].read_bytes(), camera["id"], filename=filename)

    assert response.status_code == 201
    video = response.json()["video"]
    assert video["declared_frame_count"] is None
    assert video["appears_incomplete"] is False


def test_incomplete_video_is_accepted_with_a_warning(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, clips: dict[str, Path]
) -> None:
    content = clips["half"].read_bytes()

    response = _register(client, content, camera["id"], filename="mitad.avi")

    assert response.status_code == 201
    body = response.json()
    video = body["video"]
    assert video["declared_frame_count"] == CLIP_FRAMES
    assert 0 < video["frame_count"] < CLIP_FRAMES
    assert video["appears_incomplete"] is True
    assert video["duration_seconds"] == pytest.approx(video["frame_count"] / video["fps"])
    assert _stored_files(videos_dir) == [video["relative_path"]]
    assert client.get(f"/sessions/{body['id']}").json() == body


def test_database_rows_do_not_contain_the_video(
    client: TestClient, camera: dict[str, Any], clips: dict[str, Path]
) -> None:
    content = clips["mp4"].read_bytes()
    session_id = _register(client, content, camera["id"], filename="toma.mp4").json()["id"]

    with client.app.state.session_factory() as database_session:
        video_row_size = database_session.scalar(
            text("SELECT pg_column_size(v.*) FROM video_sources v WHERE session_id = :id"),
            {"id": session_id},
        )
        frame_row_size = database_session.scalar(
            text("SELECT pg_column_size(r.*) FROM reference_frames r WHERE session_id = :id"),
            {"id": session_id},
        )
        rows = [
            database_session.execute(
                text(f"SELECT * FROM {table} WHERE session_id = :id"), {"id": session_id}
            )
            .mappings()
            .one()
            for table in ("video_sources", "reference_frames")
        ]

    # FR-007: the base keeps metadata and one JPEG, never the video itself.
    assert video_row_size < 4096
    assert frame_row_size < len(content) / 5
    for row in rows:
        for value in row.values():
            if isinstance(value, bytes | bytearray | memoryview):
                assert bytes(value) != content
                assert len(value) < len(content) / 5


def test_rejects_unknown_camera(
    client: TestClient,
    videos_dir: Path,
    clips: dict[str, Path],
    tmp_path: Path,
    database_url: str,
) -> None:
    response = _register(client, clips["avi"].read_bytes(), "00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"
    _assert_safe_error(response, tmp_path, database_url)
    _assert_nothing_created(client, videos_dir)


def test_rejects_extension_before_reading_body_or_checking_storage(
    make_client: ClientFactory, videos_dir: Path, tmp_path: Path, database_url: str
) -> None:
    client = make_client(videos=None)
    camera_id = client.post("/cameras", json={"name": "Cam"}).json()["id"]

    # Empty body and no videos folder: only the extension check can answer first.
    response = _register(client, b"", camera_id, filename="toma.webm")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_format"
    _assert_safe_error(response, tmp_path, database_url)
    _assert_nothing_created(client, videos_dir)


@pytest.mark.parametrize(
    ("clip", "filename", "code"),
    [
        (None, "toma.mp4", "file_empty"),
        ("text", "notas.mp4", "unsupported_format"),
        ("truncated", "truncado.avi", "no_decodable_frames"),
        ("avi", "toma.txt", "unsupported_format"),
    ],
    ids=["vacio", "texto-renombrado", "truncado", "extension-invalida"],
)
def test_rejected_video_leaves_no_session_row_or_file(
    client: TestClient,
    camera: dict[str, Any],
    videos_dir: Path,
    clips: dict[str, Path],
    tmp_path: Path,
    database_url: str,
    clip: str | None,
    filename: str,
    code: str,
) -> None:
    content = b"" if clip is None else clips[clip].read_bytes()

    response = _register(client, content, camera["id"], filename=filename)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code
    _assert_safe_error(response, tmp_path, database_url)
    _assert_nothing_created(client, videos_dir)


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        ({"videos": None}, "videos_dir_not_configured"),
        ("missing-dir", "videos_dir_not_writable"),
        ({"machine_id": None}, "machine_id_not_configured"),
        ({"machine_id": "Mi Equipo"}, "machine_id_not_configured"),
    ],
    ids=["sin-carpeta", "carpeta-inexistente", "sin-machine-id", "machine-id-invalido"],
)
def test_reports_unavailable_storage_with_503(
    make_client: ClientFactory,
    videos_dir: Path,
    clips: dict[str, Path],
    tmp_path: Path,
    database_url: str,
    settings: dict[str, Any] | str,
    code: str,
) -> None:
    if settings == "missing-dir":
        settings = {"videos": tmp_path / "no-existe"}
    client = make_client(**settings)
    camera_id = client.post("/cameras", json={"name": "Cam"}).json()["id"]

    response = _register(client, clips["avi"].read_bytes(), camera_id)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == code
    _assert_safe_error(response, tmp_path, database_url)
    _assert_nothing_created(client, videos_dir)
    assert not (tmp_path / "no-existe").exists()


def test_same_video_twice_is_accepted_and_reported_as_duplicate(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, clips: dict[str, Path]
) -> None:
    content = clips["avi"].read_bytes()
    first = _register(client, content, camera["id"]).json()

    second = _register(client, content, camera["id"], name="Otra vez")

    assert second.status_code == 201
    second_body = second.json()
    assert second_body["duplicate_session_ids"] == [first["id"]]
    assert client.get(f"/sessions/{first['id']}").json()["duplicate_session_ids"] == [
        second_body["id"]
    ]
    assert _stored_files(videos_dir) == sorted(
        [first["video"]["relative_path"], second_body["video"]["relative_path"]]
    )


def test_lists_sessions_as_summaries_without_availability(
    client: TestClient, camera: dict[str, Any], clips: dict[str, Path]
) -> None:
    synthetic = client.post("/sessions", json={"name": "Sintética", "camera_id": "camera-01"})
    video = _register(client, clips["avi"].read_bytes(), camera["id"]).json()

    response = client.get("/sessions")

    assert response.status_code == 200
    sessions = response.json()
    assert [item["id"] for item in sessions] == [video["id"], synthetic.json()["id"]]
    for item in sessions:
        assert SUMMARY_FIELDS <= set(item)
        assert "video" not in item
        assert "availability" not in response.text
    assert sessions[0]["camera"] == camera
    assert sessions[0]["source_kind"] == "video_file"

    filtered = client.get("/sessions", params={"registered_camera_id": camera["id"]}).json()
    assert [item["id"] for item in filtered] == [video["id"]]


def test_availability_follows_the_local_file_and_keeps_metadata(
    make_client: ClientFactory,
    client: TestClient,
    camera: dict[str, Any],
    videos_dir: Path,
    clips: dict[str, Path],
    tmp_path: Path,
) -> None:
    registered = _register(client, clips["avi"].read_bytes(), camera["id"]).json()
    session_id = registered["id"]
    stored = videos_dir / registered["video"]["relative_path"]
    expected = _without_availability(registered)

    def availability(api: TestClient = client) -> str:
        detail = api.get(f"/sessions/{session_id}").json()
        assert _without_availability(detail) == expected
        return detail["video"]["availability"]

    assert availability() == "available"

    moved = tmp_path / "movido.avi"
    shutil.move(stored, moved)
    assert availability() == "missing"

    shutil.copyfile(clips["mp4"], stored)
    assert availability() == "mismatch"

    assert availability(make_client(videos=None)) == "not_configured"


def test_reference_frame_is_served_from_the_database(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, clips: dict[str, Path]
) -> None:
    registered = _register(client, clips["mp4"].read_bytes(), camera["id"], "toma.mp4").json()
    (videos_dir / registered["video"]["relative_path"]).unlink()

    response = client.get(registered["reference_frame"]["url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == REFERENCE_FRAME_CACHE
    assert response.content[:2] == b"\xff\xd8"
    frame = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    assert frame.shape[:2] == (720, 1280)


def test_reference_frame_is_not_found_for_synthetic_or_unknown_sessions(
    client: TestClient,
) -> None:
    synthetic = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()

    for session_id in (synthetic["id"], "00000000-0000-0000-0000-000000000000"):
        response = client.get(f"/sessions/{session_id}/reference-frame")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_found"


def test_relink_with_the_same_file_restores_availability(
    client: TestClient, camera: dict[str, Any], videos_dir: Path, clips: dict[str, Path]
) -> None:
    content = clips["avi"].read_bytes()
    registered = _register(client, content, camera["id"]).json()
    stored = videos_dir / registered["video"]["relative_path"]
    stored.unlink()

    response = _relink(client, registered["id"], content)

    assert response.status_code == 200
    body = response.json()
    assert body["video"]["availability"] == "available"
    assert _without_availability(body) == _without_availability(registered)
    assert stored.read_bytes() == content
    assert _stored_files(videos_dir) == [registered["video"]["relative_path"]]


def test_relink_with_another_file_is_rejected_without_touching_the_video(
    client: TestClient,
    camera: dict[str, Any],
    videos_dir: Path,
    clips: dict[str, Path],
    tmp_path: Path,
    database_url: str,
) -> None:
    content = clips["avi"].read_bytes()
    registered = _register(client, content, camera["id"]).json()
    stored = videos_dir / registered["video"]["relative_path"]

    response = _relink(client, registered["id"], clips["mp4"].read_bytes())

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "hash_mismatch"
    _assert_safe_error(response, tmp_path, database_url)
    assert stored.read_bytes() == content
    assert _stored_files(videos_dir) == [registered["video"]["relative_path"]]
    assert client.get(f"/sessions/{registered['id']}").json() == registered


def test_relink_rejects_synthetic_and_unknown_sessions(
    client: TestClient, clips: dict[str, Path], videos_dir: Path
) -> None:
    synthetic = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"}).json()
    content = clips["avi"].read_bytes()

    not_video = _relink(client, synthetic["id"], content)
    unknown = _relink(client, "00000000-0000-0000-0000-000000000000", content)

    assert not_video.status_code == 409
    assert not_video.json()["detail"]["code"] == "not_video_session"
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "not_found"
    assert _stored_files(videos_dir) == []


def test_synthetic_session_detail_includes_camera_without_video(client: TestClient) -> None:
    created = client.post("/sessions", json={"name": "Local", "camera_id": "camera-01"})
    assert created.status_code == 201

    detail = client.get(f"/sessions/{created.json()['id']}").json()

    assert detail["source_kind"] == "synthetic"
    assert detail["camera_id"] == "camera-01"
    assert detail["camera"]["name"] == "camera-01"
    assert detail["video"] is None
    assert detail["reference_frame"] is None
    assert detail["duplicate_session_ids"] == []
