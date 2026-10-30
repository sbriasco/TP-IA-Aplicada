"""Webcam chat figures come from live checkpoints, not shop_metrics."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from flowsight.db.models import JobStatus, LiveAnalysisState, LiveCrossingBucket, ProcessingJob
from flowsight.services.chat_metrics import LiveChatUnavailable, read_figures
from flowsight.services.jobs import transition_job


def test_completed_webcam_figures_cite_live_crossings_dwell_and_coverage(live_job):
    from datetime import UTC, datetime

    from flowsight.db.models import LiveCaptureSegment, LiveCrossing, SceneVersionShop
    from flowsight.services.jobs import transition_job as move

    factory, job_id, _lease = live_job
    with factory.begin() as database:
        job = database.get(ProcessingJob, job_id)
        shop = database.scalar(
            select(SceneVersionShop).where(
                SceneVersionShop.scene_version_id == job.scene_version_id
            )
        )
        segment_id = __import__("uuid").uuid4()
        database.add(
            LiveCaptureSegment(
                id=segment_id,
                job_id=job_id,
                session_id=job.session_id,
                segment_index=0,
                started_capture_seconds=0,
                ended_capture_seconds=90,
                first_sequence=1,
                last_sequence=2,
                reason="initial",
            )
        )
        database.flush()
        database.add(
            LiveCrossing(
                job_id=job_id,
                session_id=job.session_id,
                segment_id=segment_id,
                shop_id=shop.shop_id,
                track_id=1,
                candidate_sequence=1,
                capture_sequence=1,
                capture_timestamp_seconds=Decimal("10"),
                confirmed_at_capture_seconds=Decimal("10.4"),
                direction="entry",
                foot_x=Decimal(".5"),
                foot_y=Decimal(".5"),
            )
        )
        database.add(
            LiveCrossingBucket(
                job_id=job_id,
                session_id=job.session_id,
                shop_id=shop.shop_id,
                bucket_index=0,
                start_seconds=0,
                end_seconds=60,
                entries=2,
                exits=1,
                observed_seconds=60,
                missing_seconds=0,
                pending_count=0,
                is_open=False,
                coverage_incomplete=False,
                unknown_tail=False,
                revision=1,
            )
        )
        database.add(
            LiveCrossingBucket(
                job_id=job_id,
                session_id=job.session_id,
                shop_id=shop.shop_id,
                bucket_index=1,
                start_seconds=60,
                end_seconds=90,
                entries=0,
                exits=0,
                observed_seconds=20,
                missing_seconds=10,
                pending_count=0,
                is_open=False,
                coverage_incomplete=True,
                unknown_tail=False,
                revision=1,
            )
        )
        state = database.get(LiveAnalysisState, job_id)
        state.revision = 1
        state.elapsed_capture_seconds = 90
        state.observed_seconds = 80
        state.missing_seconds = 10
        state.coverage_complete = False
        state.zone_dwell = {
            str(shop.shop_id): {
                "interior_average_seconds": 12.5,
                "interior_sample_count": 2,
                "front_average_seconds": 4,
                "front_sample_count": 1,
            }
        }
        move(database, job_id=job_id, target=JobStatus.PROCESSING, occurred_at=datetime.now(UTC))
        move(database, job_id=job_id, target=JobStatus.COMPLETED, occurred_at=datetime.now(UTC))
        session_id, shop_id = job.session_id, shop.shop_id

    with factory() as database:
        figures = {row.code: row for row in read_figures(database, session_id, shop_id)}
    assert figures["total_crossings"].value == Decimal(3)
    assert figures["entries"].value == Decimal(2)
    assert figures["exits"].value == Decimal(1)
    assert figures["dwell_interior_mean_seconds"].value == Decimal("12.5")
    assert figures["dwell_front_mean_seconds"].value == Decimal(4)
    assert figures["coverage_percent"].value == Decimal("88.9")
    assert figures["elapsed_capture_seconds"].value == Decimal(90)
    assert figures["peak"].availability == "available"
    assert figures["peak"].start_seconds == Decimal(0)
    assert figures["peak"].track_count == 3
    assert figures["funnel_entries"].availability == "unavailable"
    assert figures["visit_count"].availability == "unavailable"


def test_running_webcam_chat_source_is_rejected(live_job):
    from flowsight.db.models import SceneVersionShop

    factory, job_id, _lease = live_job
    with factory.begin() as database:
        job = database.get(ProcessingJob, job_id)
        shop = database.scalar(
            select(SceneVersionShop).where(
                SceneVersionShop.scene_version_id == job.scene_version_id
            )
        )
        if job.status != JobStatus.PROCESSING:
            transition_job(
                database,
                job_id=job_id,
                target=JobStatus.PROCESSING,
                occurred_at=__import__("datetime").datetime.now(
                    __import__("datetime").UTC
                ),
            )
        session_id, shop_id = job.session_id, shop.shop_id

    with factory() as database:
        with pytest.raises(LiveChatUnavailable):
            read_figures(database, session_id, shop_id)
