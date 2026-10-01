"""Refuse a question before any figure is read, and a draft before it is shown."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from decimal import Decimal

from flowsight.services.chat_metrics import ChatFigure

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_PURCHASE = ("compra", "compro", "venta", "vender", "vendio", "ticket")
_IDENTITY = ("quien es", "identificar", "identidad", "se llama", "su nombre", "cara", "rostro")
_CAMERAS = ("entre camaras", "otra camara", "seguirla", "seguirlo")
_OUT_OF_SCOPE = (
    ("salida", "No puedo citar salidas."),
    ("pasos", "No puedo citar pasos."),
    ("paso frente", "No puedo citar pasos."),
    ("tasa", "No puedo citar la tasa de ingreso."),
    ("flujo", "No puedo citar el detalle del flujo."),
)
_ALLOWED = (
    "trafico",
    "visita",
    "ingreso",
    "entrada",
    "ocupacion",
    "permanencia",
    "pico",
    "horario",
    "sesion",
    "local",
    "ultima",
)
_ESTIMATE_AS_FACT = ("no es una estimacion", "visita real", "dato exacto", "no es estimada")


def question_refusal(question: str) -> str | None:
    """Return a refusal with no digits, or None when the question may continue."""

    plain = _plain(question)
    if any(word in plain for word in _PURCHASE):
        return "No puedo confirmar una compra."
    if any(word in plain for word in _IDENTITY):
        return "No puedo identificar a una persona."
    if any(word in plain for word in _CAMERAS):
        return "No puedo seguir a una persona entre cámaras."
    for word, message in _OUT_OF_SCOPE:
        if word in plain:
            return message
    if any(word in plain for word in _ALLOWED):
        return None
    return (
        "Solo puedo hablar del tráfico, los ingresos, la ocupación, "
        "la permanencia y el horario pico."
    )


def draft_refusal(
    text: str, figures: Sequence[ChatFigure], *, context_names: Sequence[str] = ()
) -> str | None:
    """Return a refusal when the draft must not be shown."""

    plain = _plain(text)
    if any(word in plain for word in _PURCHASE):
        return "No puedo mostrar esa respuesta."
    if any(word in plain for word in _IDENTITY):
        return "No puedo mostrar esa respuesta."
    if any(phrase in plain for phrase in _ESTIMATE_AS_FACT):
        return "No puedo mostrar una estimación como si fuera una observación."
    if not _numbers_are_backed(_without_context_names(text, context_names), figures):
        return "No puedo mostrar esa respuesta porque incluye un número que no está en las cifras."
    return None


def _without_context_names(text: str, names: Sequence[str]) -> str:
    """Ignore explicitly quoted identifiers, never names used as measurements."""

    for name in sorted(set(names), key=len, reverse=True):
        if any(character in name for character in '«»"“”') or not name.isprintable():
            continue
        quoted = "|".join(
            re.escape(opening + name + closing)
            for opening, closing in (("«", "»"), ('"', '"'), ("“", "”"))
        )
        text = re.sub(
            r"(?<!\w)(?:local|sesi[oó]n|para)\s+(?:" + quoted + r")(?!\w)",
            "", text, flags=re.IGNORECASE,
        )
    return text


def _numbers_are_backed(text: str, figures: Sequence[ChatFigure]) -> bool:
    allowed: list[Decimal] = []
    for figure in figures:
        if figure.value is not None:
            allowed.append(figure.value)
        if figure.start_seconds is not None:
            allowed.append(figure.start_seconds)
        if figure.track_count is not None:
            allowed.append(Decimal(figure.track_count))
    for raw in _NUMBER.findall(text):
        found = Decimal(raw.replace(",", "."))
        if not any(found == value for value in allowed):
            return False
    return True


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
