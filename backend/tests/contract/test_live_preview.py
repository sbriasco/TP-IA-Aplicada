"""The live broker replaces stale frames and the producer is restricted to loopback."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from flowsight.api.main import create_app
from flowsight.preview.live_channel import LiveBroker
from flowsight.preview.live_messages import LiveUpdate
from flowsight.worker.live_control import MachineLease


def update(job_id, revision=1, sequence=1):
    return {
        "type": "live.update",
        "schema_version": "3",
        "source_kind": "webcam",
        "session_id": str(uuid.UUID(int=1)),
        "job_id": str(job_id),
        "revision": revision,
        "capture_status": "connected",
        "segment_index": 0,
        "capture_sequence": sequence,
        "capture_timestamp_seconds": sequence / 10,
        "captured_monotonic_ms": 100,
        "published_monotonic_ms": 110,
        "image_media_type": "image/jpeg",
        "image_base64": "eA==",
        "partial": True,
        "capture_fps": 30.0,
        "analysis_fps": 10.0,
        "capture_to_publish_ms": 10,
        "shops": [],
        "minutes": [],
        "coverage_complete": True,
        "checkpoint_revision": 0,
        "checkpoint_at": None,
    }


def test_slow_observer_keeps_only_newest_pair():
    async def run():
        broker = LiveBroker()
        job = uuid.uuid4()
        observer = broker.subscribe(job)
        for revision in range(1, 100):
            assert broker.publish(LiveUpdate.model_validate(update(job, revision, revision)))
        assert observer.pending_count == 1
        message = await observer.receive()
        assert message["revision"] == 99 and message["capture_sequence"] == 99
        assert observer.pending_count == 0

    asyncio.run(run())


def test_old_revision_rejected_but_same_frame_new_revision_allowed():
    broker = LiveBroker()
    job = uuid.uuid4()
    assert broker.publish(LiveUpdate.model_validate(update(job, 4, 3)))
    assert not broker.publish(LiveUpdate.model_validate(update(job, 3, 3)))
    assert broker.publish(LiveUpdate.model_validate(update(job, 5, 3)))
    assert not broker.publish(LiveUpdate.model_validate(update(job, 6, 2)))


def test_broker_observers_are_bounded_and_preview_expires():
    clock = [100.0]
    broker = LiveBroker(clock=lambda: clock[0])
    job = uuid.uuid4()
    observers = [broker.subscribe(job) for _ in range(8)]
    with pytest.raises(ValueError, match="observer_limit"):
        broker.subscribe(job)
    broker.publish(LiveUpdate.model_validate(update(job)))
    assert broker.latest(job) is not None
    clock[0] += 10.1
    assert broker.latest(job) is None
    assert all(observer.pending is None for observer in observers)
    for observer in observers:
        broker.unsubscribe(job, observer)
    assert broker.observer_count == 0


def test_reconnect_check_is_neutral_cached_and_expires_with_its_image():
    from flowsight.preview.live_messages import CaptureReconnectCheck

    clock = [100.0]
    broker = LiveBroker(clock=lambda: clock[0])
    job_id = uuid.uuid4()
    payload = CaptureReconnectCheck.model_validate(
        {
            "type": "capture.reconnect-check",
            "schema_version": "3",
            "source_kind": "webcam",
            "job_id": str(job_id),
            "session_id": str(uuid.uuid4()),
            "revision": 2,
            "capture_status": "awaiting_confirmation",
            "segment_index": 1,
            "device_index": 0,
            "width": 320,
            "height": 180,
            "backend": "fake",
            "image_media_type": "image/jpeg",
            "image_base64": "eA==",
        }
    )
    neutral = payload.model_dump(mode="json")
    neutral["type"] = "live.reconnect-check"
    neutral["check_token"] = "fresh-nonce"
    neutral["expires_in_seconds"] = 60
    broker.reconnect_check(job_id, neutral)
    observer = broker.subscribe(job_id)
    assert observer.pending == neutral and "shops" not in observer.pending
    assert "capture_timestamp_seconds" not in observer.pending
    clock[0] += 10.1
    assert broker.latest(job_id) is None and observer.pending is None

    with pytest.raises(ValidationError):
        CaptureReconnectCheck.model_validate({**payload.model_dump(), "shops": []})


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_base64", "x" * 300000),
        ("capture_timestamp_seconds", float("nan")),
        ("revision", -1),
        ("shops", [{}] * 21),
        ("image_media_type", "text/html"),
    ],
    ids=["oversize-image", "nan-time", "negative-revision", "shops-limit", "media-type"],
)
def test_message_bounds(field, value):
    message = update(uuid.uuid4())
    message[field] = value
    with pytest.raises(ValidationError):
        LiveUpdate.model_validate(message)


@pytest.fixture
def producer_app(live_engine, monkeypatch):
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv(
        "FLOWSIGHT_DATABASE_URL", live_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-channel")
    monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", "expo-channel")
    monkeypatch.setenv("FLOWSIGHT_LIVE_CHANNEL_TOKEN", "local-test-token")
    app = create_app()
    lease = MachineLease(app.state.engine, "expo-channel", "worker-channel")
    assert lease.acquire(datetime.now(UTC))
    yield app, lease
    lease.release()
    app.state.engine.dispose()


def headers(lease, token="local-test-token"):
    return {
        "Authorization": f"Bearer {token}",
        "X-FlowSight-Worker": "worker-channel",
        "X-FlowSight-Owner": str(lease.owner_epoch),
    }


@pytest.mark.parametrize("reason", ["bad_token", "remote_peer", "other_machine"])
def test_producer_authentication(producer_app, reason):
    app, lease = producer_app
    peer = ("203.0.113.12", 3000) if reason == "remote_peer" else ("127.0.0.1", 3000)
    token = "incorrect" if reason == "bad_token" else "local-test-token"
    machine = "another-machine" if reason == "other_machine" else "expo-channel"
    with TestClient(app, client=peer) as client, pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            f"/ws/internal/live/{machine}", headers=headers(lease, token)
        ):
            pass
    assert error.value.code == 1008


def test_valid_producer_registers_and_disconnect_clears_channel(producer_app):
    app, lease = producer_app
    with TestClient(app, client=("127.0.0.1", 3000)) as client:
        with client.websocket_connect(
            "/ws/internal/live/expo-channel", headers=headers(lease)
        ) as ws:
            assert ws.receive_json()["type"] == "producer.ready"
            assert app.state.live_channel.available
    assert not app.state.live_channel.available


def test_probe_request_returns_over_authenticated_channel(producer_app):
    import base64
    import threading

    app, lease = producer_app
    with TestClient(app, client=("127.0.0.1", 3000)) as client:
        camera = client.post("/cameras", json={"name": "Probe channel"}).json()
        with client.websocket_connect(
            "/ws/internal/live/expo-channel", headers=headers(lease)
        ) as ws:
            assert ws.receive_json()["type"] == "producer.ready"
            responses = []
            thread = threading.Thread(
                target=lambda: responses.append(
                    client.post(
                        "/live/sessions",
                        json={
                            "name": "Probe",
                            "registered_camera_id": camera["id"],
                            "device_index": 0,
                        },
                    )
                )
            )
            thread.start()
            control = ws.receive_json()
            assert control["type"] == "capture.probe" and control["device_index"] == 0
            ws.send_json(
                {
                    "type": "capture.probe.result",
                    "request_id": control["request_id"],
                    "image_base64": base64.b64encode(b"jpeg").decode(),
                    "width": 320,
                    "height": 180,
                    "backend": "fake",
                    "device_index": 0,
                }
            )
            thread.join(6)
            assert not thread.is_alive() and responses
            assert responses[0].status_code == 201, responses[0].text
            assert responses[0].json()["source_kind"] == "webcam"


def prepared_job(app, lease):
    from sqlalchemy.orm import Session

    from flowsight.capture.contracts import CaptureProbeResult
    from flowsight.db.models import Camera, SceneVersion
    from flowsight.services.live_jobs import start_live_job
    from flowsight.services.live_sessions import prepare_session

    with Session(app.state.engine) as database, database.begin():
        camera = Camera(id=uuid.uuid4(), name="Clock", name_key="clock")
        database.add(camera)
        database.flush()
        session = prepare_session(
            database,
            name="Clock",
            camera_id=camera.id,
            machine_id="expo-channel",
            label_mode="directions",
            probe=CaptureProbeResult(b"reference-jpeg", 320, 180, "fake", 0),
            now=datetime.now(UTC),
        )
        version = SceneVersion(
            id=uuid.uuid4(),
            camera_id=camera.id,
            version_number=1,
            reference_session_id=session.id,
            frame_width=320,
            frame_height=180,
        )
        database.add(version)
        database.flush()
        token = app.state.live_checks.issue(
            session_id=session.id,
            machine_id="expo-channel",
            owner_epoch=lease.owner_epoch,
            device_index=0,
            width=320,
            height=180,
        )
        job = start_live_job(
            database,
            session_id=session.id,
            machine_id="expo-channel",
            scene_version_id=version.id,
            checks=app.state.live_checks,
            check_token=token,
            frame_confirmed=True,
            now=datetime.now(UTC),
        )
        job_id = job.id
        session_id = session.id
    return job_id, session_id


def test_public_observer_receives_calibrated_clock_and_no_reference_as_live(producer_app):
    app, lease = producer_app
    job_id, _ = prepared_job(app, lease)
    with TestClient(app) as client, client.websocket_connect(f"/ws/jobs/{job_id}/preview") as ws:
        ws.send_json({"type": "clock.ping", "nonce": "clock-1", "client_sent_ms": 50.0})
        message = ws.receive_json()
        if message["type"] != "clock.pong":
            assert message["type"] == "live.status" and "image_base64" not in message
            message = ws.receive_json()
        assert message["type"] == "clock.pong" and message["client_sent_ms"] == 50
        assert message["server_sent_monotonic_ms"] >= message["server_received_monotonic_ms"]


def test_producer_reconnect_frame_gets_a_job_bound_nonce_without_advancing_metrics(producer_app):
    import time

    from flowsight.db.models import LiveAnalysisState
    from flowsight.worker.lifecycle import claim_next_job

    app, lease = producer_app
    job_id, session_id = prepared_job(app, lease)
    with app.state.session_factory.begin() as database:
        claim_next_job(
            database,
            "worker-channel",
            datetime.now(UTC),
            machine_id="expo-channel",
            owner_epoch=lease.owner_epoch,
        )
        database.get(LiveAnalysisState, job_id).capture_status = "awaiting_confirmation"
    with TestClient(app, client=("127.0.0.1", 3000)) as client:
        with client.websocket_connect(
            "/ws/internal/live/expo-channel", headers=headers(lease)
        ) as ws:
            assert ws.receive_json()["type"] == "producer.ready"
            ws.send_json(
                {
                    "type": "capture.reconnect-check",
                    "schema_version": "3",
                    "source_kind": "webcam",
                    "job_id": str(job_id),
                    "session_id": str(session_id),
                    "revision": 0,
                    "capture_status": "awaiting_confirmation",
                    "segment_index": 1,
                    "device_index": 0,
                    "width": 320,
                    "height": 180,
                    "backend": "fake",
                    "image_media_type": "image/jpeg",
                    "image_base64": "eA==",
                }
            )
            deadline = time.monotonic() + 2
            while app.state.live_broker.latest(job_id) is None and time.monotonic() < deadline:
                time.sleep(0.01)
            neutral = app.state.live_broker.latest(job_id)
            assert neutral is not None and neutral["type"] == "live.reconnect-check"
            assert "shops" not in neutral and "capture_timestamp_seconds" not in neutral
            check = app.state.live_checks.require(
                neutral["check_token"],
                session_id=session_id,
                machine_id="expo-channel",
                owner_epoch=lease.owner_epoch,
                device_index=0,
                job_id=job_id,
            )
            assert check.segment_index == 1 and check.width == 320
            with client.websocket_connect(f"/ws/jobs/{job_id}/preview") as observer:
                assert observer.receive_json()["check_token"] == neutral["check_token"]
    with app.state.session_factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert state.elapsed_capture_seconds == 0 and state.revision == 0
        assert state.resume_confirmed_at is None


@pytest.mark.parametrize(
    "field,value", [("segment_index", 0), ("device_index", 1), ("revision", 1)]
)
def test_reconnect_frame_rejects_stale_or_wrong_device_context(producer_app, field, value):
    from flowsight.db.models import LiveAnalysisState
    from flowsight.worker.lifecycle import claim_next_job

    app, lease = producer_app
    job_id, session_id = prepared_job(app, lease)
    with app.state.session_factory.begin() as database:
        claim_next_job(
            database,
            "worker-channel",
            datetime.now(UTC),
            machine_id="expo-channel",
            owner_epoch=lease.owner_epoch,
        )
        database.get(LiveAnalysisState, job_id).capture_status = "awaiting_confirmation"
    payload = {
        "type": "capture.reconnect-check",
        "schema_version": "3",
        "source_kind": "webcam",
        "job_id": str(job_id),
        "session_id": str(session_id),
        "revision": 0,
        "capture_status": "awaiting_confirmation",
        "segment_index": 1,
        "device_index": 0,
        "width": 320,
        "height": 180,
        "backend": "fake",
        "image_media_type": "image/jpeg",
        "image_base64": "eA==",
        field: value,
    }
    with TestClient(app, client=("127.0.0.1", 3000)) as client:
        with client.websocket_connect(
            "/ws/internal/live/expo-channel", headers=headers(lease)
        ) as ws:
            assert ws.receive_json()["type"] == "producer.ready"
            ws.send_json(payload)
            with pytest.raises(WebSocketDisconnect) as error:
                ws.receive_json()
            assert error.value.code == 1008
    assert app.state.live_broker.latest(job_id) is None
