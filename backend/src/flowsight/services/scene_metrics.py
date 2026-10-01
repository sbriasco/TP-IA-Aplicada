"""Persist scene facts and shop metrics when an analysis completes."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
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
    SceneEvent,
    SceneEventKind,
    SceneVersionShop,
    SceneZoneRole,
    Session,
    Shop,
    ShopMetric,
    ShopMetricCode,
    ShopMetricLabel,
    TrafficBucket,
)
from flowsight.vision.events import SceneEventFact
from flowsight.vision.metrics import MetricValue, TrafficBucketValue, build_shop_metrics

_SIX = Decimal("0.000001")


class ResultIncomplete(Exception):
    """The session has no completed analysis that can be shown as final."""


class ShopNotInSession(Exception):
    """The shop is not part of the completed analysis of this session."""


def persist_completed_scene(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    events: Sequence[SceneEventFact],
    fps: float,
    duration_seconds: float,
    front_by_shop: dict[uuid.UUID, bool],
    line_by_shop: dict[uuid.UUID, bool] | None = None,
) -> None:
    """Insert facts and metrics. Official measure values are copied, never updated."""

    for fact in events:
        database_session.add(
            SceneEvent(
                job_id=job_id,
                session_id=session_id,
                shop_id=fact.shop_id,
                track_id=fact.track_id,
                kind=SceneEventKind(fact.kind),
                zone_role=None if fact.zone_role is None else SceneZoneRole(fact.zone_role),
                frame_index=fact.frame_index,
                video_timestamp_seconds=_timestamp(fact.frame_index, fps),
                duration_seconds=fact.duration_seconds,
                source_crossing_id=_crossing_id(database_session, job_id, fact),
            )
        )
    database_session.flush()
    official = _official(database_session, job_id)
    for shop_id, front in front_by_shop.items():
        entries, exits, occupancy = official.get(shop_id, (0, 0, 0))
        rows, buckets, _peak = build_shop_metrics(
            events,
            shop_id=shop_id,
            entries=entries,
            exits=exits,
            visible_occupancy=occupancy,
            fps=fps,
            duration_seconds=duration_seconds,
            front_configured=front,
            line_configured=(line_by_shop or {}).get(shop_id, True),
        )
        for row in rows:
            database_session.add(
                ShopMetric(
                    job_id=job_id,
                    session_id=session_id,
                    shop_id=shop_id,
                    code=ShopMetricCode(row.code),
                    value=row.value,
                    availability=MeasureAvailability(row.availability),
                    label=ShopMetricLabel(row.label),
                    unavailable_reason=row.unavailable_reason,
                )
            )
        for bucket in buckets:
            database_session.add(
                TrafficBucket(
                    job_id=job_id,
                    session_id=session_id,
                    shop_id=shop_id,
                    bucket_index=bucket.bucket_index,
                    start_seconds=bucket.start_seconds,
                    track_count=bucket.track_count,
                )
            )


def load_shop_metrics(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> tuple[list[MetricValue], list[TrafficBucketValue], TrafficBucketValue]:
    job = _completed_job(database_session, session_id)
    _require_shop(database_session, job, shop_id)
    stored = database_session.scalars(
        select(ShopMetric)
        .where(ShopMetric.job_id == job.id, ShopMetric.shop_id == shop_id)
        .order_by(ShopMetric.code)
    ).all()
    buckets = database_session.scalars(
        select(TrafficBucket)
        .where(TrafficBucket.job_id == job.id, TrafficBucket.shop_id == shop_id)
        .order_by(TrafficBucket.bucket_index)
    ).all()
    if not stored:
        rows = [
            MetricValue(
                code.value, None, "unavailable", _label(code.value), "metrics_not_generated"
            )
            for code in ShopMetricCode
        ]
        empty = TrafficBucketValue(0, Decimal("0.000000"), 0)
        return rows, [], empty
    flow = [
        TrafficBucketValue(bucket.bucket_index, bucket.start_seconds, bucket.track_count)
        for bucket in buckets
    ]
    peak = min(flow, key=lambda bucket: (-bucket.track_count, bucket.bucket_index))
    rows = [
        MetricValue(
            metric.code.value,
            metric.value,
            metric.availability.value,
            metric.label.value,
            metric.unavailable_reason,
        )
        for metric in _ordered(stored)
    ]
    return rows, flow, peak


def load_events(
    database_session: DatabaseSession,
    session_id: uuid.UUID,
    *,
    shop_id: uuid.UUID | None = None,
    from_seconds: Decimal | None = None,
    to_seconds: Decimal | None = None,
) -> list[SceneEvent]:
    job = _completed_job(database_session, session_id)
    if shop_id is not None:
        _require_shop(database_session, job, shop_id)
    statement = select(SceneEvent).where(SceneEvent.job_id == job.id)
    if shop_id is not None:
        statement = statement.where(SceneEvent.shop_id == shop_id)
    if from_seconds is not None:
        statement = statement.where(SceneEvent.video_timestamp_seconds >= from_seconds)
    if to_seconds is not None:
        statement = statement.where(SceneEvent.video_timestamp_seconds < to_seconds)
    return list(
        database_session.scalars(
            statement.order_by(SceneEvent.video_timestamp_seconds, SceneEvent.track_id)
        )
    )


def _completed_job(database_session: DatabaseSession, session_id: uuid.UUID) -> ProcessingJob:
    job = database_session.scalar(
        select(ProcessingJob)
        .join(Session, Session.id == ProcessingJob.session_id)
        .where(ProcessingJob.session_id == session_id, Session.deleted_at.is_(None))
        .order_by(ProcessingJob.created_at.desc())
    )
    if job is None or job.status.value != "completed" or not job.result_complete:
        raise ResultIncomplete
    return job


def _require_shop(
    database_session: DatabaseSession, job: ProcessingJob, shop_id: uuid.UUID
) -> None:
    shop = database_session.get(Shop, shop_id)
    if shop is None:
        raise ShopNotInSession
    official = database_session.scalar(
        select(AnalysisMeasure.id).where(
            AnalysisMeasure.job_id == job.id, AnalysisMeasure.shop_id == shop_id
        )
    )
    if official is None and job.scene_version_id is None:
        raise ShopNotInSession
    if official is None:
        linked = database_session.scalar(
            select(SceneVersionShop.id).where(
                SceneVersionShop.scene_version_id == job.scene_version_id,
                SceneVersionShop.shop_id == shop_id,
            )
        )
        if linked is None:
            raise ShopNotInSession


def _official(
    database_session: DatabaseSession, job_id: uuid.UUID
) -> dict[uuid.UUID, tuple[int, int, int]]:
    rows = database_session.scalars(
        select(AnalysisMeasure).where(
            AnalysisMeasure.job_id == job_id, AnalysisMeasure.partial.is_(False)
        )
    ).all()
    grouped: dict[uuid.UUID, dict[MeasureCode, int]] = {}
    for row in rows:
        grouped.setdefault(row.shop_id, {})[row.code] = row.value or 0
    return {
        shop_id: (
            codes.get(MeasureCode.ENTRIES, 0),
            codes.get(MeasureCode.EXITS, 0),
            codes.get(MeasureCode.VISIBLE_OCCUPANCY, 0),
        )
        for shop_id, codes in grouped.items()
    }


def _crossing_id(
    database_session: DatabaseSession, job_id: uuid.UUID, fact: SceneEventFact
) -> uuid.UUID | None:
    if fact.crossing is None or fact.kind not in {"store_enter", "store_exit"}:
        return None
    direction = (
        CrossingDirection.ENTRY if fact.crossing.direction == "entry" else CrossingDirection.EXIT
    )
    return database_session.scalar(
        select(LineCrossing.id).where(
            LineCrossing.job_id == job_id,
            LineCrossing.shop_id == fact.shop_id,
            LineCrossing.track_id == fact.track_id,
            LineCrossing.frame_index == fact.crossing.frame_index,
            LineCrossing.direction == direction,
            LineCrossing.disposition == CrossingDisposition.CONFIRMED,
        )
    )


def _timestamp(frame_index: int, fps: float) -> Decimal:
    return (Decimal(frame_index) / Decimal(str(fps))).quantize(_SIX)


def _ordered(stored: Sequence[ShopMetric]) -> list[ShopMetric]:
    order = [code.value for code in ShopMetricCode]
    return sorted(stored, key=lambda metric: order.index(metric.code.value))


def _label(code: str) -> str:
    if code == "traffic_total":
        return "visit_estimate"
    if code == "visible_occupancy":
        return "visible"
    if code.startswith("dwell_"):
        return "observable"
    return "none"
