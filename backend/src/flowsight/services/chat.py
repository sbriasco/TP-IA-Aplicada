"""Answer one chat question from stored figures. The drafter is replaceable."""

from __future__ import annotations

import json
import logging
import time
import unicodedata
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from flowsight.core.config import Settings
from flowsight.db.models import ProcessingJob, SceneVersionShop
from flowsight.llm.client import build_client
from flowsight.llm.settings import AzureLlmConfigurationError, load_azure_llm_settings
from flowsight.services.chat_guard import draft_refusal, question_refusal
from flowsight.services.chat_metrics import AnalysisNotFinal, ChatFigure, read_figures
from flowsight.services.processed_sessions import ProcessedSessionRow, list_processed_sessions
from flowsight.services.scene_metrics import ShopNotInSession
from flowsight.services.sessions import get_active_session

logger = logging.getLogger(__name__)
MAX_MODEL_CALLS = 2
MAX_COMPLETION_TOKENS = 2048


class SessionMissing(Exception):
    """The requested session does not exist."""


@dataclass(frozen=True)
class Draft:
    text: str
    model_calls: int


@dataclass(frozen=True)
class ChatAnswer:
    status: str
    message: str
    session_id: uuid.UUID | None
    shop_id: uuid.UUID | None
    shop_name: str | None
    scope: str | None
    figures: list[ChatFigure]
    model_calls: int


Drafter = Callable[..., Draft]


def ask(
    database_session: DatabaseSession,
    *,
    session_id: uuid.UUID,
    shop_id: uuid.UUID | None,
    question: str,
    timeout_seconds: float,
    settings: Settings,
    drafter: Drafter | None = None,
) -> ChatAnswer:
    """Cite the open session and shop. A stretch in the question does not change figures."""

    if get_active_session(database_session, session_id) is None:
        raise SessionMissing
    refusal = question_refusal(question)
    if refusal is not None:
        _log(0, "refused")
        return _answer("refused", refusal, session_id=session_id, shop_id=shop_id)
    rows = list_processed_sessions(database_session, settings)
    catalog = _catalog(rows)
    session_id, stop = _resolve_session(question, session_id, rows)
    if stop == "empty":
        _log(0, "no_processed_sessions")
        return _answer("unavailable", "No hay sesiones procesadas.")
    if stop == "ambiguous":
        _log(0, "ambiguous_session")
        return _answer(
            "needs_clarification",
            "Hay más de una sesión con ese nombre. Decime cuál.",
        )
    if shop_id is None:
        _log(0, "needs_shop")
        return _answer(
            "needs_clarification",
            "Decime de qué local es la pregunta.",
            session_id=session_id,
        )
    try:
        figures = read_figures(database_session, session_id, shop_id)
    except AnalysisNotFinal:
        _log(0, "result_incomplete")
        return _answer(
            "unavailable",
            "No hay un resultado final para esta sesión.",
            session_id=session_id,
            shop_id=shop_id,
        )
    except ShopNotInSession:
        raise
    shop_name = _shop_name(database_session, session_id, shop_id)
    writer = drafter or azure_draft
    try:
        draft = _within_timeout(
            writer,
            timeout_seconds,
            question=question,
            figures=figures,
            shop_name=shop_name or "",
            sessions=catalog,
        )
    except AzureLlmConfigurationError:
        _log(0, "not_configured")
        return _answer(
            "error",
            "El servicio de redacción no está configurado.",
            session_id=session_id,
            shop_id=shop_id,
            shop_name=shop_name,
        )
    except TimeoutError:
        _log(0, "timeout")
        return _answer(
            "error",
            "La pregunta tardó demasiado. Podés volver a intentar.",
            session_id=session_id,
            shop_id=shop_id,
            shop_name=shop_name,
        )
    except Exception:
        _log(0, "drafter_failed")
        return _answer(
            "error",
            "No se pudo redactar la respuesta.",
            session_id=session_id,
            shop_id=shop_id,
            shop_name=shop_name,
        )
    calls = min(MAX_MODEL_CALLS, max(0, draft.model_calls))
    if not draft.text.strip():
        _log(calls, "empty_content")
        return _answer(
            "error",
            "El servicio de redacción no devolvió una respuesta.",
            session_id=session_id,
            shop_id=shop_id,
            shop_name=shop_name,
            model_calls=calls,
        )
    hidden = draft_refusal(draft.text, figures)
    if hidden is not None:
        _log(calls, "draft_refused")
        return _answer(
            "refused",
            hidden,
            session_id=session_id,
            shop_id=shop_id,
            shop_name=shop_name,
        )
    _log(calls, None)
    return _answer(
        "answered",
        draft.text.strip(),
        session_id=session_id,
        shop_id=shop_id,
        shop_name=shop_name,
        scope="whole_session",
        figures=figures,
        model_calls=calls,
    )


def _resolve_session(
    question: str, open_id: uuid.UUID, rows: list[ProcessedSessionRow]
) -> tuple[uuid.UUID, str | None]:
    """The open session wins unless the question says the latest one or a name."""

    if "ultima" in _fold(question):
        if not rows:
            return open_id, "empty"
        chosen = max(rows, key=lambda row: (_stamp(row.finished_at), row.job_id.int))
        return chosen.session_id, None
    matches = _name_matches(question, rows)
    if len(matches) > 1:
        return open_id, "ambiguous"
    if len(matches) == 1:
        return matches[0].session_id, None
    return open_id, None


def _name_matches(question: str, rows: list[ProcessedSessionRow]) -> list[ProcessedSessionRow]:
    plain = _fold(question)
    hits = [row for row in rows if row.name and _fold(row.name) in plain]
    if not hits:
        return []
    longest = max(len(_fold(row.name)) for row in hits)
    return [row for row in hits if len(_fold(row.name)) == longest]


def _catalog(rows: list[ProcessedSessionRow]) -> list[dict[str, object]]:
    return [
        {
            "session_id": str(row.session_id),
            "name": row.name,
            "finished_at": None if row.finished_at is None else row.finished_at.isoformat(),
            "result_complete": row.result_complete,
        }
        for row in rows
    ]


def _stamp(moment: datetime | None) -> datetime:
    if moment is None:
        return datetime.min.replace(tzinfo=UTC)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")


def suite_drafter(
    *,
    question: str,
    figures: list[ChatFigure],
    shop_name: str | None,
    timeout_seconds: float,
    sessions: list[dict[str, object]] | None = None,
) -> Draft:
    """Cite the traffic figure already loaded. Used by the e2e suite, never by Azure."""

    del question, shop_name, timeout_seconds, sessions
    traffic = next((figure for figure in figures if figure.code == "traffic_total"), None)
    if traffic is None or traffic.value is None:
        return Draft(text="El tráfico no está disponible.", model_calls=1)
    shown = format(traffic.value, "f")
    if "." in shown:
        shown = shown.rstrip("0").rstrip(".")
    return Draft(text=f"El tráfico es {shown or '0'}.", model_calls=1)


def azure_draft(
    *,
    question: str,
    figures: list[ChatFigure],
    shop_name: str,
    timeout_seconds: float,
    sessions: list[dict[str, object]] | None = None,
) -> Draft:
    """Two rounds at most, using the Foundry client already validated in specs/003."""

    client, resolved = build_client(load_azure_llm_settings())
    payload = json.dumps(_public_figures(figures), ensure_ascii=False)
    listing = json.dumps(sessions or [], ensure_ascii=False)
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": (
                f"Respondé en español sobre el local {shop_name}. "
                "Las cifras son de toda la sesión. No inventes números. "
                "Si falta una cifra, pedí get_session_figures. "
                f"Sesiones, sin cifras: {listing}."
            ),
        },
        {"role": "user", "content": question},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_session_figures",
                "description": "Cifras ya registradas de toda la sesión para el local elegido.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        }
    ]
    started = time.monotonic()
    calls = 0
    text = ""
    for _ in range(MAX_MODEL_CALLS):
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError
        calls += 1
        completion = client.chat.completions.create(
            model=resolved.deployment,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            # Includes hidden reasoning as well as visible answer tokens.
            max_completion_tokens=MAX_COMPLETION_TOKENS,
            reasoning_effort="low",
            timeout=remaining,
        )
        message = completion.choices[0].message
        tool_calls = message.tool_calls or []
        if not tool_calls:
            text = (message.content or "").strip()
            return Draft(text, calls)
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            }
        )
        for call in tool_calls:
            known = call.function.name == "get_session_figures"
            content = payload if known else '{"error":"unknown_tool"}'
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    return Draft(text, calls)


def _within_timeout(drafter: Drafter, timeout_seconds: float, **kwargs: object) -> Draft:
    kwargs["timeout_seconds"] = timeout_seconds
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(drafter, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as error:
        raise TimeoutError from error
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _public_figures(figures: list[ChatFigure]) -> list[dict[str, object]]:
    return [
        {
            "code": figure.code,
            "label": figure.label,
            "availability": figure.availability,
            "value": None if figure.value is None else str(figure.value),
            "unavailable_reason": figure.unavailable_reason,
            "start_seconds": None if figure.start_seconds is None else str(figure.start_seconds),
            "track_count": figure.track_count,
        }
        for figure in figures
    ]


def _shop_name(
    database_session: DatabaseSession, session_id: uuid.UUID, shop_id: uuid.UUID
) -> str | None:
    job = database_session.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.session_id == session_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    if job is None or job.scene_version_id is None:
        return None
    return database_session.scalar(
        select(SceneVersionShop.name).where(
            SceneVersionShop.scene_version_id == job.scene_version_id,
            SceneVersionShop.shop_id == shop_id,
        )
    )


def _answer(
    status: str,
    message: str,
    *,
    session_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    shop_name: str | None = None,
    scope: str | None = None,
    figures: list[ChatFigure] | None = None,
    model_calls: int = 0,
) -> ChatAnswer:
    return ChatAnswer(
        status=status,
        message=message,
        session_id=session_id,
        shop_id=shop_id,
        shop_name=shop_name,
        scope=scope,
        figures=figures or [],
        model_calls=model_calls,
    )


def _log(model_calls: int, error_code: str | None) -> None:
    logger.info("chat_call count=%s error_code=%s", model_calls, error_code or "none")
