"""Webcam preparation and lifecycle controls with no frame recording."""

from __future__ import annotations

import asyncio
import base64
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from flowsight.api.errors import api_error
from flowsight.api.live_schemas import LiveResume, LiveSessionCreate, LiveStart
from flowsight.api.routes import job_response, session_detail
from flowsight.capture.contracts import CaptureError
from flowsight.capture.devices import list_webcams
from flowsight.db.models import Camera, LiveAnalysisState, LiveSource, WorkerMachine
from flowsight.services.live_jobs import (
    LiveMachineError,
    release_reservation,
    request_live_continue,
    request_live_pause,
    request_live_resume,
    request_live_retry,
    request_live_stop,
    reserve_machine,
    start_live_job,
)
from flowsight.services.live_results import load_live_events, load_live_results
from flowsight.services.live_sessions import prepare_session
from flowsight.services.sessions import get_active_session

router = APIRouter()

_MESSAGES = {
    "not_found": "La sesión, cámara o trabajo no está disponible.",
    "live_not_configured": "No se pudo iniciar la conexión local de webcam. Reiniciá la app.",
    "worker_unavailable": "El worker local no está disponible.",
    "machine_busy": "El equipo está analizando o comprobando otra fuente.",
    "device_unavailable": "No se pudo abrir la webcam. Revisá su conexión y permisos.",
    "device_enumeration_failed": (
        "No se pudieron detectar las webcams. Volvé a actualizar la lista."
    ),
    "device_enumeration_unsupported": "La lista automática de webcams está disponible en Windows.",
    "capture_open_timeout": "La webcam no respondió dentro del tiempo previsto.",
    "camera_removed": "La cámara lógica fue retirada.",
    "scene_version_removed": "La configuración fue retirada.",
    "scene_version_other_camera": "Elegí una configuración de esta cámara.",
    "aspect_ratio_mismatch": "Las dimensiones no son compatibles con la configuración.",
    "encuadre_confirmation_required": "Comprobá y confirmá el encuadre actual.",
    "check_expired": "La comprobación venció. Comprobá el encuadre nuevamente.",
    "live_already_started": "Esta sesión ya tiene un análisis. Prepará otra sesión.",
    "database_unavailable": "La base de datos local no está disponible.",
    "live_not_interrupted": "Solo se puede reintentar una captura interrumpida.",
    "live_stopping": "El análisis está terminando o ya terminó.",
}


def live_error(error):
    code = error.code
    status = (
        404
        if code == "not_found"
        else 504
        if code == "capture_open_timeout"
        else 503
        if code
        in {
            "worker_unavailable",
            "live_not_configured",
            "device_unavailable",
            "database_unavailable",
            "device_enumeration_failed",
            "device_enumeration_unsupported",
        }
        else 409
    )
    return api_error(status, code, _MESSAGES.get(code, "No se pudo completar la operación."))


def machine_id(request: Request) -> str:
    settings = request.app.state.settings
    if not settings.machine_id or settings.live_channel_token is None:
        raise LiveMachineError("live_not_configured")
    return settings.machine_id


async def probe(request: Request, device_index: int):
    factory = request.app.state.session_factory
    owner = machine_id(request)
    channel = request.app.state.live_channel
    if not channel.available:
        raise LiveMachineError("worker_unavailable")
    with factory.begin() as database:
        reservation = reserve_machine(database, owner, datetime.now(UTC))
        epoch = database.get(WorkerMachine, owner).owner_epoch
    try:
        result = await asyncio.wait_for(
            channel.probe(
                machine_id=owner,
                owner_epoch=epoch,
                reservation_id=reservation,
                device_index=device_index,
            ),
            timeout=5,
        )
        if result.device_index != device_index:
            raise CaptureError("device_unavailable")
        return result, epoch
    except TimeoutError:
        raise CaptureError("capture_open_timeout") from None
    finally:
        with factory.begin() as database:
            release_reservation(database, owner, reservation)


@router.get("/live/devices")
def devices(request: Request):
    try:
        owner = machine_id(request)
        with request.app.state.session_factory() as database:
            row = database.get(WorkerMachine, owner)
            available = bool(
                row
                and (datetime.now(UTC) - row.heartbeat_at).total_seconds() < 5
                and request.app.state.live_channel.available
            )
        settings = request.app.state.settings
        candidates = (
            [{"device_index": 0, "label": "Webcam simulada (prueba)", "verified": False}]
            if settings.environment == "test" and settings.live_capture_source == "fake"
            else list_webcams()
        )
        return {
            "machine_id": owner,
            "worker_available": available,
            "candidates": candidates,
        }
    except (LiveMachineError, CaptureError) as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/live/sessions", status_code=201)
async def prepare(payload: LiveSessionCreate, request: Request):
    try:
        owner = machine_id(request)
        with request.app.state.session_factory() as database:
            camera = database.get(Camera, payload.registered_camera_id)
            if camera is None:
                raise LiveMachineError("not_found")
            if camera.deleted_at is not None:
                raise LiveMachineError("camera_removed")
        result, _ = await probe(request, payload.device_index)
        with request.app.state.session_factory.begin() as database:
            session = prepare_session(
                database,
                name=payload.name,
                camera_id=payload.registered_camera_id,
                machine_id=owner,
                label_mode=payload.label_mode,
                probe=result,
                now=datetime.now(UTC),
            )
            session_id = session.id
        with request.app.state.session_factory() as database:
            return session_detail(database, request.app.state.settings, session_id)
    except (LiveMachineError, CaptureError) as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/sessions/{session_id}/live/check")
async def check(session_id: uuid.UUID, request: Request):
    try:
        owner = machine_id(request)
        with request.app.state.session_factory() as database:
            source = database.get(LiveSource, session_id)
            if source is None or get_active_session(database, session_id) is None:
                raise LiveMachineError("not_found")
            if source.machine_id != owner:
                raise LiveMachineError("live_not_configured")
            device_index = source.device_index
        result, epoch = await probe(request, device_index)
        token = request.app.state.live_checks.issue(
            session_id=session_id,
            machine_id=owner,
            owner_epoch=epoch,
            device_index=device_index,
            width=result.width,
            height=result.height,
        )
        return {
            "image_base64": base64.b64encode(result.jpeg).decode(),
            "image_media_type": "image/jpeg",
            "width": result.width,
            "height": result.height,
            "backend": result.backend,
            "check_token": token,
            "expires_in_seconds": 60,
        }
    except (LiveMachineError, CaptureError) as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/sessions/{session_id}/live/start", status_code=201)
def start(session_id: uuid.UUID, payload: LiveStart, request: Request):
    try:
        with request.app.state.session_factory.begin() as database:
            job = start_live_job(
                database,
                session_id=session_id,
                machine_id=machine_id(request),
                scene_version_id=payload.scene_version_id,
                checks=request.app.state.live_checks,
                check_token=payload.check_token,
                frame_confirmed=payload.frame_confirmed,
                now=datetime.now(UTC),
            )
            data = job_response(database, job)
        request.app.state.live_checks.consume(payload.check_token)
        return data
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/jobs/{job_id}/live/stop", status_code=202)
def stop(job_id: uuid.UUID, request: Request, response: Response):
    try:
        with request.app.state.session_factory.begin() as database:
            job = request_live_stop(database, job_id, datetime.now(UTC))
            state = database.get(LiveAnalysisState, job_id)
            if job.status.value not in ("pending", "processing"):
                response.status_code = 200
            return {
                "job_id": str(job_id),
                "status": job.status.value,
                "stop_requested_at": state.stop_requested_at,
            }
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.get("/jobs/{job_id}/live-results")
def results(
    job_id: uuid.UUID,
    request: Request,
    response: Response,
    shop_id: uuid.UUID | None = None,
    bucket_cursor: Annotated[int | None, Query(ge=0)] = None,
):
    response.headers["Cache-Control"] = "no-store"
    try:
        with request.app.state.session_factory() as database:
            return load_live_results(database, job_id, shop_id=shop_id, bucket_cursor=bucket_cursor)
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/jobs/{job_id}/live/retry", status_code=202)
def retry(job_id: uuid.UUID, request: Request):
    try:
        with request.app.state.session_factory.begin() as database:
            request_live_retry(database, job_id, datetime.now(UTC), machine_id=machine_id(request))
            state = database.get(LiveAnalysisState, job_id)
            data = {"job_id": str(job_id), "retry_requested_at": state.retry_requested_at}
            # Hold the job lock while invalidating the old probe. Producer ingress
            # takes that same lock before issuing the next check, so it cannot
            # publish a fresh nonce between commit and this invalidation.
            request.app.state.live_checks.expire_job(job_id)
        return data
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/jobs/{job_id}/live/pause", status_code=202)
def pause(job_id: uuid.UUID, request: Request):
    try:
        with request.app.state.session_factory.begin() as database:
            request_live_pause(database, job_id, datetime.now(UTC), machine_id=machine_id(request))
        return {"job_id": str(job_id), "pause_requested": True}
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/jobs/{job_id}/live/continue", status_code=202)
def continue_capture(job_id: uuid.UUID, request: Request):
    try:
        with request.app.state.session_factory.begin() as database:
            request_live_continue(
                database, job_id, datetime.now(UTC), machine_id=machine_id(request)
            )
        return {"job_id": str(job_id), "resume_requested": True}
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.post("/jobs/{job_id}/live/confirm-resume", status_code=202)
def confirm_resume(job_id: uuid.UUID, payload: LiveResume, request: Request):
    try:
        with request.app.state.session_factory.begin() as database:
            request_live_resume(
                database,
                job_id,
                datetime.now(UTC),
                machine_id=machine_id(request),
                checks=request.app.state.live_checks,
                check_token=payload.check_token,
                frame_confirmed=payload.frame_confirmed,
            )
        request.app.state.live_checks.consume(payload.check_token)
        return {"job_id": str(job_id), "resume_requested": True}
    except LiveMachineError as error:
        raise live_error(error) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None


@router.get("/jobs/{job_id}/live-events")
def events(
    job_id: uuid.UUID,
    request: Request,
    response: Response,
    shop_id: uuid.UUID | None = None,
    from_seconds: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    to_seconds: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
):
    response.headers["Cache-Control"] = "no-store"
    if from_seconds is not None and to_seconds is not None and to_seconds < from_seconds:
        raise api_error(422, "validation_error", "El intervalo temporal no es válido.")
    try:
        with request.app.state.session_factory() as database:
            return load_live_events(
                database,
                job_id,
                shop_id=shop_id,
                from_seconds=from_seconds,
                to_seconds=to_seconds,
                cursor=cursor,
                limit=limit,
            )
    except LiveMachineError as error:
        raise live_error(error) from None
    except ValueError:
        raise api_error(
            422, "validation_error", "El cursor no corresponde a esta consulta."
        ) from None
    except SQLAlchemyError:
        raise live_error(LiveMachineError("database_unavailable")) from None
