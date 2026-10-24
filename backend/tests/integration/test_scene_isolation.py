"""Scene configuration never crosses cameras (specs/004, T027, SC-008, FR-029).

Scenario: cameras X and Y, two video sessions per camera, and shops with the same
name ("Local A") on both cameras, so a join by name instead of by camera would show.

- Part (a) goes through the API: no listing or detail of scene versions returns
  shops, zones or lines of another camera, and saving a version refuses a reference
  session or a `shop_id` of the other camera.
- Part (b) inserts rows directly: the composite foreign keys of migration 0002 reject
  every row that would tie a scene version, a version shop or a job to another camera.

Runs only against `destructive_database_url()`.
"""

from __future__ import annotations

import copy
import logging.config
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from httpx import Response
from psycopg.errors import ForeignKeyViolation
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from flowsight.api.main import create_app
from flowsight.video.fixtures import write_clip

BACKEND_DIR = Path(__file__).resolve().parents[2]
MACHINE_ID = "equipo-test"
FRAME_SIZE = (1280, 720)
SHARED_NAME = "Local A"

# Valid geometry on a 1280x720 frame; each camera draws its "Local A" differently,
# so a detail that mixed cameras would return the other camera's zones or line.
GEOMETRY = {
    "X": {
        "zones": {
            "front": [[0.1, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]],
            "interior": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.45], [0.1, 0.45]],
        },
        "entry_line": {"start": [0.05, 0.6], "end": [0.35, 0.6], "entry_direction": "a_to_b"},
    },
    "Y": {
        "zones": {"front": [[0.6, 0.5], [0.8, 0.5], [0.8, 0.7], [0.6, 0.7]]},
        "entry_line": {"start": [0.55, 0.6], "end": [0.85, 0.6], "entry_direction": "b_to_a"},
    },
}
SECOND_SHOP = {
    "zones": {"front": [[0.6, 0.1], [0.8, 0.1], [0.8, 0.3], [0.6, 0.3]]},
    "entry_line": {"start": [0.55, 0.2], "end": [0.85, 0.2], "entry_direction": "a_to_b"},
}

ClientFactory = Callable[..., Any]


# --- Part (a): API ------------------------------------------------------------------
# Fixtures copied from tests/contract/test_scene_api.py (T025).


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_clip(tmp_path_factory.mktemp("isolation-clips"), codec="mp4v", size=FRAME_SIZE)


@pytest.fixture()
def database_url() -> str:
    return prepare_empty_schema()


@pytest.fixture()
def videos_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "videos"
    directory.mkdir()
    return directory


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch, database_url: str, videos_dir: Path
) -> Iterator[TestClient]:
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FLOWSIGHT_API_PORT", "8000")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-isolation")
    monkeypatch.setenv("FLOWSIGHT_PREVIEW_MAX_FPS", "5")
    monkeypatch.setenv("FLOWSIGHT_VIDEOS_DIR", str(videos_dir))
    monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", MACHINE_ID)
    with _running_client() as test_client:
        yield test_client


@contextmanager
def _running_client() -> Iterator[TestClient]:
    application = create_app()
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.state.engine.dispose()


@dataclass(frozen=True)
class ApiCamera:
    id: str
    sessions: tuple[dict[str, Any], dict[str, Any]]


@pytest.fixture()
def cameras(client: TestClient, clip: Path) -> dict[str, ApiCamera]:
    """Cameras X and Y, each with two video sessions registered through the API."""

    content = clip.read_bytes()
    result: dict[str, ApiCamera] = {}
    for label, name in (("X", "Entrada norte"), ("Y", "Entrada sur")):
        response = client.post("/cameras", json={"name": name})
        assert response.status_code == 201, response.text
        camera_id = response.json()["id"]
        sessions = tuple(_register_video(client, content, camera_id, n) for n in (1, 2))
        result[label] = ApiCamera(camera_id, sessions)
    return result


def _register_video(
    client: TestClient, content: bytes, camera_id: str, number: int
) -> dict[str, Any]:
    response = client.post(
        "/video-sessions",
        params={
            "name": f"Sesión {number}",
            "registered_camera_id": camera_id,
            "filename": f"video-{number}.mp4",
        },
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["camera"]["id"] == camera_id
    assert (body["reference_frame"]["width"], body["reference_frame"]["height"]) == FRAME_SIZE
    return body


def _shop(name: str, geometry: dict[str, Any], shop_id: str | None = None) -> dict[str, Any]:
    return {"shop_id": shop_id, "name": name, **copy.deepcopy(geometry)}


def _post(
    client: TestClient, camera_id: str, session: dict[str, Any], shops: list[dict[str, Any]]
) -> Response:
    return client.post(
        f"/cameras/{camera_id}/scene-versions",
        json={"reference_session_id": session["id"], "shops": shops},
    )


def _create(
    client: TestClient, camera_id: str, session: dict[str, Any], shops: list[dict[str, Any]]
) -> dict[str, Any]:
    response = _post(client, camera_id, session, shops)
    assert response.status_code == 201, response.text
    return response.json()


def _get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def _versions_per_camera(
    client: TestClient, cameras: dict[str, ApiCamera]
) -> dict[str, list[dict[str, Any]]]:
    """One version per session: each camera ends with v1 and v2, both with "Local A".

    X's v2 keeps its "Local A" `shop_id` and adds a second shop; Y's v2 keeps its own.
    """

    versions: dict[str, list[dict[str, Any]]] = {}
    for label, camera in cameras.items():
        first_session, second_session = camera.sessions
        v1 = _create(client, camera.id, first_session, [_shop(SHARED_NAME, GEOMETRY[label])])
        shop_id = v1["shops"][0]["shop_id"]
        shops = [_shop(SHARED_NAME, GEOMETRY[label], shop_id)]
        if label == "X":
            shops.append(_shop("Local B", SECOND_SHOP))
        v2 = _create(client, camera.id, second_session, shops)
        assert v2["shops"][0]["shop_id"] == shop_id
        versions[label] = [v1, v2]
    return versions


def _shop_ids(versions: list[dict[str, Any]]) -> set[str]:
    return {shop["shop_id"] for version in versions for shop in version["shops"]}


def _assert_rejected(response: Response, rule: str, shop_index: int | None = None) -> None:
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_scene_configuration"
    assert rule in {error["rule"] for error in detail["errors"]}, detail["errors"]
    if shop_index is not None:
        assert any(
            error["rule"] == rule and error["shop_index"] == shop_index
            for error in detail["errors"]
        ), detail["errors"]


def test_listing_and_detail_only_return_rows_of_their_camera(
    client: TestClient, cameras: dict[str, ApiCamera]
) -> None:
    versions = _versions_per_camera(client, cameras)
    shop_ids = {label: _shop_ids(items) for label, items in versions.items()}
    # Same shop name on both cameras, but never the same shop.
    assert shop_ids["X"].isdisjoint(shop_ids["Y"])

    for label, camera in cameras.items():
        own_versions = {version["id"] for version in versions[label]}
        own_sessions = {session["id"] for session in camera.sessions}

        listing = _get(client, f"/cameras/{camera.id}/scene-versions")
        assert {item["id"] for item in listing} == own_versions
        assert [item["version_number"] for item in listing] == [2, 1]
        for item in listing:
            assert item["camera_id"] == camera.id
            assert item["reference_session_id"] in own_sessions

        for saved in versions[label]:
            detail = _get(client, f"/scene-versions/{saved['id']}")
            assert detail["camera_id"] == camera.id
            assert detail["reference_session_id"] in own_sessions
            assert {shop["shop_id"] for shop in detail["shops"]} <= shop_ids[label]
            assert detail["shop_count"] == len(saved["shops"])
            by_name = {shop["name"]: shop for shop in detail["shops"]}
            local_a = by_name[SHARED_NAME]
            assert {role: polygon for role, polygon in local_a["zones"].items() if polygon} == (
                GEOMETRY[label]["zones"]
            )
            assert local_a["entry_line"] == GEOMETRY[label]["entry_line"]


def test_reference_session_of_the_other_camera_is_rejected_for_every_session(
    client: TestClient, cameras: dict[str, ApiCamera]
) -> None:
    for label, other in (("X", "Y"), ("Y", "X")):
        camera = cameras[label]
        for foreign_session in cameras[other].sessions:
            response = _post(
                client, camera.id, foreign_session, [_shop(SHARED_NAME, GEOMETRY[label])]
            )
            _assert_rejected(response, "reference_session_other_camera")

    for camera in cameras.values():
        assert _get(client, f"/cameras/{camera.id}/scene-versions") == []


def test_shop_id_of_the_other_camera_is_rejected_even_with_the_same_name(
    client: TestClient, cameras: dict[str, ApiCamera]
) -> None:
    versions = _versions_per_camera(client, cameras)
    foreign_local_a = versions["Y"][0]["shops"][0]["shop_id"]
    before = {
        label: _get(client, f"/cameras/{camera.id}/scene-versions")
        for label, camera in cameras.items()
    }

    # From either session of X, reusing Y's "Local A" is refused.
    for session in cameras["X"].sessions:
        response = _post(
            client,
            cameras["X"].id,
            session,
            [_shop(SHARED_NAME, GEOMETRY["X"], foreign_local_a)],
        )
        _assert_rejected(response, "shop_other_camera", shop_index=0)

    for label, camera in cameras.items():
        assert _get(client, f"/cameras/{camera.id}/scene-versions") == before[label]

    # X's own "Local A" is still accepted, and Y's versions are untouched.
    own_local_a = versions["X"][0]["shops"][0]["shop_id"]
    v3 = _create(
        client,
        cameras["X"].id,
        cameras["X"].sessions[0],
        [_shop(SHARED_NAME, GEOMETRY["X"], own_local_a)],
    )
    assert v3["version_number"] == 3
    assert v3["shops"][0]["shop_id"] == own_local_a
    assert _get(client, f"/cameras/{cameras['Y'].id}/scene-versions") == before["Y"]


# --- Part (b): composite foreign keys -----------------------------------------------


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
        database_url = prepare_empty_schema()
        engine = create_engine(database_url)
        try:
            yield engine
        finally:
            engine.dispose()


@dataclass(frozen=True)
class SqlCamera:
    id: UUID
    name: str
    sessions: tuple[UUID, UUID]
    shop_id: UUID
    version_id: UUID


@pytest.fixture()
def sql_cameras(engine: Engine) -> dict[str, SqlCamera]:
    """Cameras X and Y with two video sessions each, a "Local A" shop and a v1."""

    with engine.begin() as connection:
        return {label: _insert_camera(connection, label) for label in ("X", "Y")}


def _insert_camera(connection: Connection, label: str) -> SqlCamera:
    camera_id, shop_id, version_id = uuid4(), uuid4(), uuid4()
    name = f"Cámara {label} {camera_id.hex[:8]}"
    connection.execute(
        text("INSERT INTO cameras (id, name, name_key) VALUES (:id, :name, :name_key)"),
        {"id": camera_id, "name": name, "name_key": name.casefold()},
    )
    sessions = (uuid4(), uuid4())
    for number, session_id in enumerate(sessions, start=1):
        connection.execute(
            text(
                "INSERT INTO sessions (id, name, camera_id, registered_camera_id, source_kind) "
                "VALUES (:id, :name, :camera_name, :camera, 'video_file')"
            ),
            {"id": session_id, "name": f"Video {number}", "camera_name": name, "camera": camera_id},
        )
        connection.execute(
            text(
                "INSERT INTO reference_frames (session_id, frame_index, video_timestamp_seconds, "
                "width, height, media_type, image) "
                "VALUES (:session, 0, 0, 1280, 720, 'image/jpeg', :image)"
            ),
            {"session": session_id, "image": b"\xff\xd8\xff\xd9"},
        )
    connection.execute(
        text("INSERT INTO shops (id, camera_id) VALUES (:id, :camera)"),
        {"id": shop_id, "camera": camera_id},
    )
    _insert_version(connection, version_id, camera_id, 1, sessions[0])
    _insert_version_shop(connection, version_id, camera_id, shop_id)
    return SqlCamera(camera_id, name, sessions, shop_id, version_id)


def _insert_version(
    connection: Connection, version_id: UUID, camera_id: UUID, number: int, session_id: UUID
) -> None:
    connection.execute(
        text(
            "INSERT INTO scene_versions (id, camera_id, version_number, reference_session_id, "
            "frame_width, frame_height, created_by_machine_id) "
            "VALUES (:id, :camera, :number, :session, 1280, 720, 'maquina-test')"
        ),
        {"id": version_id, "camera": camera_id, "number": number, "session": session_id},
    )


def _insert_version_shop(
    connection: Connection,
    version_id: UUID,
    camera_id: UUID,
    shop_id: UUID,
    name: str = SHARED_NAME,
    position: int = 0,
) -> None:
    connection.execute(
        text(
            "INSERT INTO scene_version_shops "
            "(id, scene_version_id, shop_id, camera_id, position, name, name_key) "
            "VALUES (:id, :version, :shop, :camera, :position, :name, :name_key)"
        ),
        {
            "id": uuid4(),
            "version": version_id,
            "shop": shop_id,
            "camera": camera_id,
            "position": position,
            "name": name,
            "name_key": name.casefold(),
        },
    )


def _insert_job(
    connection: Connection, session_id: UUID, camera_id: UUID, version_id: UUID
) -> None:
    connection.execute(
        text(
            "INSERT INTO processing_jobs "
            "(id, session_id, registered_camera_id, scene_version_id, kind, status) "
            "VALUES (:id, :session, :camera, :version, 'video_analysis', 'pending')"
        ),
        {"id": uuid4(), "session": session_id, "camera": camera_id, "version": version_id},
    )


Insert = Callable[[Connection, dict[str, SqlCamera]], None]

# Each case writes rows that tie camera X to something of camera Y.
CROSS_CAMERA_INSERTS: list[tuple[str, Insert, str]] = [
    (
        "shop-de-otra-camara",
        # X's version, X's camera, but Y's "Local A".
        lambda c, cams: _insert_version_shop(
            c, cams["X"].version_id, cams["X"].id, cams["Y"].shop_id, "Local B", 1
        ),
        "fk_scene_version_shops_shop",
    ),
    (
        "shop-con-camara-del-shop",
        # Y's "Local A" labelled with Y's camera, attached to X's version.
        lambda c, cams: _insert_version_shop(
            c, cams["X"].version_id, cams["Y"].id, cams["Y"].shop_id, "Local B", 1
        ),
        "fk_scene_version_shops_scene_version",
    ),
    (
        "referencia-de-otra-camara",
        lambda c, cams: _insert_version(c, uuid4(), cams["X"].id, 2, cams["Y"].sessions[1]),
        "fk_scene_versions_reference_session",
    ),
    (
        "trabajo-con-version-de-otra-camara",
        # X's session and camera, Y's scene version.
        lambda c, cams: _insert_job(c, cams["X"].sessions[1], cams["X"].id, cams["Y"].version_id),
        "fk_processing_jobs_scene_version",
    ),
    (
        "trabajo-con-camara-de-la-version",
        # Y's scene version and camera, X's session.
        lambda c, cams: _insert_job(c, cams["X"].sessions[1], cams["Y"].id, cams["Y"].version_id),
        "fk_processing_jobs_session_camera",
    ),
]

# The same inserts within camera X succeed: the rejections above come from the camera.
SAME_CAMERA_INSERTS: list[tuple[str, Insert]] = [
    (
        "shop-propio",
        lambda c, cams: _insert_version_shop(
            c, cams["X"].version_id, cams["X"].id, _new_shop(c, cams["X"].id), "Local B", 1
        ),
    ),
    (
        "referencia-propia",
        lambda c, cams: _insert_version(c, uuid4(), cams["X"].id, 2, cams["X"].sessions[1]),
    ),
    (
        "trabajo-propio",
        lambda c, cams: _insert_job(c, cams["X"].sessions[1], cams["X"].id, cams["X"].version_id),
    ),
]


def _new_shop(connection: Connection, camera_id: UUID) -> UUID:
    shop_id = uuid4()
    connection.execute(
        text("INSERT INTO shops (id, camera_id) VALUES (:id, :camera)"),
        {"id": shop_id, "camera": camera_id},
    )
    return shop_id


def _counts(engine: Engine) -> dict[str, int]:
    tables = ("scene_versions", "scene_version_shops", "processing_jobs")
    with engine.connect() as connection:
        return {table: connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in tables}


@pytest.mark.parametrize(
    ("insert", "constraint"),
    [
        pytest.param(insert, constraint, id=case)
        for case, insert, constraint in CROSS_CAMERA_INSERTS
    ],
)
def test_cross_camera_insert_violates_composite_foreign_key(
    engine: Engine, sql_cameras: dict[str, SqlCamera], insert: Insert, constraint: str
) -> None:
    before = _counts(engine)

    with pytest.raises(IntegrityError) as raised:
        with engine.begin() as connection:
            insert(connection, sql_cameras)

    assert isinstance(raised.value.orig, ForeignKeyViolation)
    assert raised.value.orig.diag.constraint_name == constraint
    assert _counts(engine) == before


@pytest.mark.parametrize(
    "insert", [pytest.param(insert, id=case) for case, insert in SAME_CAMERA_INSERTS]
)
def test_same_camera_insert_is_accepted(
    engine: Engine, sql_cameras: dict[str, SqlCamera], insert: Insert
) -> None:
    with engine.begin() as connection:
        insert(connection, sql_cameras)
