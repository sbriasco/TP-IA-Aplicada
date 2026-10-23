"""Upsert the three official measures and insert crossing facts, not frames."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
    """Write the current totals and only the crossings decided since the last flush."""

    rows: list[dict[str, object]] = []
    for count in counts:
        values = {
            MeasureCode.ENTRIES: count.entries,
            MeasureCode.EXITS: count.exits,
            MeasureCode.VISIBLE_OCCUPANCY: count.visible_occupancy,
        }
        for code, value in values.items():
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "job_id": job_id,
                    "session_id": session_id,
                    "shop_id": count.shop_id,
                    "code": code,
                    "value": value,
                    "availability": MeasureAvailability.AVAILABLE,
                    "partial": True,
                    "video_timestamp_seconds": video_timestamp_seconds,
                }
            )
    if rows:
        statement = insert(AnalysisMeasure).values(rows)
        database_session.execute(
            statement.on_conflict_do_update(
                constraint="uq_analysis_measures_job_id_shop_id_code",
                set_={
                    "value": statement.excluded.value,
                    "availability": statement.excluded.availability,
                    "partial": statement.excluded.partial,
                    "video_timestamp_seconds": statement.excluded.video_timestamp_seconds,
                },
            )
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


def _timestamp(frame_index: int, fps: float) -> Decimal:
    return (Decimal(frame_index) / Decimal(str(fps))).quantize(Decimal("0.000001"))


def _number(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))
