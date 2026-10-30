"""Unit tests for chat thread persistence helpers."""

from __future__ import annotations

import uuid

import pytest
from conftest import prepare_empty_schema
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from flowsight.db.models import Session, SourceKind
from flowsight.services.cameras import get_or_create_camera
from flowsight.services.chat_threads import (
    ThreadMissing,
    append_turn,
    get_thread,
    history_for_model,
    list_threads,
    resolve_thread,
)


@pytest.fixture()
def database():
    url = prepare_empty_schema()
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


def _session(database) -> uuid.UUID:
    camera = get_or_create_camera(database, "cam-chat-thread")
    row = Session(
        name="Sesión hilo",
        camera_id=camera.name,
        registered_camera_id=camera.id,
        source_kind=SourceKind.SYNTHETIC,
    )
    database.add(row)
    database.commit()
    return row.id


def test_resolve_creates_and_lists_thread(database) -> None:
    session_id = _session(database)
    shop_id = uuid.uuid4()
    thread = resolve_thread(
        database,
        session_id=session_id,
        shop_id=shop_id,
        thread_id=None,
        question="¿Cuál fue el tráfico?",
    )
    database.commit()
    assert "tráfico" in thread.title.casefold()
    listed = list_threads(database, session_id)
    assert len(listed) == 1
    assert listed[0].id == thread.id


def test_append_and_history_for_model(database) -> None:
    session_id = _session(database)
    thread = resolve_thread(
        database,
        session_id=session_id,
        shop_id=None,
        thread_id=None,
        question="tráfico",
    )
    append_turn(
        database,
        thread,
        question="tráfico",
        answer_message="El tráfico es 17.",
        answer_payload={"status": "answered", "message": "El tráfico es 17."},
    )
    database.commit()
    history = history_for_model(database, thread.id)
    assert history == [
        {"role": "user", "content": "tráfico"},
        {"role": "assistant", "content": "El tráfico es 17."},
    ]
    detail = get_thread(database, thread.id, session_id=session_id)
    assert len(detail.messages) == 2


def test_wrong_session_raises(database) -> None:
    session_id = _session(database)
    thread = resolve_thread(
        database,
        session_id=session_id,
        shop_id=None,
        thread_id=None,
        question="hola",
    )
    database.commit()
    with pytest.raises(ThreadMissing):
        resolve_thread(
            database,
            session_id=uuid.uuid4(),
            shop_id=None,
            thread_id=thread.id,
            question="otra",
        )
