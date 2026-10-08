"""Position samples are the stored feet, or unavailable when the file is missing."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from conftest import prepare_empty_schema
from fastapi.testclient import TestClient

from flowsight.api.main import create_app
from flowsight.db.models import JobKind, JobStatus, ProcessingJob

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_url = prepare_empty_schema()
    os.environ.update(
        {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": database_url,
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-contract-positions",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
            "FLOWSIGHT_DETECTOR": "fake",
            "FLOWSIGHT_VIDEOS_DIR": str(tmp_path),
        }
    )
    application = create_app()
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()


def test_position_samples_read_the_file_or_report_it_missing(
    client: TestClient, tmp_path: Path
) -> None:
    created = client.post("/sessions", json={"name": "Mapa", "camera_id": "cam-map"})
    assert created.status_code == 201
    session_id = created.json()["id"]
    job = client.post(f"/sessions/{session_id}/jobs", json={"kind": "synthetic_base_flow"})
    assert job.status_code == 201
    job_id = job.json()["id"]
    relative = f"derived/{session_id}/{job_id}/trajectory.jsonl"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                json.dumps({"record": "header", "sample_every_frames": 5}),
                json.dumps(
                    {"record": "sample", "video_timestamp_seconds": 0.4, "foot": [0.2, 0.8]}
                ),
            ]
        ),
        encoding="utf-8",
    )
    with client.app.state.session_factory.begin() as database_session:
        stored = database_session.get(ProcessingJob, uuid.UUID(job_id))
        assert stored is not None
        stored.trajectory_relative_path = relative
        assert stored.kind is JobKind.SYNTHETIC_BASE_FLOW
        assert stored.status is JobStatus.PENDING

    found = client.get(f"/jobs/{job_id}/position-samples")
    assert found.status_code == 200
    body = found.json()
    assert body["availability"] == "available"
    assert body["samples"] == [{"video_timestamp_seconds": 0.4, "foot": [0.2, 0.8]}]
    assert "metrics" not in body

    path.unlink()
    missing = client.get(f"/jobs/{job_id}/position-samples")
    assert missing.status_code == 200
    assert missing.json()["availability"] == "unavailable"
    assert missing.json()["samples"] == []

    unknown = client.get(f"/jobs/{uuid.uuid4()}/position-samples")
    assert unknown.status_code == 404
