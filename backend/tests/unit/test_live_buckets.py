"""Minute attribution follows capture time; the runtime window never grows with duration."""

import uuid
from decimal import Decimal

from flowsight.vision.live_buckets import LiveBuckets
from flowsight.vision.live_spatial import LiveCrossingFact

SHOP = uuid.UUID(int=1)


def fact(timestamp, *, direction="entry"):
    return LiveCrossingFact(
        SHOP,
        1,
        0,
        1,
        100,
        Decimal(timestamp),
        Decimal(timestamp) + Decimal(".4"),
        direction,
        (0.5, 0.5),
    )


def test_confirmed_crossing_corrects_original_minute():
    buckets = LiveBuckets([SHOP])
    buckets.observe(Decimal("59.9"), facts=[], pending=[fact("59.9")], interval=None, revision=1)
    buckets.observe(
        Decimal("60.4"),
        facts=[fact("59.9")],
        pending=[],
        interval=(Decimal("59.9"), Decimal("60.4"), True),
        revision=2,
    )
    first, second = buckets.snapshot()
    assert first["bucket_index"] == 0 and first["entries"] == 1
    assert first["pending_count"] == 0 and not first["is_open"]
    assert second["bucket_index"] == 1 and second["entries"] == 0 and second["is_open"]
    assert first["observed_seconds"] == 0.1 and second["observed_seconds"] == 0.4


def test_gap_is_split_across_minutes_without_assuming_observed_people():
    buckets = LiveBuckets([SHOP])
    buckets.observe(Decimal(58), facts=[], pending=[], interval=None, revision=1)
    buckets.observe(
        Decimal(62), facts=[], pending=[], interval=(Decimal(58), Decimal(62), False), revision=2
    )
    first, second = buckets.snapshot()
    assert first["missing_seconds"] == 2 and second["missing_seconds"] == 2
    assert all(row["coverage_incomplete"] for row in buckets.snapshot())
    assert all(row["observed_seconds"] == 0 for row in buckets.snapshot())


def test_runtime_window_and_dirty_changes_are_bounded_after_flush():
    shops = [uuid.UUID(int=index + 1) for index in range(20)]
    buckets = LiveBuckets(shops)
    for minute in range(200):
        start = Decimal(minute * 60)
        buckets.observe(
            start + 1, facts=[], pending=[], interval=(start, start + 1, True), revision=minute + 1
        )
        assert len(buckets.dirty_rows()) <= 40
        buckets.acknowledge()
    assert len(buckets.snapshot()) == 1200
    assert min(row["bucket_index"] for row in buckets.snapshot()) == 140


def test_final_closes_bucket_and_marks_unconfirmed_pending():
    buckets = LiveBuckets([SHOP])
    buckets.observe(Decimal(5), facts=[], pending=[fact("5")], interval=None, revision=1)
    buckets.finish(revision=2)
    row = buckets.snapshot()[0]
    assert not row["is_open"] and row["pending_count"] == 0


def test_old_gap_remains_in_session_coverage_after_window_eviction():
    buckets = LiveBuckets([SHOP])
    buckets.observe(
        Decimal(2), facts=[], pending=[], interval=(Decimal(0), Decimal(2), False), revision=1
    )
    buckets.acknowledge()
    for minute in range(1, 65):
        time = Decimal(minute * 60)
        buckets.observe(time, facts=[], pending=[], interval=None, revision=minute + 1)
        buckets.acknowledge()
    assert all(not row["coverage_incomplete"] for row in buckets.snapshot())
    assert not buckets.coverage_complete
