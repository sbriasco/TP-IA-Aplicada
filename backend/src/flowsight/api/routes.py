"""REST endpoints for cameras, sessions, videos and jobs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import selectinload, undefer
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from flowsight.api.errors import api_error
from flowsight.api.schemas import (
    AnalysisMeasureResponse,
    CameraCreate,
    CameraResponse,
    ChatFigure,
    ChatRequest,
    ChatResponse,
    JobCreate,
    JobResponse,
    JobTraceResponse,
    MetricValueResponse,
    PositionSampleResponse,
    PositionSamplesResponse,
    ProcessedSessionResponse,
    ReferenceFrameResponse,
    SceneEventResponse,
    SceneIssueResponse,
    SceneVersionCreate,
    SceneVersionCreatedResponse,
    SceneVersionResponse,
    SceneVersionSummary,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    ShopMetricsResponse,
    TrafficBucketResponse,
    TrimmedName,
    VideoSourceResponse,
)
from flowsight.core.config import Settings
from flowsight.db.models import (
    Camera,
    Event,
    JobKind,
    JobStatus,
    Observation,
    ProcessingJob,
    ReferenceFrame,
    Session,
    SourceKind,
    SyntheticFrame,
    VideoSource,
)
from flowsight.preview.image import load_preview_base64
from flowsight.preview.snapshot import read_preview_snapshot, snapshot_path
from flowsight.services.cameras import (
    CameraExists,
    create_camera,
    get_or_create_camera,
    list_cameras,
)
from flowsight.services.chat import ChatAnswer, SessionMissing, ask
from flowsight.services.jobs import (
    InvalidJobTransition,
    JobRequestError,
    create_job_for_session,
    transition_job,
)
from flowsight.services.measures import list_measures
from flowsight.services.position_samples import JobNotFound, list_position_samples
from flowsight.services.processed_sessions import list_processed_sessions
from flowsight.services.scene_metrics import (
    ResultIncomplete,
    ShopNotInSession,
    load_events,
    load_shop_metrics,
)
from flowsight.services.scenes import (
    InvalidSceneConfiguration,
    SceneError,
    create_scene_version,
    get_scene_version,
    list_scene_versions,
)
from flowsight.services.video_sessions import (
    VideoSessionError,
    find_duplicate_session_ids,
    register_video_session,
    relink_video,
)
from flowsight.video.probe import VideoRejected
from flowsight.video.storage import StorageError, check_availability

router = APIRouter()

REFERENCE_FRAME_CACHE_CONTROL = "private, max-age=86400, immutable"


def get_database_session(request: Request):
    with request.app.state.session_factory() as database_session:
        yield database_session


Database = Annotated[DatabaseSession, Depends(get_database_session)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def not_found(message: str) -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "not_found", message)


@router.get("/cameras", response_model=list[CameraResponse])
def get_cameras(database: Database) -> list[Camera]:
    return list_cameras(database)


@router.post("/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def post_camera(payload: CameraCreate, database: Database) -> Camera:
    try:
        camera = create_camera(database, payload.name)
    except CameraExists as error:
        database.rollback()
        existing = CameraResponse.model_validate(database.get(Camera, error.existing_id))
        raise api_error(
            status.HTTP_409_CONFLICT,
            "camera_exists",
            "Ya existe una cámara con ese nombre. Elegí la existente o usá otro nombre.",
            existing_camera=existing.model_dump(mode="json"),
        ) from None
    database.commit()
    database.refresh(camera)
    return camera


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    database: Database, registered_camera_id: uuid.UUID | None = None
) -> list[Session]:
    query = select(Session).options(selectinload(Session.camera))
    if registered_camera_id is not None:
        query = query.where(Session.registered_camera_id == registered_camera_id)
    return list(database.scalars(query.order_by(Session.created_at.desc(), Session.id.desc())))


@router.get("/processed-sessions", response_model=list[ProcessedSessionResponse])
def get_processed_sessions(request: Request, database: Database) -> list[ProcessedSessionResponse]:
    rows = list_processed_sessions(database, request.app.state.settings)
    return [ProcessedSessionResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/sessions", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, request: Request, database: Database) -> SessionDetail:
    camera_id = payload.camera_id.strip()
    flow_session = Session(
        name=payload.name.strip(),
        camera_id=camera_id,
        registered_camera_id=get_or_create_camera(database, camera_id).id,
        source_kind=SourceKind.SYNTHETIC,
    )
    database.add(flow_session)
    database.commit()
    return session_detail(database, request.app.state.settings, flow_session.id)


@router.post("/video-sessions", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
async def register_video(
    request: Request,
    database: Database,
    name: Annotated[TrimmedName, Query()],
    registered_camera_id: uuid.UUID,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> SessionDetail:
    settings = request.app.state.settings
    try:
        session_id = await register_video_session(
            database, settings, name, registered_camera_id, filename, request.stream()
        )
    except (StorageError, VideoRejected, VideoSessionError) as error:
        raise video_error(error) from None
    # The first availability check hashes the new file: keep it off the event loop.
    return await run_in_threadpool(session_detail, database, settings, session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: uuid.UUID, request: Request, database: Database) -> SessionDetail:
    return session_detail(database, request.app.state.settings, session_id)


@router.get(
    "/sessions/{session_id}/shops/{shop_id}/metrics",
    response_model=ShopMetricsResponse,
)
def get_shop_metrics(
    session_id: uuid.UUID, shop_id: uuid.UUID, database: Database
) -> ShopMetricsResponse:
    if database.get(Session, session_id) is None:
        raise not_found("La sesión no existe.")
    try:
        rows, flow, peak = load_shop_metrics(database, session_id, shop_id)
    except ResultIncomplete:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "result_incomplete",
            "No hay un análisis completado para consultar.",
        ) from None
    except ShopNotInSession:
        raise not_found("El local no pertenece a esta sesión.") from None
    return ShopMetricsResponse(
        session_id=session_id,
        shop_id=shop_id,
        metrics=[MetricValueResponse.model_validate(row) for row in rows],
        flow=[TrafficBucketResponse.model_validate(bucket) for bucket in flow],
        peak=TrafficBucketResponse.model_validate(peak),
    )


@router.post("/chat", response_model=ChatResponse)
def post_chat(payload: ChatRequest, request: Request, database: Database) -> ChatResponse:
    if not payload.question.strip():
        raise api_error(status.HTTP_400_BAD_REQUEST, "empty_question", "La pregunta está vacía.")
    try:
        answer = ask(
            database,
            session_id=payload.session_id,
            shop_id=payload.shop_id,
            question=payload.question.strip(),
            timeout_seconds=request.app.state.settings.chat_timeout_seconds,
            settings=request.app.state.settings,
            drafter=getattr(request.app.state, "chat_drafter", None),
        )
    except SessionMissing:
        raise not_found("La sesión no existe.") from None
    except ShopNotInSession:
        raise not_found("El local no pertenece a esta sesión.") from None
    return _chat_response(answer)


def _chat_response(answer: ChatAnswer) -> ChatResponse:
    return ChatResponse(
        status=answer.status,
        message=answer.message,
        session_id=answer.session_id,
        shop_id=answer.shop_id,
        shop_name=answer.shop_name,
        scope=answer.scope,
        figures=[
            ChatFigure(
                code=figure.code,
                label=figure.label,
                availability=figure.availability,
                value=None if figure.value is None else float(figure.value),
                unavailable_reason=figure.unavailable_reason,
                start_seconds=None if figure.start_seconds is None else float(figure.start_seconds),
                track_count=figure.track_count,
                bucket_index=figure.bucket_index,
            )
            for figure in answer.figures
        ],
        model_calls=answer.model_calls,
    )


@router.get("/sessions/{session_id}/events", response_model=list[SceneEventResponse])
def get_session_events(
    session_id: uuid.UUID,
    database: Database,
    shop_id: uuid.UUID | None = None,
    from_seconds: Annotated[Decimal | None, Query(ge=0)] = None,
    to_seconds: Annotated[Decimal | None, Query(ge=0)] = None,
) -> list[SceneEventResponse]:
    if database.get(Session, session_id) is None:
        raise not_found("La sesión no existe.")
    try:
        events = load_events(
            database,
            session_id,
            shop_id=shop_id,
            from_seconds=from_seconds,
            to_seconds=to_seconds,
        )
    except ResultIncomplete:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "result_incomplete",
            "No hay un análisis completado para consultar.",
        ) from None
    except ShopNotInSession:
        raise not_found("El local no pertenece a esta sesión.") from None
    return [
        SceneEventResponse(
            kind=event.kind.value,
            zone_role=None if event.zone_role is None else event.zone_role.value,
            track_id=event.track_id,
            shop_id=event.shop_id,
            video_timestamp_seconds=event.video_timestamp_seconds,
            duration_seconds=event.duration_seconds,
        )
        for event in events
    ]


@router.put("/sessions/{session_id}/video", response_model=SessionDetail)
async def relink_session_video(
    session_id: uuid.UUID, request: Request, database: Database
) -> SessionDetail:
    settings = request.app.state.settings
    try:
        await relink_video(database, settings, session_id, request.stream())
    except (StorageError, VideoSessionError) as error:
        raise video_error(error) from None
    return await run_in_threadpool(session_detail, database, settings, session_id)


@router.get("/sessions/{session_id}/reference-frame")
def get_reference_frame(session_id: uuid.UUID, database: Database) -> Response:
    frame = database.scalar(
        select(ReferenceFrame)
        .where(ReferenceFrame.session_id == session_id)
        .options(undefer(ReferenceFrame.image))
    )
    if frame is None:
        raise not_found("La sesión no existe o no tiene frame de referencia.")
    return Response(
        content=frame.image,
        media_type=frame.media_type,
        headers={"Cache-Control": REFERENCE_FRAME_CACHE_CONTROL},
    )


def session_detail(
    database: DatabaseSession, settings: Settings, session_id: uuid.UUID
) -> SessionDetail:
    flow_session = database.scalar(
        select(Session).where(Session.id == session_id).options(selectinload(Session.camera))
    )
    if flow_session is None:
        raise not_found("Sesión inexistente.")
    source = database.get(VideoSource, session_id)
    frame = database.get(ReferenceFrame, session_id)

    video = None
    duplicates: list[uuid.UUID] = []
    if source is not None:
        fields = {
            field: getattr(source, field)
            for field in VideoSourceResponse.model_fields
            if field != "availability"
        }
        availability = check_availability(
            settings.videos_dir, source.relative_path, source.size_bytes, source.sha256
        )
        video = VideoSourceResponse(**fields, availability=availability)
        duplicates = find_duplicate_session_ids(database, source.sha256, session_id)

    return SessionDetail(
        id=flow_session.id,
        name=flow_session.name,
        source_kind=flow_session.source_kind,
        camera=CameraResponse.model_validate(flow_session.camera),
        created_at=flow_session.created_at,
        camera_id=flow_session.camera_id,
        video=video,
        reference_frame=None if frame is None else ReferenceFrameResponse.model_validate(frame),
        duplicate_session_ids=duplicates,
    )


# Status and suggested action for every video error code (contracts/video-registration.md).
_VIDEO_ERRORS: dict[str, tuple[int, str, str]] = {
    "camera_not_found": (404, "not_found", "Cámara inexistente. Elegí una cámara registrada."),
    "session_not_found": (404, "not_found", "Sesión inexistente."),
    "hash_mismatch": (
        409,
        "hash_mismatch",
        "El archivo no es el que se registró. Elegí el mismo archivo que se registró "
        "originalmente.",
    ),
    "not_video_session": (
        409,
        "not_video_session",
        "La sesión no tiene un video asociado; es una sesión sintética.",
    ),
    "file_empty": (422, "file_empty", "El archivo está vacío. Elegí un archivo con contenido."),
    "unsupported_format": (
        422,
        "unsupported_format",
        "Formato de video no admitido. Convertilo a MP4 o MPEG.",
    ),
    "no_decodable_frames": (
        422,
        "no_decodable_frames",
        "No se pudo decodificar ningún frame. Verificá el archivo con un reproductor.",
    ),
    "fps_unknown": (
        422,
        "fps_unknown",
        "No se pudo determinar el fps. Volvé a codificar el video con fps fijo.",
    ),
    "upload_interrupted": (
        422,
        "upload_interrupted",
        "La subida se interrumpió. Volvé a intentar.",
    ),
    "videos_dir_not_configured": (
        503,
        "videos_dir_not_configured",
        "Falta FLOWSIGHT_VIDEOS_DIR. Definila en .env (ver .env.example).",
    ),
    "videos_dir_not_writable": (
        503,
        "videos_dir_not_writable",
        "La carpeta de videos no existe o no se puede escribir. Creala o revisá sus permisos.",
    ),
    "machine_id_not_configured": (
        503,
        "machine_id_not_configured",
        "Falta FLOWSIGHT_MACHINE_ID o es inválido. Definilo en .env (ver .env.example).",
    ),
    "insufficient_storage": (
        507,
        "insufficient_storage",
        "No hay espacio en la carpeta de videos. Liberá espacio y volvé a intentar.",
    ),
}


def video_error(error: StorageError | VideoRejected | VideoSessionError) -> HTTPException:
    status_code, code, message = _VIDEO_ERRORS[error.code]
    return api_error(status_code, code, message)


# Status and message for every scene error code.
_SCENE_ERRORS: dict[str, tuple[int, str, str]] = {
    "camera_not_found": (404, "not_found", "Cámara inexistente."),
}


def scene_error(error: SceneError) -> HTTPException:
    status_code, code, message = _SCENE_ERRORS[error.code]
    return api_error(status_code, code, message)


# Status and message for every job request error code (FR-025 to FR-028).
_JOB_ERRORS: dict[str, tuple[int, str]] = {
    "job_kind_mismatch": (
        422,
        "El tipo de trabajo no corresponde a la sesión: las sesiones sintéticas usan "
        "synthetic_base_flow y las de video, video_analysis.",
    ),
    "scene_version_not_allowed": (
        422,
        "Las sesiones sintéticas no usan una versión de escena. Quitá scene_version_id.",
    ),
    "scene_not_configured": (
        409,
        "La cámara no tiene ninguna configuración de escena. Creá una en el editor antes "
        "de iniciar el análisis.",
    ),
    "scene_version_required": (
        422,
        "Elegí una versión de escena de la cámara para iniciar el análisis.",
    ),
    "scene_version_other_camera": (
        422,
        "La versión de escena elegida no existe o es de otra cámara. Elegí una versión de "
        "la cámara de la sesión.",
    ),
    "aspect_ratio_mismatch": (
        409,
        "La relación de aspecto del video difiere de la del frame de la versión elegida. "
        "Creá una versión nueva sobre el frame de esta sesión.",
    ),
}


@router.get("/cameras/{camera_id}/scene-versions", response_model=list[SceneVersionSummary])
def get_scene_versions(camera_id: uuid.UUID, database: Database) -> list[SceneVersionSummary]:
    try:
        rows = list_scene_versions(database, camera_id)
    except SceneError as error:
        raise scene_error(error) from None
    return [SceneVersionSummary.model_validate(row) for row in rows]


@router.post(
    "/cameras/{camera_id}/scene-versions",
    response_model=SceneVersionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_scene_version(
    camera_id: uuid.UUID, payload: SceneVersionCreate, request: Request, database: Database
) -> SceneVersionCreatedResponse:
    try:
        created = create_scene_version(
            database,
            request.app.state.settings,
            camera_id,
            reference_session_id=payload.reference_session_id,
            base_version_id=payload.base_version_id,
            shops=payload.model_dump()["shops"],
        )
    except SceneError as error:
        database.rollback()
        raise scene_error(error) from None
    except InvalidSceneConfiguration as error:
        database.rollback()
        raise api_error(
            422,
            "invalid_scene_configuration",
            "La configuración de la escena tiene errores. Corregilos y volvé a guardar.",
            errors=[
                SceneIssueResponse.model_validate(issue).model_dump(mode="json")
                for issue in error.errors
            ],
        ) from None
    database.commit()
    version = SceneVersionResponse.model_validate(get_scene_version(database, created.id))
    return SceneVersionCreatedResponse(
        **version.model_dump(),
        warnings=[SceneIssueResponse.model_validate(issue) for issue in created.warnings],
    )


@router.get("/scene-versions/{scene_version_id}", response_model=SceneVersionResponse)
def get_scene_version_detail(
    scene_version_id: uuid.UUID, database: Database
) -> SceneVersionResponse:
    version = get_scene_version(database, scene_version_id)
    if version is None:
        raise not_found("Versión de escena inexistente.")
    return SceneVersionResponse.model_validate(version)


@router.post(
    "/sessions/{session_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(session_id: uuid.UUID, payload: JobCreate, database: Database) -> ProcessingJob:
    flow_session = database.get(Session, session_id)
    if flow_session is None:
        raise not_found("Sesión inexistente.")

    try:
        job = create_job_for_session(database, flow_session, payload.kind, payload.scene_version_id)
    except JobRequestError as error:
        database.rollback()
        status_code, message = _JOB_ERRORS[error.code]
        raise api_error(status_code, error.code, message, **error.extra) from None
    database.commit()
    return get_job_record(database, job.id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, database: Database) -> ProcessingJob:
    job = get_job_record(database, job_id)
    if job is None:
        raise not_found("Trabajo inexistente.")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: uuid.UUID, database: Database) -> ProcessingJob:
    if database.get(ProcessingJob, job_id) is None:
        raise not_found("Trabajo inexistente.")
    try:
        transition_job(
            database,
            job_id=job_id,
            target=JobStatus.CANCELLED,
            occurred_at=datetime.now(UTC),
            reason_code="operator_cancelled",
        )
    except InvalidJobTransition:
        database.rollback()
        raise api_error(
            status.HTTP_409_CONFLICT,
            "invalid_job_transition",
            "El trabajo ya no se puede cancelar.",
        ) from None
    database.commit()
    stored = get_job_record(database, job_id)
    if stored is None:
        raise not_found("Trabajo inexistente.")
    return stored


@router.get("/jobs/{job_id}/position-samples", response_model=PositionSamplesResponse)
def get_position_samples(
    job_id: uuid.UUID, request: Request, database: Database
) -> PositionSamplesResponse:
    try:
        sample_set = list_position_samples(database, request.app.state.settings, job_id)
    except JobNotFound:
        raise not_found("El análisis no existe.") from None
    return PositionSamplesResponse(
        job_id=sample_set.job_id,
        availability=sample_set.availability,
        samples=[
            PositionSampleResponse(
                video_timestamp_seconds=sample.video_timestamp_seconds, foot=sample.foot
            )
            for sample in sample_set.samples
        ],
    )


@router.get("/jobs/{job_id}/measures", response_model=list[AnalysisMeasureResponse])
def get_job_measures(job_id: uuid.UUID, database: Database) -> list[AnalysisMeasureResponse]:
    job = database.get(ProcessingJob, job_id)
    if job is None:
        raise not_found("Trabajo inexistente.")
    return [AnalysisMeasureResponse.model_validate(row) for row in list_measures(database, job)]


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


_TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


def _terminal_message(
    session_id: uuid.UUID, job_id: uuid.UUID, status: JobStatus
) -> dict[str, str]:
    return {
        "type": "job.terminal",
        "schema_version": "1",
        "session_id": str(session_id),
        "job_id": str(job_id),
        "status": status.value,
    }


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
        job_kind = job.kind

    await websocket.accept()
    if job_status in _TERMINAL_STATUSES:
        await websocket.send_json(_terminal_message(session_id, job_id, job_status))
        return
    if job_kind is JobKind.VIDEO_ANALYSIS:
        await _preview_video_analysis(websocket, job_id, session_id)
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
            if job is not None and job.status in _TERMINAL_STATUSES:
                await websocket.send_json(_terminal_message(session_id, job_id, job.status))
                break
            await asyncio.sleep(1 / websocket.app.state.settings.preview_max_fps)
    except WebSocketDisconnect:
        pass


async def _preview_video_analysis(
    websocket: WebSocket, job_id: uuid.UUID, session_id: uuid.UUID
) -> None:
    """Subscribe to the broker. The worker writes the latest frame; this loop publishes it.

    Publishing replaces the single pending update, so a slow client does not
    make the worker wait. Disconnecting drops only this subscription.
    """

    factory = websocket.app.state.session_factory
    broker = websocket.app.state.preview_broker
    subscription = broker.subscribe(job_id)
    videos_dir = websocket.app.state.settings.videos_dir
    path = None if videos_dir is None else snapshot_path(videos_dir, session_id, job_id)
    last_frame_index = -1
    interval = 1 / websocket.app.state.settings.preview_max_fps
    try:
        while True:
            if path is not None:
                snapshot = read_preview_snapshot(path)
                if snapshot is not None and snapshot.frame_index > last_frame_index:
                    last_frame_index = snapshot.frame_index
                    broker.publish(snapshot)
            try:
                message = await asyncio.wait_for(subscription.receive(), timeout=interval)
            except TimeoutError:
                message = None
            if message is not None:
                await websocket.send_json(message)
                if message["type"] == "job.terminal":
                    break
            with factory() as database:
                job = database.get(ProcessingJob, job_id)
            if job is not None and job.status in _TERMINAL_STATUSES:
                broker.finish(session_id, job_id, job.status.value)
                if message is None or message["type"] != "job.terminal":
                    message = await subscription.receive()
                    await websocket.send_json(message)
                    if message["type"] != "job.terminal":
                        await websocket.send_json(await subscription.receive())
                break
    except WebSocketDisconnect:
        pass
    finally:
        broker.unsubscribe(job_id, subscription)
