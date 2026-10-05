"""Transactional live checkpoints and source-specific read models."""

from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from flowsight.capture.contracts import CaptureError
from flowsight.db.models import (
    JobKind,
    JobStatus,
    LiveAnalysisState,
    LiveCaptureSegment,
    LiveCrossing,
    LiveCrossingBucket,
    LiveInterruption,
    LivePositionSample,
    LiveSource,
    ProcessingJob,
    SceneEntryLine,
    SceneVersionShop,
    WorkerMachine,
)
from flowsight.services.live_jobs import LiveMachineError
from flowsight.services.sessions import get_active_session


def persist_live_checkpoint(
    database,
    job_id,
    session_id,
    segment_id,
    started_at,
    frame,
    analyzed,
    revision,
    observed,
    missing,
    sampler,
    counter,
    facts,
    slots,
    now,
    *,
    bucket_rows=(),
    owner_epoch=None,
    machine_id=None,
):
    database.execute(text("SET LOCAL lock_timeout = '250ms'"))
    database.execute(text("SET LOCAL statement_timeout = '1000ms'"))
    if owner_epoch is not None:
        machine = database.scalar(
            select(WorkerMachine)
            .where(WorkerMachine.machine_id == machine_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if machine is None or machine.owner_epoch != owner_epoch:
            raise CaptureError("worker_owner_lost")
    job = database.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # A delayed write may finish after failure recovery or normal completion.
    # Serialize with the terminal transition and preserve its durable horizon.
    if job is None or job.status != JobStatus.PROCESSING:
        return
    state = database.scalar(
        select(LiveAnalysisState)
        .where(LiveAnalysisState.job_id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state.revision >= revision:
        return
    segment = database.get(LiveCaptureSegment, segment_id)
    if segment is None:
        segment_start = getattr(frame, "segment_start_seconds", Decimal(0))
        segment_reason = getattr(frame, "segment_reason", "initial")
        if segment_reason == "analysis_gap":
            previous = database.scalar(
                select(LiveCaptureSegment).where(
                    LiveCaptureSegment.job_id == job_id,
                    LiveCaptureSegment.segment_index == frame.segment_index - 1,
                )
            )
            if previous is None or previous.ended_capture_seconds is not None:
                raise CaptureError("live_segment_invalid")
            previous.ended_capture_seconds = state.elapsed_capture_seconds
            previous.last_sequence = state.last_analyzed_sequence
            database.add(
                LiveInterruption(
                    job_id=job_id,
                    session_id=session_id,
                    start_seconds=state.elapsed_capture_seconds,
                    end_seconds=segment_start,
                    end_known=True,
                    reason="analysis_gap",
                )
            )
        elif segment_reason == "reconnected":
            interruption = database.scalar(
                select(LiveInterruption)
                .where(
                    LiveInterruption.job_id == job_id,
                    LiveInterruption.end_known.is_(False),
                    LiveInterruption.reason == "capture_lost",
                )
                .order_by(LiveInterruption.start_seconds.desc())
            )
            if interruption is None:
                raise CaptureError("live_segment_invalid")
            interruption.end_seconds = segment_start
            interruption.end_known = True
        database.add(
            LiveCaptureSegment(
                id=segment_id,
                job_id=job_id,
                session_id=session_id,
                segment_index=frame.segment_index,
                started_capture_seconds=segment_start,
                first_sequence=getattr(frame, "first_sequence", 1),
                reason=segment_reason,
            )
        )
        database.flush()
    for fact in facts:
        database.execute(
            insert(LiveCrossing)
            .values(
                job_id=job_id,
                session_id=session_id,
                segment_id=segment_id,
                shop_id=fact.shop_id,
                track_id=fact.track_id,
                candidate_sequence=fact.candidate_sequence,
                capture_sequence=fact.capture_sequence,
                capture_timestamp_seconds=fact.capture_timestamp_seconds,
                confirmed_at_capture_seconds=fact.confirmed_at_capture_seconds,
                direction=fact.direction,
                foot_x=Decimal(str(fact.foot[0])),
                foot_y=Decimal(str(fact.foot[1])),
            )
            .on_conflict_do_nothing()
        )
    for change in slots.values():
        sample = change.sample
        values = dict(
            job_id=job_id,
            session_id=session_id,
            slot_index=change.slot_index,
            segment_id=segment_id,
            track_id=sample.track_id,
            capture_sequence=sample.sequence,
            capture_timestamp_seconds=sample.timestamp_s,
            foot_x=Decimal(str(sample.foot[0])),
            foot_y=Decimal(str(sample.foot[1])),
        )
        database.execute(
            insert(LivePositionSample)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[LivePositionSample.job_id, LivePositionSample.slot_index],
                set_=values,
            )
        )
    ending_capture_seconds = getattr(frame, "ending_capture_seconds", None)
    state.capture_status = "stopping" if ending_capture_seconds is not None else "connected"
    if ending_capture_seconds is not None:
        for interruption in database.scalars(
            select(LiveInterruption).where(
                LiveInterruption.job_id == job_id,
                LiveInterruption.end_known.is_(False),
                LiveInterruption.reason == "capture_lost",
            )
        ):
            interruption.end_seconds = ending_capture_seconds
            interruption.end_known = True
    state.resume_confirmed_at = None
    if bucket_rows:
        values = [
            {
                **row,
                "shop_id": uuid.UUID(row["shop_id"]),
                "job_id": job_id,
                "session_id": session_id,
            }
            for row in bucket_rows
        ]
        statement = insert(LiveCrossingBucket).values(values)
        database.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    LiveCrossingBucket.job_id,
                    LiveCrossingBucket.shop_id,
                    LiveCrossingBucket.bucket_index,
                ],
                set_={
                    key: getattr(statement.excluded, key)
                    for key in values[0]
                    if key not in {"job_id", "shop_id", "bucket_index", "session_id"}
                },
            )
        )
    state.capture_started_at = started_at
    state.elapsed_capture_seconds = (
        frame.timestamp_seconds if ending_capture_seconds is None else ending_capture_seconds
    )
    state.last_capture_sequence = frame.sequence
    state.last_analyzed_sequence = frame.sequence
    state.current_segment_index = frame.segment_index
    state.observed_seconds, state.missing_seconds = observed, missing
    state.coverage_complete = state.coverage_complete and missing == 0
    state.sample_candidates_seen = sampler.candidates_seen
    state.unconfirmed_crossings = counter.discarded_crossings
    state.revision, state.checkpoint_at = revision, now
    database.get(ProcessingJob, job_id).frames_analyzed = analyzed


def _live_context(database, job_id, shop_id):
    job = database.get(ProcessingJob, job_id)
    if (
        job is None
        or job.kind != JobKind.LIVE_ANALYSIS
        or (get_active_session(database, job.session_id) is None)
    ):
        raise LiveMachineError("not_found")
    state = database.get(LiveAnalysisState, job_id)
    source = database.get(LiveSource, job.session_id)
    if state is None or source is None:
        raise LiveMachineError("not_found")
    shops = list(
        database.scalars(
            select(SceneVersionShop)
            .where(SceneVersionShop.scene_version_id == job.scene_version_id)
            .order_by(SceneVersionShop.position)
        )
    )
    selected = (
        next((shop for shop in shops if shop.shop_id == shop_id), None)
        if shop_id
        else (shops[0] if shops else None)
    )
    if shop_id is not None and selected is None:
        raise LiveMachineError("not_found")
    return job, state, source, shops, selected


def mark_live_interrupted(database, job, *, reason, occurred_at):
    """Retain the last committed horizon; a crash does not prove the capture end."""
    state = database.scalar(
        select(LiveAnalysisState).where(LiveAnalysisState.job_id == job.id).with_for_update()
    )
    if state is None:
        return
    state.capture_status = "ended"
    state.coverage_complete = False
    state.unknown_tail = True
    state.capture_ended_at = None
    state.revision += 1
    state.checkpoint_at = occurred_at
    existing = database.scalar(
        select(LiveInterruption)
        .where(LiveInterruption.job_id == job.id, LiveInterruption.end_known.is_(False))
        .limit(1)
    )
    if existing is None:
        database.add(
            LiveInterruption(
                job_id=job.id,
                session_id=job.session_id,
                start_seconds=state.elapsed_capture_seconds,
                end_seconds=None,
                end_known=False,
                reason=reason,
            )
        )
    for row in database.scalars(
        select(LiveCaptureSegment).where(
            LiveCaptureSegment.job_id == job.id, LiveCaptureSegment.ended_capture_seconds.is_(None)
        )
    ):
        row.ended_capture_seconds = state.elapsed_capture_seconds
        row.last_sequence = state.last_analyzed_sequence
    for row in database.scalars(
        select(LiveCrossingBucket).where(
            LiveCrossingBucket.job_id == job.id, LiveCrossingBucket.is_open.is_(True)
        )
    ):
        state.unconfirmed_crossings += row.pending_count
        row.pending_count = 0
        row.is_open = False
        row.coverage_incomplete = True
        row.unknown_tail = True
        row.revision = state.revision


def _minute(row):
    return {
        "shop_id": str(row.shop_id),
        "bucket_index": row.bucket_index,
        "start_seconds": float(row.start_seconds),
        "end_seconds": float(row.end_seconds),
        "entries": row.entries,
        "exits": row.exits,
        "observed_seconds": float(row.observed_seconds),
        "missing_seconds": float(row.missing_seconds),
        "pending_count": row.pending_count,
        "is_open": row.is_open,
        "coverage_incomplete": row.coverage_incomplete,
        "unknown_tail": row.unknown_tail,
        "revision": row.revision,
    }


def load_live_results(database, job_id, *, shop_id=None, bucket_cursor=None):
    if not database.in_transaction():
        database.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    job, state, source, shops, selected = _live_context(database, job_id, shop_id)
    summary = None
    minutes = []
    if selected is not None:
        entries, exits = database.execute(
            select(
                func.coalesce(func.sum(LiveCrossingBucket.entries), 0),
                func.coalesce(func.sum(LiveCrossingBucket.exits), 0),
            ).where(
                LiveCrossingBucket.job_id == job_id, LiveCrossingBucket.shop_id == selected.shop_id
            )
        ).one()
        line = database.get(SceneEntryLine, selected.id)
        entries_are_a = line is not None and line.entry_direction.value == "a_to_b"
        summary = {
            "shop_id": str(selected.shop_id),
            "shop_name": selected.name,
            "entry_count": entries,
            "exit_count": exits,
            "a_to_b_count": entries if entries_are_a else exits,
            "b_to_a_count": exits if entries_are_a else entries,
            "total_crossings": entries + exits,
            "partial": not job.result_complete,
            "label_mode": source.label_mode,
            "entry_direction": None if line is None else line.entry_direction.value,
        }
        minutes = list(
            database.scalars(
                select(LiveCrossingBucket)
                .where(
                    LiveCrossingBucket.job_id == job_id,
                    LiveCrossingBucket.shop_id == selected.shop_id,
                    LiveCrossingBucket.bucket_index >= (bucket_cursor or 0),
                )
                .order_by(LiveCrossingBucket.bucket_index)
                .limit(251)
            )
        )
    next_cursor = minutes[249].bucket_index + 1 if len(minutes) > 250 else None
    interruptions = list(
        database.scalars(
            select(LiveInterruption)
            .where(LiveInterruption.job_id == job_id)
            .order_by(LiveInterruption.start_seconds, LiveInterruption.id)
        )
    )
    sample_count = database.scalar(
        select(func.count())
        .select_from(LivePositionSample)
        .where(LivePositionSample.job_id == job_id)
    )
    return {
        "job_id": str(job_id),
        "session_id": str(job.session_id),
        "source_kind": "webcam",
        "status": job.status.value,
        "capture_status": state.capture_status,
        "result_complete": job.result_complete,
        "coverage_complete": state.coverage_complete,
        "unknown_tail": state.unknown_tail,
        "capture_started_at": state.capture_started_at,
        "capture_ended_at": state.capture_ended_at,
        "elapsed_capture_seconds": float(state.elapsed_capture_seconds),
        "checkpoint_at": state.checkpoint_at,
        "revision": state.revision,
        "selected_shop_id": None if selected is None else str(selected.shop_id),
        "shops": [{"shop_id": str(shop.shop_id), "shop_name": shop.name} for shop in shops],
        "summary": summary,
        "minutes": [_minute(row) for row in minutes[:250]],
        "next_bucket_cursor": next_cursor,
        "interruptions": [
            {
                "id": str(row.id),
                "start_seconds": float(row.start_seconds),
                "end_seconds": None if row.end_seconds is None else float(row.end_seconds),
                "end_known": row.end_known,
                "reason": row.reason,
            }
            for row in interruptions
        ],
        "observed_seconds": float(state.observed_seconds),
        "missing_seconds": float(state.missing_seconds),
        "unconfirmed_crossings": state.unconfirmed_crossings,
        "sampling": {
            "time_basis": "capture",
            "sample_count": sample_count,
            "candidate_count": state.sample_candidates_seen,
            "capacity": state.sample_capacity,
        },
    }


def load_live_events(
    database, job_id, *, shop_id=None, from_seconds=None, to_seconds=None, cursor=None, limit=100
):
    if not database.in_transaction():
        database.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    job, state, _, _, selected = _live_context(database, job_id, shop_id)
    selected_id = None if selected is None else selected.shop_id
    context = {
        "job": str(job_id),
        "shop": None if selected_id is None else str(selected_id),
        "from": None if from_seconds is None else str(from_seconds),
        "to": None if to_seconds is None else str(to_seconds),
    }
    horizon, revision = state.elapsed_capture_seconds, state.revision
    after = None
    if cursor is not None:
        try:
            value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if not isinstance(value, dict) or any(
                value.get(key) != item for key, item in context.items()
            ):
                raise ValueError("Invalid cursor context")
            horizon = Decimal(value["h"])
            time_value = Decimal(value["t"])
            number, revision = value["n"], value["r"]
            if (
                not horizon.is_finite()
                or not time_value.is_finite()
                or not (0 <= time_value <= horizon <= state.elapsed_capture_seconds)
                or type(number) is not int
                or not 0 <= number < 2**63
                or (type(revision) is not int or not 0 <= revision <= state.revision)
            ):
                raise ValueError("Invalid cursor bounds")
            after = (time_value, number)
        except (ValueError, KeyError, TypeError, ArithmeticError):
            raise ValueError("invalid_cursor") from None
    query = select(LiveCrossing).where(
        LiveCrossing.job_id == job_id,
        LiveCrossing.shop_id == selected_id,
        LiveCrossing.confirmed_at_capture_seconds <= horizon,
    )
    if from_seconds is not None:
        query = query.where(LiveCrossing.capture_timestamp_seconds >= from_seconds)
    if to_seconds is not None:
        query = query.where(LiveCrossing.capture_timestamp_seconds <= to_seconds)
    if after is not None:
        query = query.where(
            or_(
                LiveCrossing.capture_timestamp_seconds > after[0],
                (LiveCrossing.capture_timestamp_seconds == after[0])
                & (LiveCrossing.candidate_sequence > after[1]),
            )
        )
    rows = list(
        database.scalars(
            query.order_by(
                LiveCrossing.capture_timestamp_seconds, LiveCrossing.candidate_sequence
            ).limit(limit + 1)
        )
    )
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        payload = {
            **context,
            "h": str(horizon),
            "r": revision,
            "t": str(last.capture_timestamp_seconds),
            "n": last.candidate_sequence,
        }
        next_cursor = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()
    return {
        "job_id": str(job_id),
        "session_id": str(job.session_id),
        "source_kind": "webcam",
        "selected_shop_id": None if selected_id is None else str(selected_id),
        "snapshot_revision": revision,
        "checkpoint_horizon_seconds": float(horizon),
        "events": [
            {
                "id": str(row.id),
                "segment_id": str(row.segment_id),
                "track_id": row.track_id,
                "candidate_sequence": row.candidate_sequence,
                "capture_sequence": row.capture_sequence,
                "capture_timestamp_seconds": float(row.capture_timestamp_seconds),
                "confirmed_at_capture_seconds": float(row.confirmed_at_capture_seconds),
                "direction": row.direction,
                "foot": [float(row.foot_x), float(row.foot_y)],
            }
            for row in rows[:limit]
        ],
        "next_cursor": next_cursor,
    }
