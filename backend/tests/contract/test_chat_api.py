"""POST /chat cites stored figures and does not call Azure."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from conftest import destructive_database_url
from fastapi.testclient import TestClient
from sqlalchemy import select

from alembic import command
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
from flowsight.llm.settings import AzureLlmConfigurationError
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.chat import Draft

BACKEND_DIR = Path(__file__).resolve().parents[2]
SIX = Decimal("0.000001")


@pytest.fixture()
def client() -> TestClient:
    database_url = destructive_database_url()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract-chat",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
        }
    )
    config = Config(BACKEND_DIR / "alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()
    command.downgrade(config, "base")


def test_answered_traffic_cites_the_stored_figure(client: TestClient, caplog) -> None:
    session_id, shop_id = _seed(client)

    def drafter(**kwargs):
        traffic = next(figure for figure in kwargs["figures"] if figure.code == "traffic_total")
        value = traffic.value.quantize(Decimal("1"))
        return Draft(text=f"El tráfico es {value}.", model_calls=1)

    client.app.state.chat_drafter = drafter
    with caplog.at_level("INFO"):
        response = client.post(
            "/chat",
            json={
                "question": "¿cuál es el tráfico?",
                "session_id": session_id,
                "shop_id": shop_id,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["scope"] == "whole_session"
    assert body["shop_name"] == "Local"
    assert body["model_calls"] <= 2
    traffic = next(figure for figure in body["figures"] if figure["code"] == "traffic_total")
    assert traffic["value"] == 17
    assert "17" in body["message"]
    assert "¿cuál es el tráfico?" not in caplog.text


def test_invented_number_is_not_answered(client: TestClient) -> None:
    session_id, shop_id = _seed(client)
    def invent(**_kwargs):
        return Draft(text="el tráfico es 123456", model_calls=1)

    client.app.state.chat_drafter = invent
    response = client.post(
        "/chat",
        json={"question": "tráfico", "session_id": session_id, "shop_id": shop_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "refused"
    assert "123456" not in body["message"]


def test_prohibited_questions_do_not_call_the_drafter(client: TestClient) -> None:
    session_id, shop_id = _seed(client)

    def drafter(**_kwargs):
        return Draft(text="el valor es 123456", model_calls=1)

    client.app.state.chat_drafter = drafter
    questions = (
        "¿confirmamos la compra?",
        "¿quién es esa persona?",
        "seguila entre cámaras",
        "¿va a llover?",
        "¿cuántas salidas hubo?",
        "¿cuántos pasos frente al local?",
        "¿cuál es la tasa de ingreso?",
    )
    for question in questions:
        response = client.post(
            "/chat",
            json={"question": question, "session_id": session_id, "shop_id": shop_id},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "refused"
        assert body["model_calls"] == 0
        assert body["figures"] == []
        assert "123456" not in body["message"]
        assert not any(character.isdigit() for character in body["message"])


def test_a_bad_draft_is_not_shown(client: TestClient) -> None:
    session_id, shop_id = _seed(client)

    def drafter(**_kwargs):
        return Draft(text="Confirmó la compra.", model_calls=1)

    client.app.state.chat_drafter = drafter
    response = client.post(
        "/chat",
        json={"question": "tráfico", "session_id": session_id, "shop_id": shop_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "refused"
    assert body["model_calls"] == 0
    assert "Confirmó" not in body["message"]
    assert "compra" not in body["message"].casefold()


def test_empty_question_is_400_and_missing_session_is_404(client: TestClient) -> None:
    empty = client.post(
        "/chat",
        json={"question": "  ", "session_id": str(uuid.uuid4()), "shop_id": None},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"]["code"] == "empty_question"

    missing = client.post(
        "/chat",
        json={"question": "tráfico", "session_id": str(uuid.uuid4()), "shop_id": None},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"


def test_drafter_failures_leave_metrics_readable(client: TestClient, monkeypatch) -> None:
    session_id, shop_id = _seed(client)
    payload = {"question": "tráfico", "session_id": session_id, "shop_id": shop_id}

    def unavailable():
        raise AzureLlmConfigurationError("missing")

    monkeypatch.setattr("flowsight.services.chat.load_azure_llm_settings", unavailable)
    client.app.state.chat_drafter = None
    missing_config = client.post("/chat", json=payload)
    assert missing_config.status_code == 200
    assert missing_config.json()["status"] == "error"
    assert "no está configurado" in missing_config.json()["message"]
    assert missing_config.json()["figures"] == []

    def too_slow(**_kwargs):
        time.sleep(1)
        return Draft(text="tarde", model_calls=1)

    client.app.state.chat_drafter = too_slow
    client.app.state.settings.chat_timeout_seconds = 0.2
    timed_out = client.post("/chat", json=payload)
    assert timed_out.status_code == 200
    assert timed_out.json()["status"] == "error"
    assert "tardó demasiado" in timed_out.json()["message"]
    assert timed_out.json()["figures"] == []

    client.app.state.chat_drafter = lambda **_kwargs: Draft(text="", model_calls=1)
    client.app.state.settings.chat_timeout_seconds = 20
    empty = client.post("/chat", json=payload)
    assert empty.status_code == 200
    assert empty.json()["status"] == "error"
    assert "no devolvió" in empty.json()["message"]
    assert empty.json()["figures"] == []

    metrics = client.get(f"/sessions/{session_id}/shops/{shop_id}/metrics")
    assert metrics.status_code == 200


def test_last_session_uses_the_latest_finish_and_the_open_one_otherwise(client: TestClient) -> None:
    early, shop_id = _processed(
        client,
        name="Mañana",
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        traffic=11,
        version_number=1,
    )
    late, _shop = _processed(
        client,
        name="Tarde",
        finished_at=datetime(2026, 9, 3, tzinfo=UTC),
        traffic=29,
        version_number=2,
        shop_id=shop_id,
    )
    seen: list[list[dict[str, object]]] = []

    def drafter(**kwargs):
        seen.append(kwargs["sessions"])
        traffic = next(figure for figure in kwargs["figures"] if figure.code == "traffic_total")
        return Draft(text=f"El tráfico es {traffic.value.quantize(Decimal('1'))}.", model_calls=1)

    client.app.state.chat_drafter = drafter
    opened = client.post(
        "/chat",
        json={"question": "¿cuál es el tráfico?", "session_id": early, "shop_id": shop_id},
    )
    assert opened.status_code == 200
    assert opened.json()["session_id"] == early
    assert "11" in opened.json()["message"]

    last = client.post(
        "/chat",
        json={"question": "tráfico de la última", "session_id": early, "shop_id": shop_id},
    )
    assert last.status_code == 200
    body = last.json()
    assert body["status"] == "answered"
    assert body["session_id"] == late
    assert "29" in body["message"]
    assert "11" not in body["message"]
    catalog = seen[-1]
    assert catalog
    assert set(catalog[0]) == {"session_id", "name", "finished_at", "result_complete"}


def test_tied_finish_uses_the_larger_job_id(client: TestClient) -> None:
    moment = datetime(2026, 9, 2, tzinfo=UTC)
    smaller, shop_id = _processed(
        client,
        name="Una",
        finished_at=moment,
        traffic=11,
        version_number=1,
        job_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
    )
    larger, _shop = _processed(
        client,
        name="Otra",
        finished_at=moment,
        traffic=29,
        version_number=2,
        shop_id=shop_id,
        job_id=uuid.UUID("00000000-0000-4000-8000-00000000000a"),
    )
    client.app.state.chat_drafter = _traffic_drafter
    response = client.post(
        "/chat",
        json={"question": "la última sesión", "session_id": smaller, "shop_id": shop_id},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == larger
    assert "29" in response.json()["message"]


def test_a_session_name_selects_that_session(client: TestClient) -> None:
    morning, shop_id = _processed(
        client,
        name="Mañana",
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        traffic=11,
        version_number=1,
    )
    afternoon, _shop = _processed(
        client,
        name="Tarde",
        finished_at=datetime(2026, 9, 3, tzinfo=UTC),
        traffic=29,
        version_number=2,
        shop_id=shop_id,
    )
    client.app.state.chat_drafter = _traffic_drafter
    response = client.post(
        "/chat",
        json={
            "question": "tráfico de la sesión mañana",
            "session_id": afternoon,
            "shop_id": shop_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == morning
    assert "11" in response.json()["message"]
    assert "29" not in response.json()["message"]


def test_two_sessions_with_the_same_name_ask_instead_of_choosing(client: TestClient) -> None:
    first, shop_id = _processed(
        client,
        name="Feria",
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        traffic=11,
        version_number=1,
    )
    _processed(
        client,
        name="Feria",
        finished_at=datetime(2026, 9, 3, tzinfo=UTC),
        traffic=29,
        version_number=2,
        shop_id=shop_id,
    )

    def drafter(**_kwargs):
        raise AssertionError("el redactor no debe elegirse")

    client.app.state.chat_drafter = drafter
    response = client.post(
        "/chat",
        json={"question": "tráfico de feria", "session_id": first, "shop_id": shop_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["model_calls"] == 0
    assert body["figures"] == []
    assert "11" not in body["message"]
    assert "29" not in body["message"]


def test_no_processed_sessions_does_not_invent_figures(client: TestClient) -> None:
    with client.app.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-vacia")
        flow = Session(
            name="Vacía",
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.SYNTHETIC,
        )
        db.add(flow)
        db.flush()
        session_id = str(flow.id)

    response = client.post(
        "/chat",
        json={"question": "la última", "session_id": session_id, "shop_id": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_calls"] == 0
    assert body["figures"] == []
    assert "procesad" in body["message"].casefold()
    assert not any(character.isdigit() for character in body["message"])


def test_an_incomplete_latest_analysis_is_not_replaced(client: TestClient) -> None:
    _processed(
        client,
        name="Temprana",
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        traffic=11,
        version_number=1,
    )
    late, shop_id = _processed(
        client,
        name="Tardía",
        finished_at=datetime(2026, 9, 2, tzinfo=UTC),
        traffic=99,
        version_number=2,
    )
    with client.app.state.session_factory.begin() as db:
        previous = db.scalar(
            select(ProcessingJob).where(ProcessingJob.session_id == uuid.UUID(late))
        )
        assert previous is not None
        db.add(
            ProcessingJob(
                session_id=previous.session_id,
                scene_version_id=previous.scene_version_id,
                registered_camera_id=previous.registered_camera_id,
                kind=JobKind.VIDEO_ANALYSIS,
                status=JobStatus.FAILED,
                created_at=datetime(2026, 9, 4, tzinfo=UTC),
                finished_at=datetime(2026, 9, 4, tzinfo=UTC),
                result_complete=False,
                failure_code="analysis_failed",
                failure_message="no se pudo analizar",
            )
        )
    client.app.state.chat_drafter = _traffic_drafter
    response = client.post(
        "/chat",
        json={"question": "tráfico de la última", "session_id": late, "shop_id": shop_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["session_id"] == late
    assert body["figures"] == []
    assert "99" not in body["message"]
    assert "11" not in body["message"]


def _traffic_drafter(**kwargs):
    traffic = next(figure for figure in kwargs["figures"] if figure.code == "traffic_total")
    return Draft(text=f"El tráfico es {traffic.value.quantize(Decimal('1'))}.", model_calls=1)


def _processed(
    client: TestClient,
    *,
    name: str,
    finished_at: datetime,
    traffic: int,
    version_number: int,
    shop_id: str | None = None,
    job_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    with client.app.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-api")
        flow = Session(
            name=name,
            camera_id=camera.name,
            registered_camera_id=camera.id,
            source_kind=SourceKind.SYNTHETIC,
        )
        db.add(flow)
        db.flush()
        shop = (
            db.get(Shop, uuid.UUID(shop_id))
            if shop_id is not None
            else Shop(camera_id=camera.id)
        )
        if shop_id is None:
            db.add(shop)
            db.flush()
        version = SceneVersion(
            camera_id=camera.id,
            version_number=version_number,
            reference_session_id=flow.id,
            frame_width=320,
            frame_height=240,
        )
        db.add(version)
        db.flush()
        assert shop is not None
        db.add(
            SceneVersionShop(
                scene_version_id=version.id,
                shop_id=shop.id,
                camera_id=camera.id,
                position=0,
                name="Local",
                name_key="local",
            )
        )
        job = ProcessingJob(
            id=job_id or uuid.uuid4(),
            session_id=flow.id,
            scene_version_id=version.id,
            registered_camera_id=camera.id,
            kind=JobKind.VIDEO_ANALYSIS,
            status=JobStatus.COMPLETED,
            created_at=finished_at,
            finished_at=finished_at,
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
                value=Decimal(traffic).quantize(SIX),
                availability=MeasureAvailability.AVAILABLE,
                label=ShopMetricLabel.VISIT_ESTIMATE,
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
                track_count=traffic,
            )
        )
        return str(flow.id), str(shop.id)


def _seed(client: TestClient) -> tuple[str, str]:
    with client.app.state.session_factory.begin() as db:
        camera = get_or_create_camera(db, "cam-chat-api")
        flow = Session(
            name="Chat",
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
                name="Local",
                name_key="local",
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
