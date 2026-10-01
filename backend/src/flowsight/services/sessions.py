"""Session visibility and removal from public history.

Removal retains all files and rows. Immutable camera scene versions and their
reference image deliberately remain readable, even when the reference session
has been removed: other sessions can still use those saved configurations.
New scene versions must use an active reference session. All other public
session and job reads exclude removed sessions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import JobStatus, ProcessingJob, Session


class SessionNotFound(LookupError):
    pass


class SessionHasActiveJobs(ValueError):
    pass


def get_active_session(
    database: DatabaseSession, session_id: uuid.UUID, *, lock: bool = False
) -> Session | None:
    statement = select(Session).where(Session.id == session_id, Session.deleted_at.is_(None))
    if lock:
        # Creation and removal take this same lock until commit. Refresh an
        # already-loaded object after waiting so a stale session cannot start work.
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return database.scalar(statement)


def remove_session(database: DatabaseSession, session_id: uuid.UUID) -> None:
    """Mark a session removed. Repeated removal succeeds; unknown ids do not.

    The caller commits. Every pending/processing job blocks removal, including
    an older job when the newest job has already finished.
    """

    session = database.scalar(
        select(Session)
        .where(Session.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if session is None:
        raise SessionNotFound
    if session.deleted_at is not None:
        return
    active_job = database.scalar(
        select(ProcessingJob.id)
        .where(
            ProcessingJob.session_id == session_id,
            ProcessingJob.status.in_((JobStatus.PENDING, JobStatus.PROCESSING)),
        )
        .limit(1)
    )
    if active_job is not None:
        raise SessionHasActiveJobs
    session.deleted_at = datetime.now(UTC)
    database.flush()
