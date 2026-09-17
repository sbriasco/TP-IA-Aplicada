"""Persistence service for validated synthetic traces."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import Event, Observation, SyntheticFrame
from flowsight.synthetic.trace import SyntheticTrace


def persist_synthetic_trace(
    database_session: DatabaseSession, trace: SyntheticTrace
) -> dict[str, int]:
    """Persist a trace idempotently using its deterministic identifiers."""
    for record in trace.frames:
        if database_session.get(SyntheticFrame, record.id) is None:
            database_session.add(SyntheticFrame(**record.__dict__))
    database_session.flush()

    for record in trace.observations:
        if database_session.get(Observation, record.id) is None:
            database_session.add(Observation(**record.__dict__))
    database_session.flush()

    for record in trace.events:
        if database_session.get(Event, record.id) is None:
            database_session.add(Event(**record.__dict__))
    database_session.flush()

    job_id = trace.frames[0].job_id if trace.frames else None
    return {
        "frames": _count_for_job(database_session, SyntheticFrame, job_id),
        "observations": _count_for_job(database_session, Observation, job_id),
        "events": _count_for_job(database_session, Event, job_id),
    }


def _count_for_job(database_session: DatabaseSession, model: type, job_id: object) -> int:
    if job_id is None:
        return 0
    return database_session.scalar(
        select(func.count()).select_from(model).where(model.job_id == job_id)
    )
