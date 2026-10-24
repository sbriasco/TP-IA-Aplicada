"""Contract tests for the scene version API (specs/004, T025).

Covers `POST/GET /cameras/{camera_id}/scene-versions` and
`GET /scene-versions/{scene_version_id}` as described in contracts/openapi.yaml,
SC-005 (invalid configurations rejected with element and rule) and SC-006
(saved versions never change).
"""

from __future__ import annotations

import copy
import json
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text

from flowsight.api.main import create_app
from flowsight.video.fixtures import write_clip

BACKEND_DIR = Path(__file__).resolve().parents[2]
MACHINE_ID = "equipo-test"
FRAME_SIZE = (1280, 720)
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"
SCENE_TABLES = (
    "scene_versions",
    "scene_version_shops",
    "scene_zones",
    "scene_entry_lines",
    "shops",
)
SUMMARY_FIELDS = {
    "id",
    "camera_id",
    "version_number",
    "reference_session_id",
    "frame_width",
    "frame_height",
    "display_name",
    "created_by_machine_id",
    "created_at",
    "shop_count",
}

ClientFactory = Callable[..., Any]

# Valid geometry on a 1280x720 reference frame: the line crosses the front zone.
FRONT = [[0.1, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]]
INTERIOR = [[0.1, 0.2], [0.3, 0.2], [0.3, 0.45], [0.1, 0.45]]
LINE = {"start": [0.05, 0.6], "end": [0.35, 0.6], "entry_direction": "a_to_b"}


# --- Fixtures copied from test_video_sessions_api.py (US1) ------------------------


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_clip(tmp_path_factory.mktemp("scene-clips"), codec="mp4v", size=FRAME_SIZE)


@pytest.fixture()
def database_url() -> str:
    return prepare_empty_schema()


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


# --- Scene fixtures ----------------------------------------------------------------


def _create_camera(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post("/cameras", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _register_video(client: TestClient, content: bytes, camera_id: str) -> dict[str, Any]:
    response = client.post(
        "/video-sessions",
        params={"name": "Sesión de video", "registered_camera_id": camera_id, "filename": "a.mp4"},
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["reference_frame"]["width"], body["reference_frame"]["height"]) == FRAME_SIZE
    return body


@pytest.fixture()
def camera(client: TestClient) -> dict[str, Any]:
    return _create_camera(client, "Entrada norte")


@pytest.fixture()
def video_session(client: TestClient, camera: dict[str, Any], clip: Path) -> dict[str, Any]:
    return _register_video(client, clip.read_bytes(), camera["id"])


@pytest.fixture()
def other_camera(client: TestClient) -> dict[str, Any]:
    return _create_camera(client, "Entrada sur")


@pytest.fixture()
def other_video_session(
    client: TestClient, other_camera: dict[str, Any], clip: Path
) -> dict[str, Any]:
    return _register_video(client, clip.read_bytes(), other_camera["id"])


# --- Helpers -----------------------------------------------------------------------


def _shop(
    name: str = "Local A",
    *,
    shop_id: str | None = None,
    front: list[list[float]] | None = FRONT,
    interior: list[list[float]] | None = INTERIOR,
    showcase: list[list[float]] | None = None,
    entry_line: dict[str, Any] | None = LINE,
) -> dict[str, Any]:
    zones = {
        role: copy.deepcopy(polygon)
        for role, polygon in (("front", front), ("interior", interior), ("showcase", showcase))
        if polygon is not None
    }
    return {
        "shop_id": shop_id,
        "name": name,
        "zones": zones,
        "entry_line": copy.deepcopy(entry_line),
    }


def _payload(
    session: dict[str, Any], shops: list[dict[str, Any]], base_version_id: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"reference_session_id": session["id"], "shops": shops}
    if base_version_id is not None:
        body["base_version_id"] = base_version_id
    return body


def _post(client: TestClient, camera_id: str, payload: dict[str, Any]) -> Response:
    return client.post(f"/cameras/{camera_id}/scene-versions", json=payload)


def _create(client: TestClient, camera_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = _post(client, camera_id, payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_removed_configuration_keeps_content_and_numbering(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    first = _create(client, camera["id"], _payload(video_session, [_shop()]))
    second = _create(client, camera["id"], _payload(video_session, [_shop()]))
    before = client.get(f"/scene-versions/{second['id']}").json()
    assert client.delete(f"/scene-versions/{second['id']}").status_code == 204
    assert client.delete(f"/scene-versions/{second['id']}").status_code == 204
    assert client.get(f"/scene-versions/{second['id']}").json() == before
    remaining = client.get(f"/cameras/{camera['id']}/scene-versions").json()
    assert [item["id"] for item in remaining] == [first["id"]]
    rejected = client.post(
        f"/sessions/{video_session['id']}/jobs",
        json={"kind": "video_analysis", "scene_version_id": second["id"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "scene_version_removed"
    third = _create(client, camera["id"], _payload(video_session, [_shop()], first["id"]))
    assert third["version_number"] == 3
    assert not any(warning["rule"] == "newer_version_exists" for warning in third["warnings"])


def test_active_job_blocks_configuration_removal_and_cancelled_job_keeps_reference(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    version = _create(client, camera["id"], _payload(video_session, [_shop()]))
    job = client.post(
        f"/sessions/{video_session['id']}/jobs",
        json={"kind": "video_analysis", "scene_version_id": version["id"]},
    )
    assert job.status_code == 201, job.text
    blocked = client.delete(f"/scene-versions/{version['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "scene_version_has_active_jobs"
    assert client.post(f"/jobs/{job.json()['id']}/cancel").status_code == 200
    assert client.delete(f"/scene-versions/{version['id']}").status_code == 204
    assert client.get(f"/jobs/{job.json()['id']}").json()["scene_version_id"] == version["id"]
    assert client.get(f"/scene-versions/{version['id']}").status_code == 200
    rejected = client.post(
        f"/sessions/{video_session['id']}/jobs",
        json={"kind": "video_analysis", "scene_version_id": version["id"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "scene_not_configured"


def test_configuration_removal_rejects_unknown_id(client: TestClient) -> None:
    assert client.delete(f"/scene-versions/{UNKNOWN_ID}").status_code == 404


def _canonical(body: Any) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _without_warnings(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key != "warnings"}


def _issue(rule: str, element: str, shop_index: int | None, shop_name: str | None) -> dict:
    return {"rule": rule, "element": element, "shop_index": shop_index, "shop_name": shop_name}


def _issue_key(issue: dict[str, Any]) -> tuple:
    index = -1 if issue["shop_index"] is None else issue["shop_index"]
    return (index, issue["element"], issue["rule"], issue["shop_name"] or "")


def _assert_rejected(response: Response, expected: list[dict[str, Any]]) -> None:
    """422 `invalid_scene_configuration` listing exactly the expected problems."""

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_scene_configuration"
    assert isinstance(detail["message"], str) and detail["message"]
    errors = detail["errors"]
    for error in errors:
        assert isinstance(error["message"], str) and error["message"]
    got = [
        {key: error[key] for key in ("rule", "element", "shop_index", "shop_name")}
        for error in errors
    ]
    assert sorted(got, key=_issue_key) == sorted(expected, key=_issue_key)


def _count(client: TestClient, table: str) -> int:
    with client.app.state.session_factory() as database_session:
        return database_session.scalar(text(f"SELECT count(*) FROM {table}"))


def _assert_nothing_saved(client: TestClient, camera_id: str) -> None:
    listing = client.get(f"/cameras/{camera_id}/scene-versions")
    assert listing.status_code == 200
    assert listing.json() == []
    for table in SCENE_TABLES:
        assert _count(client, table) == 0, table


def _coordinates(version: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for shop in version["shops"]:
        for polygon in shop["zones"].values():
            if polygon is not None:
                values.extend(value for point in polygon for value in point)
        line = shop["entry_line"]
        values.extend([*line["start"], *line["end"]])
    return values


# --- Creation ----------------------------------------------------------------------


def test_creates_first_version_with_frame_size_machine_and_generated_shop_id(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    front = [[0.12345678, 0.5], [0.3, 0.5000004], [0.3, 0.7], [0.1, 0.7]]
    shop = _shop("  Local A  ", front=front)

    response = _post(client, camera["id"], _payload(video_session, [shop]))

    assert response.status_code == 201, response.text
    body = response.json()
    uuid.UUID(body["id"])
    assert body["camera_id"] == camera["id"]
    assert body["version_number"] == 1
    assert body["reference_session_id"] == video_session["id"]
    assert (body["frame_width"], body["frame_height"]) == FRAME_SIZE
    assert body["created_by_machine_id"] == MACHINE_ID
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert body["shop_count"] == 1
    assert body["warnings"] == []

    [saved] = body["shops"]
    uuid.UUID(saved["shop_id"])
    assert saved["name"] == "Local A"
    assert saved["zones"]["front"] == [[0.123457, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]]
    assert saved["zones"]["interior"] == INTERIOR
    assert saved["zones"].get("showcase") is None
    assert saved["entry_line"] == LINE
    for value in _coordinates(body):
        assert 0 <= value <= 1
        assert round(value, 6) == value

    detail = client.get(f"/scene-versions/{body['id']}")
    assert detail.status_code == 200
    assert detail.json() == _without_warnings(body)


def test_non_blocking_warnings_are_returned_and_version_is_saved(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    far_line = {"start": [0.5, 0.1], "end": [0.6, 0.1], "entry_direction": "b_to_a"}
    shops = [_shop("Local A", entry_line=far_line), _shop("Local B", interior=None)]

    body = _create(client, camera["id"], _payload(video_session, shops))

    assert body["version_number"] == 1
    warnings = [
        {key: warning[key] for key in ("rule", "element", "shop_index", "shop_name")}
        for warning in body["warnings"]
    ]
    assert _issue("line_not_touching_zones", "entry_line", 0, "Local A") in warnings
    assert _issue("zones_overlap", "zone:front", 1, "Local B") in warnings
    for warning in body["warnings"]:
        assert warning["message"]
    assert [shop["name"] for shop in body["shops"]] == ["Local A", "Local B"]
    assert body["shops"][0]["entry_line"]["entry_direction"] == "b_to_a"


# --- SC-005: invalid configurations ------------------------------------------------


@pytest.mark.parametrize(
    ("shop", "expected"),
    [
        (
            _shop(front=[[0.1, 0.5], [0.3, 0.5]]),
            _issue("too_few_vertices", "zone:front", 0, "Local A"),
        ),
        (
            _shop(front=[[0.1, 0.5], [0.3, 0.5], [0.3, 0.5], [0.3, 0.7], [0.1, 0.7]]),
            _issue("vertices_too_close", "zone:front", 0, "Local A"),
        ),
        (
            # 0.0015 * 1280 = 1.92 px between consecutive vertices.
            _shop(front=[[0.1, 0.5], [0.3, 0.5], [0.3015, 0.5], [0.3, 0.7], [0.1, 0.7]]),
            _issue("vertices_too_close", "zone:front", 0, "Local A"),
        ),
        (
            _shop(front=[[0.1, 0.5], [0.4, 0.7], [0.4, 0.5], [0.1, 0.8]]),
            _issue("self_intersection", "zone:front", 0, "Local A"),
        ),
        (
            # 6.4 px x 7.2 px = 46 px².
            _shop(front=[[0.1, 0.5], [0.105, 0.5], [0.105, 0.51], [0.1, 0.51]]),
            _issue("area_too_small", "zone:front", 0, "Local A"),
        ),
        (
            _shop(
                entry_line={"start": [0.2, 0.6], "end": [0.205, 0.6], "entry_direction": "a_to_b"}
            ),
            _issue("line_too_short", "entry_line", 0, "Local A"),
        ),
        (
            _shop(front=[[0.1, 0.5], [1.2, 0.5], [0.3, 0.7], [-0.1, 0.7]]),
            _issue("out_of_range", "zone:front", 0, "Local A"),
        ),
        (
            _shop(entry_line={"start": [0.2, 0.6], "end": [0.2, 1.5], "entry_direction": "a_to_b"}),
            _issue("out_of_range", "entry_line", 0, "Local A"),
        ),
    ],
    ids=[
        "menos-de-3-vertices",
        "vertice-repetido",
        "vertices-a-2px",
        "autointerseccion",
        "area-chica",
        "linea-corta",
        "zona-fuera-de-rango",
        "linea-fuera-de-rango",
    ],
)
def test_rejects_each_invalid_configuration_of_sc005(
    client: TestClient,
    camera: dict[str, Any],
    video_session: dict[str, Any],
    shop: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    response = _post(client, camera["id"], _payload(video_session, [shop]))

    _assert_rejected(response, [expected])
    _assert_nothing_saved(client, camera["id"])


def test_rejects_version_without_shops(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    response = _post(client, camera["id"], _payload(video_session, []))

    _assert_rejected(response, [_issue("no_shops", "version", None, None)])
    _assert_nothing_saved(client, camera["id"])


def test_rejection_lists_every_error_and_saves_nothing(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    short_line = {"start": [0.2, 0.6], "end": [0.205, 0.6], "entry_direction": "a_to_b"}
    tiny_front = [[0.5, 0.5], [0.505, 0.5], [0.505, 0.51], [0.5, 0.51]]
    shops = [
        _shop("Local A", front=None, entry_line=short_line),
        _shop(" local a ", front=tiny_front, interior=None, entry_line=None),
    ]

    response = _post(client, camera["id"], _payload(video_session, shops))

    _assert_rejected(
        response,
        [
            _issue("missing_front_zone", "shop", 0, "Local A"),
            _issue("line_too_short", "entry_line", 0, "Local A"),
            _issue("duplicate_shop_name", "shop", 1, "local a"),
            _issue("missing_entry_line", "shop", 1, "local a"),
            _issue("area_too_small", "zone:front", 1, "local a"),
        ],
    )
    _assert_nothing_saved(client, camera["id"])


# --- Rules that need the database --------------------------------------------------


def test_rejects_reference_session_of_another_camera(
    client: TestClient,
    camera: dict[str, Any],
    video_session: dict[str, Any],
    other_video_session: dict[str, Any],
) -> None:
    response = _post(client, camera["id"], _payload(other_video_session, [_shop()]))

    _assert_rejected(response, [_issue("reference_session_other_camera", "version", None, None)])
    _assert_nothing_saved(client, camera["id"])


def test_rejects_synthetic_reference_session_of_the_same_camera(
    client: TestClient, camera: dict[str, Any]
) -> None:
    synthetic = client.post("/sessions", json={"name": "Sintética", "camera_id": camera["name"]})
    assert synthetic.status_code == 201
    assert synthetic.json()["camera"]["id"] == camera["id"]

    response = _post(client, camera["id"], _payload(synthetic.json(), [_shop()]))

    _assert_rejected(response, [_issue("reference_frame_missing", "version", None, None)])
    _assert_nothing_saved(client, camera["id"])


def test_rejects_shop_id_of_another_camera_or_unknown(
    client: TestClient,
    camera: dict[str, Any],
    video_session: dict[str, Any],
    other_camera: dict[str, Any],
    other_video_session: dict[str, Any],
) -> None:
    foreign = _create(client, other_camera["id"], _payload(other_video_session, [_shop("Ajeno")]))
    foreign_shop_id = foreign["shops"][0]["shop_id"]
    shops = [_shop("Local A", shop_id=foreign_shop_id), _shop("Local B", shop_id=str(uuid.uuid4()))]

    response = _post(client, camera["id"], _payload(video_session, shops))

    _assert_rejected(
        response,
        [
            _issue("shop_other_camera", "shop", 0, "Local A"),
            _issue("shop_other_camera", "shop", 1, "Local B"),
        ],
    )
    assert client.get(f"/cameras/{camera['id']}/scene-versions").json() == []
    assert _count(client, "scene_versions") == 1
    assert _count(client, "shops") == 1


# --- SC-006: versioning and immutability -------------------------------------------


def test_new_versions_keep_shop_identity_and_never_change_older_ones(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    v1 = _create(client, camera["id"], _payload(video_session, [_shop("Local A")]))
    shop_id = v1["shops"][0]["shop_id"]
    v1_before = client.get(f"/scene-versions/{v1['id']}")
    assert v1_before.status_code == 200
    v1_canonical = _canonical(v1_before.json())
    assert v1_canonical == _canonical(_without_warnings(v1))

    renamed = _shop("Local A renombrado", shop_id=shop_id)
    other_front = [[0.6, 0.5], [0.8, 0.5], [0.8, 0.7], [0.6, 0.7]]
    other_line = {"start": [0.55, 0.6], "end": [0.85, 0.6], "entry_direction": "a_to_b"}
    new_shop = _shop("Local B", front=other_front, interior=None, entry_line=other_line)
    v2 = _create(
        client, camera["id"], _payload(video_session, [renamed, new_shop], base_version_id=v1["id"])
    )

    assert v2["version_number"] == 2
    assert v2["shops"][0]["shop_id"] == shop_id
    assert v2["shops"][0]["name"] == "Local A renombrado"
    assert v2["shops"][1]["shop_id"] != shop_id
    new_shop_id = v2["shops"][1]["shop_id"]
    v1_after_v2 = client.get(f"/scene-versions/{v1['id']}")
    assert v1_after_v2.status_code == 200
    assert v1_after_v2.text.encode() == v1_before.text.encode()
    assert _canonical(v1_after_v2.json()) == v1_canonical
    v2_canonical = _canonical(client.get(f"/scene-versions/{v2['id']}").json())

    # v3 drops shop A: it stays in v1 and v2.
    kept = _shop(
        "Local B", shop_id=new_shop_id, front=other_front, interior=None, entry_line=other_line
    )
    v3 = _create(client, camera["id"], _payload(video_session, [kept], base_version_id=v2["id"]))

    assert v3["version_number"] == 3
    assert [shop["shop_id"] for shop in v3["shops"]] == [new_shop_id]
    assert _canonical(client.get(f"/scene-versions/{v1['id']}").json()) == v1_canonical
    assert _canonical(client.get(f"/scene-versions/{v2['id']}").json()) == v2_canonical
    assert shop_id in {
        shop["shop_id"] for shop in client.get(f"/scene-versions/{v1['id']}").json()["shops"]
    }
    assert shop_id in {
        shop["shop_id"] for shop in client.get(f"/scene-versions/{v2['id']}").json()["shops"]
    }


def test_warns_when_base_version_is_not_the_latest(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any]
) -> None:
    v1 = _create(client, camera["id"], _payload(video_session, [_shop()]))
    v2 = _create(client, camera["id"], _payload(video_session, [_shop()], base_version_id=v1["id"]))
    assert "newer_version_exists" not in {warning["rule"] for warning in v2["warnings"]}

    v3 = _create(client, camera["id"], _payload(video_session, [_shop()], base_version_id=v1["id"]))

    assert v3["version_number"] == 3
    newer = [warning for warning in v3["warnings"] if warning["rule"] == "newer_version_exists"]
    assert len(newer) == 1
    assert newer[0]["element"] == "version"
    assert newer[0]["shop_index"] is None
    assert newer[0]["message"]


def test_lists_versions_newest_first_with_shop_count(
    client: TestClient,
    camera: dict[str, Any],
    video_session: dict[str, Any],
    other_camera: dict[str, Any],
    other_video_session: dict[str, Any],
) -> None:
    assert client.get(f"/cameras/{camera['id']}/scene-versions").json() == []
    v1 = _create(client, camera["id"], _payload(video_session, [_shop()]))
    second = _shop(
        "Local B",
        front=[[0.6, 0.5], [0.8, 0.5], [0.8, 0.7], [0.6, 0.7]],
        interior=None,
        entry_line={"start": [0.55, 0.6], "end": [0.85, 0.6], "entry_direction": "b_to_a"},
    )
    v2 = _create(client, camera["id"], _payload(video_session, [_shop(), second]))
    _create(client, other_camera["id"], _payload(other_video_session, [_shop()]))

    response = client.get(f"/cameras/{camera['id']}/scene-versions")

    assert response.status_code == 200
    listing = response.json()
    assert [item["id"] for item in listing] == [v2["id"], v1["id"]]
    assert [item["version_number"] for item in listing] == [2, 1]
    assert [item["shop_count"] for item in listing] == [2, 1]
    for item in listing:
        assert SUMMARY_FIELDS <= set(item)
        assert item["camera_id"] == camera["id"]
        assert item["reference_session_id"] == video_session["id"]
        assert (item["frame_width"], item["frame_height"]) == FRAME_SIZE
        assert item["created_by_machine_id"] == MACHINE_ID


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_versions_cannot_be_modified(
    client: TestClient, camera: dict[str, Any], video_session: dict[str, Any], method: str
) -> None:
    payload = _payload(video_session, [_shop()])
    version = _create(client, camera["id"], payload)
    before = client.get(f"/scene-versions/{version['id']}").text

    response = client.request(method, f"/scene-versions/{version['id']}", json=payload)

    assert response.status_code == 405
    assert client.get(f"/scene-versions/{version['id']}").text == before


def test_concurrent_saves_get_distinct_version_numbers(
    make_client: ClientFactory, clip: Path
) -> None:
    first_client, second_client = make_client(), make_client()
    camera = _create_camera(first_client, "Concurrente")
    session = _register_video(first_client, clip.read_bytes(), camera["id"])
    barrier = threading.Barrier(2)
    responses: list[Response] = []
    lock = threading.Lock()

    def save(api: TestClient, name: str) -> None:
        barrier.wait()
        response = _post(api, camera["id"], _payload(session, [_shop(name)]))
        with lock:
            responses.append(response)

    threads = [
        threading.Thread(target=save, args=(first_client, "Local A")),
        threading.Thread(target=save, args=(second_client, "Local B")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert [response.status_code for response in responses] == [201, 201], [
        response.text for response in responses
    ]
    assert sorted(response.json()["version_number"] for response in responses) == [1, 2]
    listing = first_client.get(f"/cameras/{camera['id']}/scene-versions").json()
    assert [item["version_number"] for item in listing] == [2, 1]


# --- Not found ---------------------------------------------------------------------


def test_unknown_camera_or_version_is_not_found(
    client: TestClient, video_session: dict[str, Any]
) -> None:
    responses = [
        client.get(f"/cameras/{UNKNOWN_ID}/scene-versions"),
        _post(client, UNKNOWN_ID, _payload(video_session, [_shop()])),
        client.get(f"/scene-versions/{UNKNOWN_ID}"),
    ]

    for response in responses:
        assert response.status_code == 404, response.text
        detail = response.json()["detail"]
        assert isinstance(detail, dict), detail
        assert detail["code"] == "not_found"
        assert detail["message"]
    assert _count(client, "scene_versions") == 0
