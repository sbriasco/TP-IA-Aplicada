"""Persist and read one shop funnel. The figures are computed before this module runs."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import (
    MeasureAvailability,
    ProcessingJob,
    ShopFunnel,
    ShopFunnelLabel,
    ShopFunnelRate,
    ShopFunnelRateCode,
    ShopFunnelStage,
    ShopFunnelStageCode,
    SourceKind,
)
from flowsight.services.scene_metrics import _completed_job, _require_shop
from flowsight.services.sessions import get_active_session
from flowsight.vision.events import SceneEventFact
from flowsight.vision.funnel import (
    ATTENTION_THRESHOLD_SECONDS,
    STOP_THRESHOLD_SECONDS,
    FunnelDraft,
    build_funnel,
)

_STAGE_ORDER = (
    "observed_pass",
    "exposure",
    "stop",
    "attention",
    "linked_entry",
)
_RATE_ORDER = (
    "observed_pass_to_exposure",
    "exposure_to_stop",
    "stop_to_attention",
    "attention_to_linked_entry",
)


class LiveFunnelUnavailable(Exception):
    """A webcam session has no commercial funnel."""


@dataclass(frozen=True)
class FunnelView:
    job_id: uuid.UUID
    session_id: uuid.UUID
    shop_id: uuid.UUID
    stop_threshold_seconds: Decimal
    attention_threshold_seconds: Decimal
    excluded_window_only: int
    precision_uncommitted: bool
    stages: tuple[ShopFunnelStage, ...]
    rates: tuple[ShopFunnelRate, ...]


def persist_shop_funnel(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    events: Sequence[SceneEventFact],
    fps: float,
    windows: dict[uuid.UUID, bool],
    source_kind: str,
) -> None:
    """Store one funnel per shop. A webcam source stores nothing."""

    if source_kind == SourceKind.WEBCAM.value:
        return
    for shop_id, window_configured in windows.items():
        draft = build_funnel(
            events, shop_id=shop_id, window_configured=window_configured, fps=fps
        )
        _insert(
            database_session,
            job_id=job_id,
            session_id=session_id,
            shop_id=shop_id,
            draft=draft,
        )


def load_shop_funnel(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> FunnelView:
    session = get_active_session(database_session, session_id)
    if session is not None and session.source_kind is SourceKind.WEBCAM:
        raise LiveFunnelUnavailable
    job = _completed_job(database_session, session_id)
    _require_shop(database_session, job, shop_id)
    header = database_session.scalar(
        select(ShopFunnel).where(ShopFunnel.job_id == job.id, ShopFunnel.shop_id == shop_id)
    )
    if header is None:
        return _missing(job, shop_id)
    stages = database_session.scalars(
        select(ShopFunnelStage).where(
            ShopFunnelStage.job_id == job.id, ShopFunnelStage.shop_id == shop_id
        )
    ).all()
    rates = database_session.scalars(
        select(ShopFunnelRate).where(
            ShopFunnelRate.job_id == job.id, ShopFunnelRate.shop_id == shop_id
        )
    ).all()
    by_stage = {row.stage.value: row for row in stages}
    by_rate = {row.code.value: row for row in rates}
    return FunnelView(
        job_id=job.id,
        session_id=session_id,
        shop_id=shop_id,
        stop_threshold_seconds=header.stop_threshold_seconds,
        attention_threshold_seconds=header.attention_threshold_seconds,
        excluded_window_only=header.excluded_window_only,
        precision_uncommitted=header.precision_uncommitted,
        stages=tuple(by_stage[code] for code in _STAGE_ORDER),
        rates=tuple(by_rate[code] for code in _RATE_ORDER),
    )


def _insert(
    database_session: DatabaseSession,
    *,
    job_id: uuid.UUID,
    session_id: uuid.UUID,
    shop_id: uuid.UUID,
    draft: FunnelDraft,
) -> None:
    database_session.add(
        ShopFunnel(
            job_id=job_id,
            session_id=session_id,
            shop_id=shop_id,
            stop_threshold_seconds=draft.stop_threshold_seconds,
            attention_threshold_seconds=draft.attention_threshold_seconds,
            excluded_window_only=draft.excluded_window_only,
            precision_uncommitted=True,
        )
    )
    database_session.flush()
    for stage in draft.stages:
        database_session.add(
            ShopFunnelStage(
                job_id=job_id,
                session_id=session_id,
                shop_id=shop_id,
                stage=ShopFunnelStageCode(stage.stage),
                count=stage.count,
                availability=MeasureAvailability(stage.availability),
                label=ShopFunnelLabel(stage.label),
                unavailable_reason=stage.unavailable_reason,
            )
        )
    for rate in draft.rates:
        database_session.add(
            ShopFunnelRate(
                job_id=job_id,
                session_id=session_id,
                shop_id=shop_id,
                code=ShopFunnelRateCode(rate.code),
                value=rate.value,
                availability=MeasureAvailability(rate.availability),
                unavailable_reason=rate.unavailable_reason,
            )
        )


def _missing(job: ProcessingJob, shop_id: uuid.UUID) -> FunnelView:
    """Keep a completed job readable when its funnel rows were never stored.

    The stage contract only allows ``no_showcase`` or null. Missing rows are
    not a missing showcase, so the reason stays null.
    """

    stages = tuple(
        ShopFunnelStage(
            job_id=job.id,
            session_id=job.session_id,
            shop_id=shop_id,
            stage=ShopFunnelStageCode(code),
            count=None,
            availability=MeasureAvailability.UNAVAILABLE,
            label=ShopFunnelLabel.NONE,
            unavailable_reason=None,
        )
        for code in _STAGE_ORDER
    )
    rates = tuple(
        ShopFunnelRate(
            job_id=job.id,
            session_id=job.session_id,
            shop_id=shop_id,
            code=ShopFunnelRateCode(code),
            value=None,
            availability=MeasureAvailability.UNAVAILABLE,
            unavailable_reason=None,
        )
        for code in _RATE_ORDER
    )
    return FunnelView(
        job_id=job.id,
        session_id=job.session_id,
        shop_id=shop_id,
        stop_threshold_seconds=STOP_THRESHOLD_SECONDS,
        attention_threshold_seconds=ATTENTION_THRESHOLD_SECONDS,
        excluded_window_only=0,
        precision_uncommitted=True,
        stages=stages,
        rates=rates,
    )
