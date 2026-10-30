"""Contrast session resolution and axis cues for the expanded chat."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from flowsight.services.chat import (
    _resolve_axis,
    _resolve_contrast_sessions,
    _wants_comparison,
)
from flowsight.services.processed_sessions import ProcessedSessionRow


def _row(name: str, *, finished: datetime, session_id: uuid.UUID | None = None):
    return ProcessedSessionRow(
        session_id=session_id or uuid.uuid4(),
        name=name,
        video_filename=None,
        video_availability=None,
        job_id=uuid.uuid4(),
        status="completed",
        finished_at=finished,
        failure_code=None,
        failure_message=None,
        scene_version_id=None,
        version_number=None,
        result_complete=True,
        source_kind="synthetic",
    )


def test_wants_comparison_cues():
    assert _wants_comparison("¿cuál sesión tuvo más tráfico que la última?")
    assert _wants_comparison("compará A y B")
    assert not _wants_comparison("¿cuál es el tráfico?")


def test_resolve_axis_from_question():
    assert _resolve_axis("compará por día") == "day"
    assert _resolve_axis("contraste por franja horaria") == "time_of_day"
    assert _resolve_axis("compará por zona") == "zone"
    assert _resolve_axis("cuál tuvo más tráfico") == "session"


def test_contrast_needs_pair_without_other_session():
    open_id = uuid.uuid4()
    rows = [
        _row("Solo", finished=datetime(2026, 9, 1, tzinfo=UTC), session_id=open_id),
    ]
    ids, stop = _resolve_contrast_sessions("compará el tráfico", open_id, rows)
    assert stop == "need_pair"
    assert ids == [open_id]


def test_contrast_open_plus_ultima():
    open_id = uuid.uuid4()
    other = uuid.uuid4()
    rows = [
        _row("Abierta", finished=datetime(2026, 9, 1, tzinfo=UTC), session_id=open_id),
        _row("Nueva", finished=datetime(2026, 9, 2, tzinfo=UTC), session_id=other),
    ]
    ids, stop = _resolve_contrast_sessions(
        "compará con la última el tráfico", open_id, rows
    )
    assert stop is None
    assert ids == [open_id, other]
