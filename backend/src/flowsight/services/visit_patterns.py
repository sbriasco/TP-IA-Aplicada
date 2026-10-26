"""Persist and read visit patterns. The draft is computed before this module runs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    MeasureAvailability,
    SceneZoneRole,
    SourceKind,
    VisitAreaTransition,
    VisitGroup,
    VisitGroupLabel,
    VisitGroupMember,
    VisitPatternReport,
    VisitSequence,
    VisitShopTransition,
)
from flowsight.services.scene_metrics import ResultIncomplete, _completed_job
from flowsight.services.sessions import get_active_session
from flowsight.vision.visit_patterns import (
    DIRECTION_DEGREES,
    MINIMUM_SECONDS,
    MOTION_EPSILON_WIDTH_FRACTION,
    PROXIMITY_WIDTH_FRACTION,
    VisitPatternDraft,
)


class LivePatternsUnavailable(Exception):
    """A webcam session has no visit patterns."""


@dataclass(frozen=True)
class VisitPatternsView:
    report: VisitPatternReport
    area_transitions: tuple[VisitAreaTransition, ...]
    sequences: tuple[VisitSequence, ...]
    shop_transitions: tuple[VisitShopTransition, ...]
    groups: tuple[tuple[VisitGroup, tuple[int, ...]], ...]


def persist_visit_patterns(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    draft: VisitPatternDraft,
    source_kind: str,
) -> None:
    """Store the closed result. A webcam source stores nothing."""

    if source_kind == SourceKind.WEBCAM.value:
        return
    database_session.add(
        VisitPatternReport(
            job_id=job_id,
            session_id=session_id,
            proximity_width_fraction=PROXIMITY_WIDTH_FRACTION,
            direction_degrees=DIRECTION_DEGREES,
            minimum_seconds=MINIMUM_SECONDS,
            motion_epsilon_width_fraction=MOTION_EPSILON_WIDTH_FRACTION,
            patterns_availability=MeasureAvailability(draft.patterns_availability),
            patterns_unavailable_reason=draft.patterns_unavailable_reason,
            groups_availability=MeasureAvailability.AVAILABLE,
            group_count=draft.group_count,
            precision_uncommitted=True,
        )
    )
    if draft.patterns_availability == "available":
        for row in draft.area_transitions:
            database_session.add(
                VisitAreaTransition(
                    job_id=job_id,
                    from_shop_id=row.from_shop_id,
                    to_shop_id=row.to_shop_id,
                    from_zone_role=SceneZoneRole(row.from_zone_role),
                    to_zone_role=SceneZoneRole(row.to_zone_role),
                    track_count=row.track_count,
                )
            )
        for row in draft.sequences:
            database_session.add(
                VisitSequence(
                    job_id=job_id,
                    areas=[
                        {"shop_id": str(area.shop_id), "zone_role": area.zone_role}
                        for area in row.areas
                    ],
                    track_count=row.track_count,
                )
            )
        for row in draft.shop_transitions:
            database_session.add(
                VisitShopTransition(
                    job_id=job_id,
                    from_shop_id=row.from_shop_id,
                    to_shop_id=row.to_shop_id,
                    track_count=row.track_count,
                )
            )
    for episode in draft.groups:
        group = VisitGroup(
            job_id=job_id,
            ordinal=episode.ordinal,
            started_video_timestamp_seconds=episode.started_video_timestamp_seconds,
            ended_video_timestamp_seconds=episode.ended_video_timestamp_seconds,
            label=VisitGroupLabel.GROUP_ESTIMATE,
        )
        database_session.add(group)
        database_session.flush()
        for track_id in episode.track_ids:
            database_session.add(VisitGroupMember(group_id=group.id, track_id=track_id))


def load_visit_patterns(
    database_session: DatabaseSession, session_id: uuid.UUID
) -> VisitPatternsView:
    session = get_active_session(database_session, session_id)
    if session is not None and session.source_kind is SourceKind.WEBCAM:
        raise LivePatternsUnavailable
    job = _completed_job(database_session, session_id)
    report = database_session.scalar(
        select(VisitPatternReport).where(VisitPatternReport.job_id == job.id)
    )
    if report is None:
        raise ResultIncomplete
    transitions = database_session.scalars(
        select(VisitAreaTransition).where(VisitAreaTransition.job_id == job.id)
    ).all()
    sequences = database_session.scalars(
        select(VisitSequence).where(VisitSequence.job_id == job.id)
    ).all()
    shops = database_session.scalars(
        select(VisitShopTransition).where(VisitShopTransition.job_id == job.id)
    ).all()
    stored_groups = database_session.scalars(
        select(VisitGroup).where(VisitGroup.job_id == job.id).order_by(VisitGroup.ordinal)
    ).all()
    groups: list[tuple[VisitGroup, tuple[int, ...]]] = []
    for group in stored_groups:
        members = database_session.scalars(
            select(VisitGroupMember.track_id)
            .where(VisitGroupMember.group_id == group.id)
            .order_by(VisitGroupMember.track_id)
        ).all()
        groups.append((group, tuple(members)))
    return VisitPatternsView(
        report=report,
        area_transitions=tuple(transitions),
        sequences=tuple(sequences),
        shop_transitions=tuple(shops),
        groups=tuple(groups),
    )
