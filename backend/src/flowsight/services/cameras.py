"""Registered cameras, identified by their normalized name."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from flowsight.db.models import Camera, JobStatus, ProcessingJob
from flowsight.db.models import Session as FlowSession


class CameraExists(ValueError):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__("Ya existe una cámara con ese nombre.")
        self.existing_id = existing_id


class CameraNotFound(ValueError):
    pass


class CameraRemoved(ValueError):
    pass


class CameraHasActiveJobs(ValueError):
    pass


def normalize_name_key(name: str) -> str:
    """Key that makes `"Cam 01"`, `" cam 01 "` and `"CAM 01"` the same camera.

    Migration 0002 keeps a fixed copy of this function: change both or neither.
    """

    return name.strip().casefold()


def _insert_if_absent(database_session: Session, name: str) -> uuid.UUID | None:
    name = name.strip()
    return database_session.scalar(
        insert(Camera)
        .values(id=uuid.uuid4(), name=name, name_key=normalize_name_key(name))
        .on_conflict_do_nothing(index_elements=[Camera.name_key])
        .returning(Camera.id)
    )


def _get_by_name(database_session: Session, name: str) -> Camera | None:
    return database_session.scalars(
        select(Camera)
        .where(Camera.name_key == normalize_name_key(name))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()


def get_or_create_camera(database_session: Session, name: str) -> Camera:
    """Return the camera for `name`, creating it if needed; the caller commits."""

    while True:
        _insert_if_absent(database_session, name)
        camera = _get_by_name(database_session, name)
        if camera is None:
            # A concurrent rename can free this name after the insert's conflict check.
            continue
        if camera.deleted_at is not None:
            raise CameraRemoved
        return camera


def create_camera(database_session: Session, name: str) -> Camera:
    """Create a camera or raise `CameraExists` with the id of the one already registered."""

    while True:
        inserted = _insert_if_absent(database_session, name)
        camera = _get_by_name(database_session, name)
        if camera is None:
            continue
        if camera.deleted_at is not None:
            raise CameraRemoved
        if inserted is None:
            raise CameraExists(camera.id)
        return camera


def list_cameras(database_session: Session) -> list[Camera]:
    # By `name_key` so the order does not depend on the database collation.
    return list(
        database_session.scalars(
            select(Camera)
            .where(Camera.deleted_at.is_(None))
            .order_by(Camera.name_key, Camera.name, Camera.id)
        )
    )


def rename_camera(database: Session, camera_id: uuid.UUID, name: str) -> Camera:
    camera = database.scalar(
        select(Camera)
        .where(Camera.id == camera_id, Camera.deleted_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if camera is None:
        raise CameraNotFound
    key = normalize_name_key(name)
    existing = database.scalar(select(Camera).where(Camera.name_key == key, Camera.id != camera_id))
    if existing is not None:
        if existing.deleted_at is not None:
            raise CameraRemoved
        raise CameraExists(existing.id)
    try:
        with database.begin_nested():
            camera.name = name.strip()
            camera.name_key = key
            database.flush()
    except IntegrityError as error:
        if (
            getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            != "uq_cameras_name_key"
        ):
            raise
        existing = _get_by_name(database, name)
        if existing is None:
            return rename_camera(database, camera_id, name)
        if existing.deleted_at is not None:
            raise CameraRemoved from None
        raise CameraExists(existing.id) from None
    return camera


def remove_camera(database: Session, camera_id: uuid.UUID) -> None:
    """Logical removal; all session rows, files and scenes remain available."""
    camera = database.scalar(
        select(Camera)
        .where(Camera.id == camera_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if camera is None:
        raise CameraNotFound
    if camera.deleted_at is not None:
        return
    active_job = database.scalar(
        select(ProcessingJob.id)
        .join(FlowSession, ProcessingJob.session_id == FlowSession.id)
        .where(
            FlowSession.registered_camera_id == camera_id,
            ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
        )
        .limit(1)
    )
    if active_job is not None:
        raise CameraHasActiveJobs
    camera.deleted_at = datetime.now(UTC)
    database.flush()
