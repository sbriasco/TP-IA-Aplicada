"""Durable live snapshots expose crossings and coverage, never file-only analytics."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from flowsight.api.main import create_app
from flowsight.db.models import (
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveCrossing,
    LiveCrossingBucket,
    LivePositionSample,
    ProcessingJob,
    SceneVersionShop,
)
from flowsight.services.jobs import transition_job


@pytest.fixture
def results_client(live_job, monkeypatch):
    factory, job_id, _ = live_job
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "worker-results")
    application = create_app()
    with TestClient(application) as client:
        yield client, factory, job_id
    application.state.engine.dispose()


def seed_results(factory, job_id):
    with factory.begin() as database:
        job = database.get(ProcessingJob, job_id)
        shop = database.scalar(
            select(SceneVersionShop).where(
                SceneVersionShop.scene_version_id == job.scene_version_id
            )
        )
        segment_id = uuid.uuid4()
        database.add(
            LiveCaptureSegment(
                id=segment_id,
                job_id=job_id,
                session_id=job.session_id,
                segment_index=0,
                started_capture_seconds=0,
                ended_capture_seconds=61,
                first_sequence=1,
                last_sequence=4,
                reason="initial",
            )
        )
        database.flush()
        for candidate, timestamp, direction in [
            (1, "5", "entry"),
            (2, "20", "exit"),
            (3, "60.1", "entry"),
        ]:
            database.add(
                LiveCrossing(
                    job_id=job_id,
                    session_id=job.session_id,
                    segment_id=segment_id,
                    shop_id=shop.shop_id,
                    track_id=1,
                    candidate_sequence=candidate,
                    capture_sequence=candidate,
                    capture_timestamp_seconds=Decimal(timestamp),
                    confirmed_at_capture_seconds=Decimal(timestamp) + Decimal(".4"),
                    direction=direction,
                    foot_x=Decimal(".5"),
                    foot_y=Decimal(".5"),
                )
            )
        for index, entries, exits, observed, missing, end in [
            (0, 1, 1, 60, 0, 60),
            (1, 1, 0, 0, 1, 61),
        ]:
            database.add(
                LiveCrossingBucket(
                    job_id=job_id,
                    session_id=job.session_id,
                    shop_id=shop.shop_id,
                    bucket_index=index,
                    start_seconds=index * 60,
                    end_seconds=end,
                    entries=entries,
                    exits=exits,
                    observed_seconds=observed,
                    missing_seconds=missing,
                    pending_count=0,
                    is_open=False,
                    coverage_incomplete=missing > 0,
                    unknown_tail=False,
                    revision=3,
                )
            )
        state = database.get(LiveAnalysisState, job_id)
        state.revision = 3
        state.capture_status = "ended"
        state.elapsed_capture_seconds = 61
        state.observed_seconds, state.missing_seconds = 60, 1
        state.coverage_complete = False
        transition_job(
            database, job_id=job_id, target=JobStatus.PROCESSING, occurred_at=datetime.now(UTC)
        )
        transition_job(
            database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=datetime.now(UTC)
        )
        return job.session_id, shop.shop_id


def test_pending_snapshot_has_zero_capture_duration(results_client):
    client, _, job_id = results_client
    response = client.get(f"/jobs/{job_id}/live-results")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_kind"] == "webcam" and data["elapsed_capture_seconds"] == 0
    assert data["summary"]["total_crossings"] == 0 and data["summary"]["partial"]
    assert data["capture_status"] == "starting" and data["revision"] == 0
    assert "image_base64" not in data and "visits" not in data["summary"]


def test_completed_snapshot_keeps_coverage_separate_from_completion(results_client):
    client, factory, job_id = results_client
    _, shop_id = seed_results(factory, job_id)
    response = client.get(f"/jobs/{job_id}/live-results")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["result_complete"] and not data["coverage_complete"]
    assert data["selected_shop_id"] == str(shop_id)
    assert data["summary"]["entry_count"] == data["summary"]["a_to_b_count"] == 2
    assert data["summary"]["exit_count"] == data["summary"]["b_to_a_count"] == 1
    assert data["summary"]["total_crossings"] == 3 and not data["summary"]["partial"]
    assert data["summary"]["entry_direction"] == "a_to_b"
    assert data["minutes"][1]["missing_seconds"] == 1 and data["minutes"][1]["coverage_incomplete"]


def test_events_pagination_and_time_filter_do_not_mix_sessions(results_client):
    client, factory, job_id = results_client
    seed_results(factory, job_id)
    page = client.get(f"/jobs/{job_id}/live-events?limit=2")
    assert page.status_code == 200, page.text
    data = page.json()
    assert [event["capture_timestamp_seconds"] for event in data["events"]] == [5, 20]
    assert data["next_cursor"]
    second = client.get(
        f"/jobs/{job_id}/live-events", params={"limit": 2, "cursor": data["next_cursor"]}
    ).json()
    assert [event["capture_timestamp_seconds"] for event in second["events"]] == [60.1]
    filtered = client.get(f"/jobs/{job_id}/live-events?from_seconds=10&to_seconds=30").json()
    assert [event["capture_timestamp_seconds"] for event in filtered["events"]] == [20]
    assert client.get(f"/jobs/{job_id}/live-events?limit=251").status_code == 422


def test_foreign_shop_and_retired_session_are_hidden(results_client):
    from flowsight.db.models import Session

    client, factory, job_id = results_client
    session_id, _ = seed_results(factory, job_id)
    assert client.get(f"/jobs/{job_id}/live-results?shop_id={uuid.uuid4()}").status_code == 404
    with factory.begin() as database:
        database.get(Session, session_id).deleted_at = datetime.now(UTC)
    assert client.get(f"/jobs/{job_id}/live-results").status_code == 404
    assert client.get(f"/jobs/{job_id}/live-events").status_code == 404


def test_live_history_has_capture_metadata_and_no_missing_video(results_client):
    client, factory, job_id = results_client
    seed_results(factory, job_id)
    row = next(
        row for row in client.get("/processed-sessions").json() if row["job_id"] == str(job_id)
    )
    assert row["source_kind"] == "webcam"
    assert row["live_duration_seconds"] == 61 and not row["coverage_complete"]
    assert row["video_filename"] is None and row["video_availability"] is None


def test_live_positions_are_bounded_and_use_capture_time(results_client):
    client, factory, job_id = results_client
    session_id, _ = seed_results(factory, job_id)
    with factory.begin() as database:
        segment = database.scalar(
            select(LiveCaptureSegment).where(LiveCaptureSegment.job_id == job_id)
        )
        database.add_all(
            [
                LivePositionSample(
                    job_id=job_id,
                    session_id=session_id,
                    slot_index=index,
                    segment_id=segment.id,
                    track_id=1,
                    capture_sequence=index + 1,
                    capture_timestamp_seconds=Decimal(index) / 100,
                    foot_x=Decimal(".5"),
                    foot_y=Decimal(".4"),
                )
                for index in range(2001)
            ]
        )
    data = client.get(f"/jobs/{job_id}/position-samples").json()
    assert data["source_kind"] == "webcam" and data["time_basis"] == "capture"
    assert data["sample_count"] == 2001 and data["returned_count"] == 2000
    assert data["capacity"] == 20000 and len(data["samples"]) == 2000
    assert "capture_timestamp_seconds" in data["samples"][0]
    assert (
        "video_timestamp_seconds" not in data["samples"][0] and "track_id" not in data["samples"][0]
    )


def test_webcam_chat_is_rejected_before_reading_figures_or_calling_model(
    results_client, monkeypatch
):
    import flowsight.services.chat as chat_service

    client, factory, job_id = results_client
    session_id, shop_id = seed_results(factory, job_id)

    def unexpected(*args, **kwargs):
        raise AssertionError("A webcam must never invoke the model or commercial metrics")

    monkeypatch.setattr(chat_service, "read_figures", unexpected)
    monkeypatch.setattr(chat_service, "azure_draft", unexpected)
    response = client.post(
        "/chat",
        json={
            "session_id": str(session_id),
            "shop_id": str(shop_id),
            "question": "Cuántas visitas hubo?",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "live_chat_unavailable"
