"""Store the file-analysis result of a completed live job."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    MeasureAvailability,
    ShopMetric,
    ShopMetricCode,
    ShopMetricLabel,
    SourceKind,
    TrafficBucket,
)
from flowsight.services.funnel import persist_shop_funnel
from flowsight.services.possible_purchase import persist_possible_purchase
from flowsight.services.visit_patterns import persist_visit_patterns
from flowsight.vision.events import SceneEventFact
from flowsight.vision.live_file_analysis import CAPTURE_FPS
from flowsight.vision.metrics import MetricValue, TrafficBucketValue
from flowsight.vision.possible_purchase import PossiblePurchaseDraft
from flowsight.vision.spatial import ShopGeometry
from flowsight.vision.visit_patterns import VisitPatternDraft


def persist_live_file_result(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    shops: list[ShopGeometry],
    events: list[SceneEventFact],
    patterns: VisitPatternDraft,
    purchases: PossiblePurchaseDraft,
    metrics: dict[uuid.UUID, list[MetricValue]],
    buckets: dict[uuid.UUID, list[TrafficBucketValue]],
) -> None:
    persist_shop_funnel(
        database_session,
        job_id=job_id,
        session_id=session_id,
        events=events,
        fps=float(CAPTURE_FPS),
        windows={shop.shop_id: shop.window_polygon is not None for shop in shops},
        source_kind=SourceKind.WEBCAM.value,
        allow_webcam=True,
    )
    persist_visit_patterns(
        database_session,
        job_id=job_id,
        session_id=session_id,
        draft=patterns,
        source_kind=SourceKind.WEBCAM.value,
        allow_webcam=True,
    )
    persist_possible_purchase(
        database_session,
        job_id=job_id,
        session_id=session_id,
        draft=purchases,
        source_kind=SourceKind.WEBCAM.value,
        allow_webcam=True,
    )
    for shop_id, rows in metrics.items():
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
        for bucket in buckets.get(shop_id, []):
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
