"""Chat threads list/detail and follow-up persistence via POST /chat."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient

from flowsight.api.main import create_app
from flowsight.db.models import (
    JobKind,
    JobStatus,
    MeasureAvailability,
    ProcessingJob,
    SceneVersion,
    SceneVersionShop,
    Session,
    Shop,
    ShopMetric,
    ShopMetricCode,
    ShopMetricLabel,
    SourceKind,
    TrafficBucket,
)
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.chat import Draft

SIX = Decimal("0.000001")


@pytest.fixture()
def client() -> TestClient:
    database_url = prepare_empty_schema()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract-chat-threads",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
        }
    )
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()


def test_follow_up_reuses_thread_and_lists_history(client: TestClient) -> None:
    session_id, shop_id = _seed(client)

    def drafter(**kwargs):
        history = kwargs.get("history") or []
        if any("tráfico" in turn.get("content", "").casefold() for turn in history):
            dwell = next(
                (figure for figure in kwargs["figures"] if figure.code == "dwell_mean_seconds"),
                None,
            )
            if dwell and dwell.value is not None:
                return Draft(
                    text=f"La permanencia media es {dwell.value.quantize(Decimal('1'))} s.",
                    model_calls=1,
                )
        traffic = next(figure for figure in kwargs["figures"] if figure.code == "traffic_total")
        return Draft(text=f"El tráfico es {traffic.value.quantize(Decimal('1'))}.", model_calls=1)

    client.app.state.chat_drafter = drafter
    first = client.post(
        "/chat",
        json={"question": "¿cuál es el tráfico?", "session_id": session_id, "shop_id": shop_id},
    )
    assert first.status_code == 200
    thread_id = first.json()["thread_id"]
    assert thread_id
    second = client.post(
        "/chat",
        json={
            "question": "¿y la permanencia?",
            "session_id": session_id,
            "shop_id": shop_id,
            "thread_id": thread_id,
        },
    )
    assert second.status_code == 200
    assert second.json()["thread_id"] == thread_id
    assert "permanencia" in second.json()["message"].casefold()

    listed = client.get(f"/sessions/{session_id}/chat-threads")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == thread_id

    detail = client.get(f"/chat-threads/{thread_id}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["answer"]["status"] == "answered"


def test_new_thread_without_thread_id(client: TestClient) -> None:
    session_id, shop_id = _seed(client)

    def drafter(**kwargs):
        traffic = next(figure for figure in kwargs["figures"] if figure.code == "traffic_total")
        return Draft(text=f"El tráfico es {traffic.value.quantize(Decimal('1'))}.", model_calls=1)

    client.app.state.chat_drafter = drafter
    a = client.post(
        "/chat",
        json={"question": "tráfico uno", "session_id": session_id, "shop_id": shop_id},
    )
    b = client.post(
        "/chat",
        json={"question": "tráfico dos", "session_id": session_id, "shop_id": shop_id},
    )
    assert a.json()["thread_id"] != b.json()["thread_id"]
    listed = client.get(f"/sessions/{session_id}/chat-threads")
    assert len(listed.json()) == 2


def _seed(client: TestClient) -> tuple[str, str]:
    with client.app.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-threads")
        flow = Session(
            name="Análisis hilos",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.SYNTHETIC,
        )
        db.add(flow)
        db.flush()
        shop = Shop(camera_id=camera.id)
        version = SceneVersion(
            camera_id=camera.id,
            version_number=1,
            reference_session_id=flow.id,
            frame_width=320,
            frame_height=240,
        )
        db.add_all([shop, version])
        db.flush()
        db.add(
            SceneVersionShop(
                scene_version_id=version.id,
                shop_id=shop.id,
                camera_id=camera.id,
                position=0,
                name="Zona A",
                name_key="zona a",
            )
        )
        job = ProcessingJob(
            session_id=flow.id,
            scene_version_id=version.id,
            registered_camera_id=camera.id,
            kind=JobKind.VIDEO_ANALYSIS,
            status=JobStatus.COMPLETED,
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
            finished_at=datetime(2026, 9, 1, tzinfo=UTC),
            result_complete=True,
        )
        db.add(job)
        db.flush()
        db.add(
            ShopMetric(
                job_id=job.id,
                session_id=flow.id,
                shop_id=shop.id,
                code=ShopMetricCode.TRAFFIC_TOTAL,
                value=Decimal("17").quantize(SIX),
                availability=MeasureAvailability.AVAILABLE,
                label=ShopMetricLabel.VISIT_ESTIMATE,
                unavailable_reason=None,
            )
        )
        db.add(
            ShopMetric(
                job_id=job.id,
                session_id=flow.id,
                shop_id=shop.id,
                code=ShopMetricCode.DWELL_MEAN_SECONDS,
                value=Decimal("42").quantize(SIX),
                availability=MeasureAvailability.AVAILABLE,
                label=ShopMetricLabel.OBSERVABLE,
                unavailable_reason=None,
            )
        )
        db.add(
            TrafficBucket(
                job_id=job.id,
                session_id=flow.id,
                shop_id=shop.id,
                bucket_index=0,
                start_seconds=Decimal("0.000000"),
                track_count=17,
            )
        )
        return str(flow.id), str(shop.id)
