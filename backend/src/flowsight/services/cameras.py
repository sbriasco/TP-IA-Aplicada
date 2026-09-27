"""Registered cameras, identified by their normalized name."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from flowsight.db.models import Camera


class CameraExists(ValueError):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__("Ya existe una cámara con ese nombre.")
        self.existing_id = existing_id


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


def _get_by_name(database_session: Session, name: str) -> Camera:
    return database_session.scalars(
        select(Camera).where(Camera.name_key == normalize_name_key(name))
    ).one()


def get_or_create_camera(database_session: Session, name: str) -> Camera:
    """Return the camera for `name`, creating it if needed; the caller commits."""

    _insert_if_absent(database_session, name)
    return _get_by_name(database_session, name)


def create_camera(database_session: Session, name: str) -> Camera:
    """Create a camera or raise `CameraExists` with the id of the one already registered."""

    if _insert_if_absent(database_session, name) is None:
        raise CameraExists(_get_by_name(database_session, name).id)
    return _get_by_name(database_session, name)


def list_cameras(database_session: Session) -> list[Camera]:
    return list(database_session.scalars(select(Camera).order_by(Camera.name, Camera.id)))
