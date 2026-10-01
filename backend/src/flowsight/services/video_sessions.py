"""Register local videos as sessions and relink them on another machine.

Follows contracts/video-registration.md: nothing that can be rejected cheaply
waits for the upload, and a failure after the copy leaves no session, no row
and no file behind (SC-002).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import PureWindowsPath
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.core.config import Settings
from flowsight.db.models import Camera, ReferenceFrame, Session, SourceKind, VideoSource
from flowsight.services.sessions import get_active_session
from flowsight.video.probe import probe_video
from flowsight.video.storage import (
    discard,
    ensure_videos_dir,
    extension_for,
    finalize,
    stream_to_partial,
    video_path,
)

REFERENCE_MEDIA_TYPE = "image/jpeg"
# The MPEG program stream header does not carry a reliable frame count (R3).
UNRELIABLE_FRAME_COUNT_EXTENSIONS = frozenset({".mpg", ".mpeg"})

VideoSessionErrorCode = Literal[
    "camera_not_found",
    "session_not_found",
    "not_video_session",
    "hash_mismatch",
    "machine_id_not_configured",
]


class VideoSessionError(RuntimeError):
    """Registration or relink refused; `code` is translated by the API."""

    def __init__(self, code: VideoSessionErrorCode) -> None:
        super().__init__(code)
        self.code = code


async def register_video_session(
    database_session: DatabaseSession,
    settings: Settings,
    name: str,
    registered_camera_id: uuid.UUID,
    original_filename: str,
    chunks: AsyncIterator[bytes],
) -> uuid.UUID:
    """Copy, probe and persist a video session; return its id."""

    # 1. Cheap checks first: a bad extension never reads the body.
    extension = extension_for(original_filename)
    camera = database_session.get(Camera, registered_camera_id)
    if camera is None:
        raise VideoSessionError("camera_not_found")
    camera_name = camera.name
    # Do not hold a transaction open while the upload streams in.
    database_session.rollback()

    # 2. Storage and machine identity.
    videos_dir = ensure_videos_dir(settings)
    machine_id = settings.machine_id
    if machine_id is None:
        raise VideoSessionError("machine_id_not_configured")

    # 3. Copy and hash.
    partial = await stream_to_partial(chunks, videos_dir)
    session_id = uuid.uuid4()
    relative_path: str | None = None
    try:
        # 4. Probe.
        probe = await asyncio.to_thread(probe_video, partial.path)

        # 5. Insert, move to the final name, then commit.
        database_session.add(
            Session(
                id=session_id,
                name=name.strip(),
                camera_id=camera_name,
                registered_camera_id=registered_camera_id,
                source_kind=SourceKind.VIDEO_FILE,
            )
        )
        database_session.flush()
        database_session.add_all(
            [
                VideoSource(
                    session_id=session_id,
                    relative_path=f"{session_id}{extension}",
                    original_filename=PureWindowsPath(original_filename).name,
                    size_bytes=partial.size_bytes,
                    sha256=partial.sha256,
                    origin_machine_id=machine_id,
                    width=probe.width,
                    height=probe.height,
                    fps=probe.fps,
                    fps_is_estimated=probe.fps_is_estimated,
                    frame_count=probe.frame_count,
                    declared_frame_count=(
                        None
                        if extension in UNRELIABLE_FRAME_COUNT_EXTENSIONS
                        else probe.declared_frame_count
                    ),
                    duration_seconds=probe.duration_seconds,
                ),
                ReferenceFrame(
                    session_id=session_id,
                    frame_index=probe.reference_frame_index,
                    video_timestamp_seconds=probe.reference_timestamp_seconds,
                    width=probe.width,
                    height=probe.height,
                    media_type=REFERENCE_MEDIA_TYPE,
                    image=probe.reference_jpeg,
                ),
            ]
        )
        database_session.flush()
        relative_path = finalize(partial, videos_dir, session_id, extension)
        database_session.commit()
    except BaseException:
        # 6. Leave nothing behind: no rows, no partial, no destination file.
        database_session.rollback()
        discard(partial, videos_dir, relative_path)
        raise
    return session_id


async def relink_video(
    database_session: DatabaseSession,
    settings: Settings,
    session_id: uuid.UUID,
    chunks: AsyncIterator[bytes],
) -> uuid.UUID:
    """Store the same video again on this machine; metadata is never touched."""

    flow_session = get_active_session(database_session, session_id)
    if flow_session is None:
        raise VideoSessionError("session_not_found")
    source = database_session.get(VideoSource, session_id)
    if flow_session.source_kind != SourceKind.VIDEO_FILE or source is None:
        raise VideoSessionError("not_video_session")
    expected = (source.sha256, source.size_bytes)
    relative_path = source.relative_path
    database_session.rollback()

    videos_dir = ensure_videos_dir(settings)
    partial = await stream_to_partial(chunks, videos_dir)
    try:
        if (partial.sha256, partial.size_bytes) != expected:
            raise VideoSessionError("hash_mismatch")
        # Recheck after the upload under the removal lock before touching disk.
        if get_active_session(database_session, session_id, lock=True) is None:
            raise VideoSessionError("session_not_found")
        os.replace(partial.path, video_path(videos_dir, relative_path))
        database_session.commit()
    except BaseException:
        database_session.rollback()
        discard(partial, videos_dir)
        raise
    return session_id


def find_duplicate_session_ids(
    database_session: DatabaseSession, sha256: str, exclude: uuid.UUID
) -> list[uuid.UUID]:
    """Other sessions registered with the same content, oldest first."""

    return list(
        database_session.scalars(
            select(VideoSource.session_id)
            .join(Session, Session.id == VideoSource.session_id)
            .where(
                VideoSource.sha256 == sha256,
                VideoSource.session_id != exclude,
                Session.deleted_at.is_(None),
            )
            .order_by(Session.created_at, Session.id)
        )
    )
