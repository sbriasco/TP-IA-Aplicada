"""Persist and read possible-purchase estimates. Draft computed before this module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    MeasureAvailability,
    PossiblePurchaseMember,
    PossiblePurchaseReport,
    SourceKind,
)
from flowsight.services.scene_metrics import ResultIncomplete, _completed_job
from flowsight.services.sessions import get_active_session
from flowsight.vision.possible_purchase import MINIMUM_SECONDS, PossiblePurchaseDraft


class LivePurchaseUnavailable(Exception):
    """A webcam session has no possible-purchase estimate."""


@dataclass(frozen=True)
class PossiblePurchaseView:
    report: PossiblePurchaseReport
    track_ids: tuple[int, ...]


def persist_possible_purchase(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    draft: PossiblePurchaseDraft,
    source_kind: str,
) -> None:
    """Store the closed result. A webcam source stores nothing."""

    if source_kind == SourceKind.WEBCAM.value:
        return
    report = PossiblePurchaseReport(
        job_id=job_id,
        session_id=session_id,
        minimum_seconds=MINIMUM_SECONDS,
        visit_count=draft.visit_count,
        availability=MeasureAvailability.AVAILABLE,
        precision_uncommitted=True,
    )
    database_session.add(report)
    database_session.flush()
    for track_id in draft.track_ids:
        database_session.add(
            PossiblePurchaseMember(report_id=report.id, track_id=track_id)
        )


def load_possible_purchase(
    database_session: DatabaseSession, session_id: uuid.UUID
) -> PossiblePurchaseView:
    """Return the closed report for a completed file session."""

    flow_session = get_active_session(database_session, session_id)
    if flow_session is None:
        raise ResultIncomplete()
    if flow_session.source_kind == SourceKind.WEBCAM:
        raise LivePurchaseUnavailable()
    job = _completed_job(database_session, session_id)
    if job is None:
        raise ResultIncomplete()
    report = database_session.scalar(
        select(PossiblePurchaseReport).where(PossiblePurchaseReport.job_id == job.id)
    )
    if report is None:
        raise ResultIncomplete()
    members = database_session.scalars(
        select(PossiblePurchaseMember)
        .where(PossiblePurchaseMember.report_id == report.id)
        .order_by(PossiblePurchaseMember.track_id)
    ).all()
    return PossiblePurchaseView(
        report=report,
        track_ids=tuple(member.track_id for member in members),
    )


def empty_draft() -> PossiblePurchaseDraft:
    """Zero visits — used when tests need a typed empty payload."""

    return PossiblePurchaseDraft(
        visit_count=0,
        track_ids=(),
        minimum_seconds=Decimal(MINIMUM_SECONDS),
    )
