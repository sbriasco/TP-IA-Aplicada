"""Upsert the three official measures and insert crossing facts, not frames."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    AnalysisMeasure,
    CrossingDirection,
    CrossingDisposition,
    LineCrossing,
    MeasureAvailability,
    MeasureCode,
    ProcessingJob,
    SceneVersionShop,
)
from flowsight.vision.spatial import CrossingFact, ShopCounts


@dataclass(frozen=True)
class MeasureView:
    job_id: uuid.UUID
    session_id: uuid.UUID
    shop_id: uuid.UUID
    shop_name: str
    code: MeasureCode
    value: int | None
    availability: MeasureAvailability
    partial: bool
    video_timestamp_seconds: Decimal


def sync_measures(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    video_timestamp_seconds: Decimal,
    counts: Sequence[ShopCounts],
    facts: Sequence[CrossingFact],
    fps: float,
) -> None:
    """Write the current totals and only the crossings decided on this frame."""

    for count in counts:
        values = {
            MeasureCode.ENTRIES: count.entries,
            MeasureCode.EXITS: count.exits,
            MeasureCode.VISIBLE_OCCUPANCY: count.visible_occupancy,
        }
        for code, value in values.items():
            _upsert(
                database_session,
                job_id=job_id,
                session_id=session_id,
                shop_id=count.shop_id,
                code=code,
                value=value,
                video_timestamp_seconds=video_timestamp_seconds,
            )
    for fact in facts:
        database_session.add(
            LineCrossing(
                job_id=job_id,
                session_id=session_id,
                shop_id=fact.shop_id,
                track_id=fact.track_id,
                frame_index=fact.frame_index,
                video_timestamp_seconds=_timestamp(fact.frame_index, fps),
                direction=CrossingDirection(fact.direction),
                disposition=CrossingDisposition(fact.disposition),
                foot_x=_number(fact.foot[0]),
                foot_y=_number(fact.foot[1]),
            )
        )


def close_measures(database_session: DatabaseSession, job_id: uuid.UUID) -> None:
    """Same rows become the official numbers. Nothing is inserted again."""

    rows = database_session.scalars(
        select(AnalysisMeasure).where(AnalysisMeasure.job_id == job_id)
    )
    for row in rows:
        row.partial = False


def list_measures(database_session: DatabaseSession, job: ProcessingJob) -> list[MeasureView]:
    """Measures of the scene version the job used, with that version's shop name."""

    shop_name = SceneVersionShop.name
    rows = database_session.execute(
        select(AnalysisMeasure, shop_name)
        .outerjoin(
            SceneVersionShop,
            (SceneVersionShop.shop_id == AnalysisMeasure.shop_id)
            & (SceneVersionShop.scene_version_id == job.scene_version_id),
        )
        .where(AnalysisMeasure.job_id == job.id)
        .order_by(SceneVersionShop.position, AnalysisMeasure.code)
    ).all()
    return [
        MeasureView(
            job_id=measure.job_id,
            session_id=measure.session_id,
            shop_id=measure.shop_id,
            shop_name=name or "",
            code=measure.code,
            value=measure.value,
            availability=measure.availability,
            partial=measure.partial,
            video_timestamp_seconds=measure.video_timestamp_seconds,
        )
        for measure, name in rows
    ]


def _upsert(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    shop_id: uuid.UUID,
    code: MeasureCode,
    value: int,
    video_timestamp_seconds: Decimal,
) -> None:
    existing = database_session.scalar(
        select(AnalysisMeasure).where(
            AnalysisMeasure.job_id == job_id,
            AnalysisMeasure.shop_id == shop_id,
            AnalysisMeasure.code == code,
        )
    )
    if existing is None:
        database_session.add(
            AnalysisMeasure(
                job_id=job_id,
                session_id=session_id,
                shop_id=shop_id,
                code=code,
                value=value,
                availability=MeasureAvailability.AVAILABLE,
                partial=True,
                video_timestamp_seconds=video_timestamp_seconds,
            )
        )
        return
    existing.value = value
    existing.availability = MeasureAvailability.AVAILABLE
    existing.partial = True
    existing.video_timestamp_seconds = video_timestamp_seconds


def _timestamp(frame_index: int, fps: float) -> Decimal:
    return (Decimal(frame_index) / Decimal(str(fps))).quantize(Decimal("0.000001"))


def _number(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))
