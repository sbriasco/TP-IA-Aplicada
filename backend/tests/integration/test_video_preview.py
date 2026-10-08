"""Live preview for a video analysis keeps one pending frame and does not touch the job."""

from __future__ import annotations

import asyncio
import base64
import uuid
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient

from flowsight.api.main import create_app
from flowsight.preview.broker import PreviewBroker, PreviewUpdate
from flowsight.vision.detector import Detection
from flowsight.vision.overlay import MAX_JPEG_BYTES, render_overlay_jpeg

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _jpeg_update(job_id: uuid.UUID, frame_index: int, image: bytes) -> PreviewUpdate:
    return PreviewUpdate(
        session_id=uuid.uuid4(),
        job_id=job_id,
        frame_index=frame_index,
        video_timestamp_seconds=Decimal(frame_index) / Decimal(25),
        progress_percent=float(frame_index),
        image_base64=base64.b64encode(image).decode("ascii"),
        schema_version="2",
    )


def test_two_video_updates_leave_only_the_later_frame() -> None:
    image = render_overlay_jpeg(
        np.zeros((48, 64, 3), dtype=np.uint8),
        [Detection(track_id=3, bbox=(10, 8, 30, 40))],
        [((0.1, 0.1), (0.8, 0.1), (0.8, 0.8), (0.1, 0.8))],
        ((0.1, 0.5), (0.8, 0.5)),
    )

    async def scenario() -> dict[str, object]:
        broker = PreviewBroker()
        job_id = uuid.uuid4()
        client = broker.subscribe(job_id)
        broker.publish(_jpeg_update(job_id, 0, image))
        later = _jpeg_update(job_id, 10, image)
        broker.publish(later)
        return await client.receive()

    message = asyncio.run(scenario())
    assert message["schema_version"] == "2"
    assert message["frame_index"] == 10
    assert message["video_timestamp_seconds"] == 0.4
    raw = base64.b64decode(str(message["image_base64"]))
    assert raw[:2] == b"\xff\xd8"
    assert message["measures"] == []


def test_synthetic_preview_message_stays_on_schema_one() -> None:
    message = PreviewUpdate(
        session_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        frame_index=1,
        video_timestamp_seconds=Decimal("0.2"),
        progress_percent=10,
        image_base64="/9j/2Q==",
    ).as_message()

    assert message["schema_version"] == "1"
    assert "measures" not in message


def test_overlay_keeps_the_frame_size_and_limits_the_jpeg() -> None:
    frame = np.random.default_rng(0).integers(0, 256, size=(360, 640, 3), dtype=np.uint8)
    encoded = render_overlay_jpeg(frame, [], [], None)
    assert encoded[:2] == b"\xff\xd8"
    assert len(encoded) <= MAX_JPEG_BYTES
    import cv2

    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape[0] == 360
    assert decoded.shape[1] == 640


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_url = prepare_empty_schema()
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOWSIGHT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("FLOWSIGHT_API_PORT", "8000")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-preview")
    monkeypatch.setenv("FLOWSIGHT_PREVIEW_MAX_FPS", "5")
    with TestClient(create_app()) as test_client:
        yield test_client
    test_client.app.state.engine.dispose()


def test_disconnected_preview_client_does_not_change_the_job(client: TestClient) -> None:
    session = client.post("/sessions", json={"name": "Vista", "camera_id": "cam-vista"}).json()
    created = client.post(
        f"/sessions/{session['id']}/jobs", json={"kind": "synthetic_base_flow"}
    ).json()

    with client.websocket_connect(f"/ws/jobs/{created['id']}/preview"):
        pass

    stored = client.get(f"/jobs/{created['id']}").json()
    assert stored["status"] == created["status"]
