"""Manual commands preserve the job and reject stale/foreign operations."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from flowsight.api.main import create_app
from flowsight.db.models import JobStatus, LiveAnalysisState, ProcessingJob
from flowsight.services.jobs import transition_job


@pytest.fixture
def client(live_job, monkeypatch):
    factory, job_id, _ = live_job
    monkeypatch.setenv("FLOWSIGHT_ENV", "test")
    monkeypatch.setenv("FLOWSIGHT_WORKER_ID", "pause-contract-worker")
    monkeypatch.setenv("FLOWSIGHT_MACHINE_ID", "expo-runner")
    monkeypatch.setenv("FLOWSIGHT_LIVE_CHANNEL_TOKEN", "synthetic-pause-test-token")
    with factory.begin() as database:
        transition_job(
            database, job_id=job_id, target=JobStatus.PROCESSING, occurred_at=datetime.now(UTC)
        )
        database.get(LiveAnalysisState, job_id).capture_status = "connected"
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client, factory, job_id
    app.state.engine.dispose()


def test_pause_is_idempotent(client):
    http, factory, job_id = client
    url = f"/jobs/{job_id}/live/pause"
    assert http.post(url).status_code == 202
    with factory() as database:
        first = database.get(LiveAnalysisState, job_id).pause_requested_at
        assert first is not None
    assert http.post(url).status_code == 202
    with factory() as database:
        state = database.get(LiveAnalysisState, job_id)
        assert state.pause_requested_at == first and state.capture_status == "pausing"
        assert database.get(ProcessingJob, job_id).status == JobStatus.PROCESSING


def test_continue_requires_acknowledged_pause(client):
    http, factory, job_id = client
    url = f"/jobs/{job_id}/live/continue"
    assert http.post(url).status_code == 409
    assert http.post(f"/jobs/{job_id}/live/pause").status_code == 202
    assert http.post(url).status_code == 409
    with factory.begin() as database:
        state = database.get(LiveAnalysisState, job_id)
        state.capture_status = "paused"
        state.paused_at = datetime.now(UTC)
    assert http.post(url).status_code == 202
    with factory() as database:
        timestamp = database.get(LiveAnalysisState, job_id).resume_requested_at
    assert http.post(url).status_code == 202
    with factory() as database:
        assert database.get(LiveAnalysisState, job_id).resume_requested_at == timestamp


def test_stop_wins_over_pause_and_continue(client):
    http, _, job_id = client
    assert http.post(f"/jobs/{job_id}/live/stop").status_code == 202
    for action in ("pause", "continue"):
        assert http.post(f"/jobs/{job_id}/live/{action}").status_code == 409


def test_pause_rejects_wrong_machine(client):
    http, factory, job_id = client
    http.app.state.settings.machine_id = "another-machine"
    assert http.post(f"/jobs/{job_id}/live/pause").status_code == 409
    with factory() as database:
        assert database.get(LiveAnalysisState, job_id).capture_status == "connected"
