"""Coalescing queue for remote measure flushes (no YOLO / no Azure)."""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from flowsight.vision.spatial import CrossingFact, ShopCounts
from flowsight.worker.video_analysis import (
    _coalesce_measure_payloads,
    _MeasureFlushGate,
    _MeasureFlushPayload,
)


def _payload(*, frames: int, facts: tuple[CrossingFact, ...] = ()) -> _MeasureFlushPayload:
    shop = uuid.uuid4()
    return _MeasureFlushPayload(
        job_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        frames_analyzed=frames,
        video_timestamp_seconds=Decimal(frames),
        counts=(
            ShopCounts(
                shop_id=shop,
                shop_name="Local",
                entries=frames,
                exits=0,
                visible_occupancy=1,
            ),
        ),
        facts=facts,
        fps=30.0,
    )


def _fact(frame_index: int) -> CrossingFact:
    return CrossingFact(
        shop_id=uuid.uuid4(),
        track_id=1,
        frame_index=frame_index,
        direction="entry",
        disposition="confirmed",
        foot=(0.5, 0.5),
    )


def test_coalesce_keeps_latest_totals_and_appends_facts() -> None:
    first = _payload(frames=15, facts=(_fact(2),))
    second = _payload(frames=30, facts=(_fact(20),))
    merged = _coalesce_measure_payloads(first, second)
    assert merged.frames_analyzed == 30
    assert merged.counts[0].entries == 30
    assert len(merged.facts) == 2
    assert merged.facts[0].frame_index == 2
    assert merged.facts[1].frame_index == 20


def test_remote_queue_does_not_block_submit_on_slow_write() -> None:
    written: list[int] = []
    started = time.perf_counter()
    gate = _MeasureFlushGate(object(), overlap=True, interval_s=0.05)

    def write(payload: _MeasureFlushPayload) -> None:
        time.sleep(0.15)
        written.append(payload.frames_analyzed)

    gate._write = write  # type: ignore[method-assign]
    gate.submit(_payload(frames=15))
    gate.submit(_payload(frames=30))
    assert time.perf_counter() - started < 0.1
    gate.join()
    assert written
    assert written[-1] == 30
