"""Authenticated loopback-only producer ingress; browsers cannot publish frames."""

from __future__ import annotations

import ipaddress
import json
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from flowsight.db.models import (
    JobKind,
    JobStatus,
    LiveAnalysisState,
    LiveSource,
    ProcessingJob,
    WorkerMachine,
)
from flowsight.preview.live_messages import CaptureReconnectCheck, LiveUpdate
from flowsight.services.live_jobs import LiveMachineError

router = APIRouter()


def _authorized(websocket: WebSocket, machine_id: str):
    settings = websocket.app.state.settings
    token = settings.live_channel_token
    if token is None or settings.machine_id != machine_id or websocket.client is None:
        return None
    try:
        if not ipaddress.ip_address(websocket.client.host).is_loopback:
            return None
        owner_epoch = uuid.UUID(websocket.headers.get("x-flowsight-owner", ""))
    except ValueError:
        return None
    if not secrets.compare_digest(
        websocket.headers.get("authorization", ""), "Bearer " + token.get_secret_value()
    ):
        return None
    with websocket.app.state.session_factory() as database:
        machine = database.get(WorkerMachine, machine_id)
        if (
            machine is None
            or machine.owner_epoch != owner_epoch
            or (
                machine.worker_id != websocket.headers.get("x-flowsight-worker")
                or (datetime.now(UTC) - machine.heartbeat_at).total_seconds() >= 5
            )
        ):
            return None
    return owner_epoch


@router.websocket("/ws/internal/live/{machine_id}")
async def live_producer(websocket: WebSocket, machine_id: str):
    epoch = _authorized(websocket, machine_id)
    channel = websocket.app.state.live_channel
    if epoch is None or channel.available:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    channel.attach(websocket, machine_id, epoch)
    try:
        await websocket.send_json({"type": "producer.ready"})
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode()) > 1048576 or _authorized(websocket, machine_id) != epoch:
                await websocket.close(code=1008)
                return
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("Invalid message")
            if message.get("type") == "capture.probe.result":
                if message.get("backend") == "fake" and (
                    websocket.app.state.settings.environment != "test"
                ):
                    raise ValueError("Fake capture forbidden")
                channel.probe_result(message)
                continue
            if message.get("type") == "capture.reconnect-check":
                check = CaptureReconnectCheck.model_validate(message)
                if check.backend == "fake" and websocket.app.state.settings.environment != "test":
                    raise ValueError("Fake capture forbidden")
                with websocket.app.state.session_factory.begin() as database:
                    machine = database.scalar(
                        select(WorkerMachine)
                        .where(WorkerMachine.machine_id == machine_id)
                        .with_for_update()
                    )
                    if machine is None or machine.owner_epoch != epoch:
                        raise ValueError("Invalid owner")
                    job = database.scalar(
                        select(ProcessingJob)
                        .where(ProcessingJob.id == check.job_id)
                        .with_for_update()
                    )
                    state = database.get(LiveAnalysisState, check.job_id)
                    source = database.get(LiveSource, check.session_id)
                    if (
                        job is None
                        or state is None
                        or source is None
                        or (
                            job.kind != JobKind.LIVE_ANALYSIS
                            or job.status != JobStatus.PROCESSING
                            or job.target_machine_id != machine_id
                            or job.session_id != check.session_id
                            or job.claimed_by != websocket.headers.get("x-flowsight-worker")
                            or state.capture_status != "awaiting_confirmation"
                            or state.stop_requested_at is not None
                            or state.resume_confirmed_at is not None
                            or state.revision != check.revision
                            or state.current_segment_index + 1 != check.segment_index
                            or source.device_index != check.device_index
                        )
                    ):
                        raise ValueError("Invalid reconnect context")
                    checks = websocket.app.state.live_checks
                    checks.expire_job(check.job_id)
                    token = checks.issue(
                        session_id=check.session_id,
                        job_id=check.job_id,
                        machine_id=machine_id,
                        owner_epoch=epoch,
                        device_index=check.device_index,
                        segment_index=check.segment_index,
                        width=check.width,
                        height=check.height,
                    )
                neutral = check.model_dump(mode="json")
                neutral.update(
                    type="live.reconnect-check", check_token=token, expires_in_seconds=60
                )
                channel.broker.reconnect_check(check.job_id, neutral)
                continue
            update = LiveUpdate.model_validate(message)
            with websocket.app.state.session_factory() as database:
                job = database.get(ProcessingJob, update.job_id)
                if job is None or (
                    job.kind != JobKind.LIVE_ANALYSIS
                    or job.status != JobStatus.PROCESSING
                    or job.target_machine_id != machine_id
                    or job.session_id != update.session_id
                    or job.claimed_by != websocket.headers.get("x-flowsight-worker")
                ):
                    raise ValueError("Invalid job context")
            channel.broker.publish(update)
    except WebSocketDisconnect:
        pass
    except (ValueError, KeyError, ValidationError, LiveMachineError):
        await websocket.close(code=1008)
    finally:
        channel.detach(websocket)
