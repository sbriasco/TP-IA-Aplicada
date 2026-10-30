"""Persist and load chat threads for follow-up history."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.db.models import ChatMessage, ChatThread

HISTORY_MESSAGE_LIMIT = 20
_TITLE_MAX = 80


class ThreadMissing(Exception):
    """The thread does not exist, is deleted, or belongs to another session."""


@dataclass(frozen=True)
class ThreadSummary:
    id: uuid.UUID
    session_id: uuid.UUID
    shop_id: uuid.UUID | None
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredMessage:
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    answer_payload: dict[str, Any] | None


@dataclass(frozen=True)
class ThreadDetail:
    summary: ThreadSummary
    messages: list[StoredMessage]


def list_threads(database_session: DatabaseSession, session_id: uuid.UUID) -> list[ThreadSummary]:
    rows = database_session.scalars(
        select(ChatThread)
        .where(
            ChatThread.session_id == session_id,
            ChatThread.deleted_at.is_(None),
        )
        .order_by(ChatThread.updated_at.desc())
    ).all()
    return [_summary(row) for row in rows]


def get_thread(
    database_session: DatabaseSession,
    thread_id: uuid.UUID,
    *,
    session_id: uuid.UUID | None = None,
) -> ThreadDetail:
    thread = database_session.get(ChatThread, thread_id)
    if thread is None or thread.deleted_at is not None:
        raise ThreadMissing
    if session_id is not None and thread.session_id != session_id:
        raise ThreadMissing
    messages = database_session.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return ThreadDetail(
        summary=_summary(thread),
        messages=[
            StoredMessage(
                id=row.id,
                role=row.role,
                content=row.content,
                created_at=row.created_at,
                answer_payload=_loads_payload(row.answer_payload),
            )
            for row in messages
        ],
    )


def resolve_thread(
    database_session: DatabaseSession,
    *,
    session_id: uuid.UUID,
    shop_id: uuid.UUID | None,
    thread_id: uuid.UUID | None,
    question: str,
) -> ChatThread:
    """Return an existing thread or create one. Rejects cross-session / deleted ids."""

    if thread_id is None:
        return _create_thread(database_session, session_id=session_id, shop_id=shop_id, question=question)
    thread = database_session.get(ChatThread, thread_id)
    if thread is None or thread.deleted_at is not None or thread.session_id != session_id:
        raise ThreadMissing
    if shop_id is not None and thread.shop_id is not None and thread.shop_id != shop_id:
        raise ThreadMissing
    if thread.shop_id is None and shop_id is not None:
        thread.shop_id = shop_id
    return thread


def history_for_model(database_session: DatabaseSession, thread_id: uuid.UUID) -> list[dict[str, str]]:
    messages = database_session.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    clipped = messages[-HISTORY_MESSAGE_LIMIT:]
    return [{"role": row.role, "content": row.content} for row in clipped]


def append_turn(
    database_session: DatabaseSession,
    thread: ChatThread,
    *,
    question: str,
    answer_message: str,
    answer_payload: dict[str, Any] | None,
) -> None:
    now = datetime.now(UTC)
    database_session.add(
        ChatMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            role="user",
            content=question,
            created_at=now,
            answer_payload=None,
        )
    )
    database_session.add(
        ChatMessage(
            id=uuid.uuid4(),
            thread_id=thread.id,
            role="assistant",
            content=answer_message,
            created_at=now,
            answer_payload=(
                None
                if answer_payload is None
                else json.dumps(answer_payload, ensure_ascii=False)
            ),
        )
    )
    thread.updated_at = now
    if thread.title == "Nueva conversación":
        thread.title = _title_from_question(question)
    database_session.flush()


def soft_delete_thread(database_session: DatabaseSession, thread_id: uuid.UUID, session_id: uuid.UUID) -> None:
    thread = database_session.get(ChatThread, thread_id)
    if thread is None or thread.deleted_at is not None or thread.session_id != session_id:
        raise ThreadMissing
    thread.deleted_at = datetime.now(UTC)
    thread.updated_at = thread.deleted_at
    database_session.flush()


def _create_thread(
    database_session: DatabaseSession,
    *,
    session_id: uuid.UUID,
    shop_id: uuid.UUID | None,
    question: str,
) -> ChatThread:
    now = datetime.now(UTC)
    thread = ChatThread(
        id=uuid.uuid4(),
        session_id=session_id,
        shop_id=shop_id,
        title=_title_from_question(question),
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    database_session.add(thread)
    database_session.flush()
    return thread


def _title_from_question(question: str) -> str:
    plain = " ".join(question.strip().split())
    if not plain:
        return "Nueva conversación"
    if len(plain) <= _TITLE_MAX:
        return plain
    return plain[: _TITLE_MAX - 1].rstrip() + "…"


def _summary(row: ChatThread) -> ThreadSummary:
    return ThreadSummary(
        id=row.id,
        session_id=row.session_id,
        shop_id=row.shop_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _loads_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None
