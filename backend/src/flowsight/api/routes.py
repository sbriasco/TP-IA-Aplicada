"""REST endpoints for persisted sessions and jobs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import selectinload
from starlette.websockets import WebSocketDisconnect

from flowsight.api.schemas import (
    JobCreate,
    JobResponse,
    JobTraceResponse,
    SessionCreate,
    SessionResponse,
)
from flowsight.db.models import (
    Event,
    JobStatus,
    JobStatusTransition,
    Observation,
    ProcessingJob,
    Session,
    SourceKind,
    SyntheticFrame,
)
from flowsight.preview.image import load_preview_base64

router = APIRouter()


def get_database_session(request: Request):
    with request.app.state.session_factory() as database_session:
        yield database_session


Database = Annotated[DatabaseSession, Depends(get_database_session)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": message},
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, database: Database) -> Session:
    flow_session = Session(
        name=payload.name.strip(),
        camera_id=payload.camera_id.strip(),
        source_kind=SourceKind.SYNTHETIC,
    )
    database.add(flow_session)
    database.commit()
    database.refresh(flow_session)
    return flow_session


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: uuid.UUID, database: Database) -> Session:
    flow_session = database.get(Session, session_id)
    if flow_session is None:
        raise not_found("Sesión inexistente.")
    return flow_session


@router.post(
    "/sessions/{session_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(session_id: uuid.UUID, payload: JobCreate, database: Database) -> ProcessingJob:
    if database.get(Session, session_id) is None:
        raise not_found("Sesión inexistente.")

    occurred_at = datetime.now(UTC)
    job = ProcessingJob(
        session_id=session_id,
        kind=payload.kind,
        status=JobStatus.PENDING,
        transitions=[
            JobStatusTransition(
                from_status=None,
                to_status=JobStatus.PENDING,
                occurred_at=occurred_at,
            )
        ],
    )
    database.add(job)
    database.commit()
    return get_job_record(database, job.id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, database: Database) -> ProcessingJob:
    job = get_job_record(database, job_id)
    if job is None:
        raise not_found("Trabajo inexistente.")
    return job


@router.get("/jobs/{job_id}/trace", response_model=JobTraceResponse)
def get_job_trace(job_id: uuid.UUID, database: Database) -> JobTraceResponse:
    job = get_job_record(database, job_id)
    if job is None:
        raise not_found("Trabajo inexistente.")

    frames = list(
        database.scalars(
            select(SyntheticFrame)
            .where(SyntheticFrame.job_id == job_id)
            .order_by(SyntheticFrame.frame_index)
        )
    )
    observations = list(
        database.scalars(
            select(Observation)
            .where(Observation.job_id == job_id)
            .join(SyntheticFrame, Observation.frame_id == SyntheticFrame.id)
            .order_by(SyntheticFrame.frame_index, Observation.id)
        )
    )
    events = list(
        database.scalars(
            select(Event)
            .where(Event.job_id == job_id)
            .order_by(Event.video_timestamp_seconds, Event.id)
        )
    )
    response_job = JobResponse.model_validate(job)
    return JobTraceResponse(
        job=response_job,
        transitions=response_job.transitions,
        frames=frames,
        observations=observations,
        events=events,
    )


def get_job_record(database: DatabaseSession, job_id: uuid.UUID) -> ProcessingJob | None:
    return database.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .options(selectinload(ProcessingJob.transitions))
    )


@router.websocket("/ws/jobs/{job_id}/preview")
async def preview_job(websocket: WebSocket, job_id: uuid.UUID) -> None:
    factory = websocket.app.state.session_factory
    with factory() as database:
        job = database.get(ProcessingJob, job_id)
        if job is None:
            await websocket.close(code=4404)
            return
        session_id = job.session_id
        job_status = job.status

    await websocket.accept()
    if job_status in {JobStatus.COMPLETED, JobStatus.FAILED}:
        await websocket.send_json(
            {
                "type": "job.terminal",
                "schema_version": "1",
                "session_id": str(session_id),
                "job_id": str(job_id),
                "status": job_status.value,
            }
        )
        return
    preview_path = (
        Path(__file__).resolve().parents[4] / "fixtures" / "synthetic" / "preview-320x180.jpg"
    )
    image_base64 = load_preview_base64(preview_path)
    last_frame_index = -1
    try:
        while True:
            with factory() as database:
                job = database.get(ProcessingJob, job_id)
                frame = database.scalar(
                    select(SyntheticFrame)
                    .where(SyntheticFrame.job_id == job_id)
                    .order_by(SyntheticFrame.frame_index.desc())
                    .limit(1)
                )
            if frame is not None and frame.frame_index > last_frame_index:
                last_frame_index = frame.frame_index
                await websocket.send_json(
                    {
                        "type": "preview.update",
                        "schema_version": "1",
                        "session_id": str(session_id),
                        "job_id": str(job_id),
                        "frame_index": frame.frame_index,
                        "video_timestamp_seconds": float(frame.video_timestamp_seconds),
                        "progress_percent": min(99.0, float((frame.frame_index + 1) * 10)),
                        "image_media_type": "image/jpeg",
                        "image_base64": image_base64,
                    }
                )
            if job is not None and job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                await websocket.send_json(
                    {
                        "type": "job.terminal",
                        "schema_version": "1",
                        "session_id": str(session_id),
                        "job_id": str(job_id),
                        "status": job.status.value,
                    }
                )
                break
            await asyncio.sleep(1 / websocket.app.state.settings.preview_max_fps)
    except WebSocketDisconnect:
        pass
