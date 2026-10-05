"""Prepared webcam metadata and short-lived, single-use frame confirmations."""

from __future__ import annotations

import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.capture.contracts import CaptureProbeResult
from flowsight.db.models import Camera, LiveSource, ReferenceFrame, Session, SourceKind
from flowsight.services.live_jobs import LiveMachineError


@dataclass(frozen=True)
class FrameCheck:
    session_id: uuid.UUID
    machine_id: str
    owner_epoch: uuid.UUID
    device_index: int
    width: int
    height: int
    expires_at: float
    job_id: uuid.UUID | None = None
    segment_index: int | None = None


class LiveChecks:
    """Bounded RAM only; restarting the API requires checking the frame again."""

    def __init__(self, capacity: int = 8) -> None:
        self.capacity = capacity
        self._checks: dict[str, FrameCheck] = {}
        self._lock = threading.RLock()

    def issue(self, **fields) -> str:
        with self._lock:
            now = time.monotonic()
            self._checks = {
                key: check for key, check in self._checks.items() if check.expires_at > now
            }
            if len(self._checks) >= self.capacity:
                raise LiveMachineError("machine_busy")
            token = secrets.token_urlsafe(32)
            self._checks[token] = FrameCheck(**fields, expires_at=now + 60)
            return token

    def require(
        self,
        token: str,
        *,
        session_id: uuid.UUID,
        machine_id: str,
        owner_epoch: uuid.UUID,
        device_index: int,
        job_id: uuid.UUID | None = None,
    ) -> FrameCheck:
        with self._lock:
            check = self._checks.get(token)
            if check is None or check.expires_at <= time.monotonic():
                self._checks.pop(token, None)
                raise LiveMachineError("check_expired")
            if (
                check.session_id,
                check.machine_id,
                check.owner_epoch,
                check.device_index,
                check.job_id,
            ) != (session_id, machine_id, owner_epoch, device_index, job_id):
                raise LiveMachineError("encuadre_confirmation_required")
            return check

    def consume(self, token: str) -> None:
        with self._lock:
            self._checks.pop(token, None)

    def expire(self, token: str) -> None:
        self.consume(token)

    def expire_job(self, job_id: uuid.UUID) -> None:
        with self._lock:
            self._checks = {
                token: check for token, check in self._checks.items() if check.job_id != job_id
            }


def prepare_session(
    database: DatabaseSession,
    *,
    name: str,
    camera_id: uuid.UUID,
    machine_id: str,
    label_mode: str,
    probe: CaptureProbeResult,
    now: datetime,
) -> Session:
    camera = database.scalar(
        select(Camera)
        .where(Camera.id == camera_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if camera is None:
        raise LiveMachineError("not_found")
    if camera.deleted_at is not None:
        raise LiveMachineError("camera_removed")
    session = Session(
        id=uuid.uuid4(),
        name=name,
        camera_id=str(camera.id),
        registered_camera_id=camera.id,
        source_kind=SourceKind.WEBCAM,
    )
    database.add(session)
    database.flush()
    database.add(
        LiveSource(
            session_id=session.id,
            machine_id=machine_id,
            device_index=probe.device_index,
            capture_backend=probe.backend,
            width=probe.width,
            height=probe.height,
            reported_fps=probe.reported_fps,
            label_mode=label_mode,
            prepared_at=now,
        )
    )
    database.add(
        ReferenceFrame(
            session_id=session.id,
            frame_index=0,
            video_timestamp_seconds=Decimal(0),
            width=probe.width,
            height=probe.height,
            media_type="image/jpeg",
            image=probe.jpeg,
        )
    )
    database.flush()
    return session
