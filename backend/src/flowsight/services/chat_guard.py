"""Refuse a question before any figure is read, and a draft before it is shown."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from decimal import Decimal

from flowsight.services.chat_metrics import ChatFigure

_NUMBER = re.compile(r"(?<!\d)[-−+]?\d+(?:[.,]\d+)?")
_PURCHASE = ("compra", "compro", "venta", "vender", "vendio", "ticket")
_PURCHASE_SOFT = (
    "posible compra",
    "posibles compra",
    "compra estimad",
    "compras estimad",
    "bolsa",
)
_IDENTITY = (
    "quien es esa persona",
    "quien es esta persona",
    "identidad de",
    "se llama",
    "su nombre",
    "cara",
    "rostro",
)
_CAMERAS = ("entre camaras", "otra camara", "seguirla", "seguirlo")
_SQL_VIDEO = (
    "sql",
    "select ",
    "frame a frame",
    "mirar el video",
    "exportar la base",
)
_ESTIMATE_AS_FACT = (
    "no es una estimacion",
    "visita real",
    "dato exacto",
    "no es estimada",
    "venta confirmada",
    "compro seguro",
    "es una venta",
)


def question_refusal(question: str) -> str | None:
    """Return a refusal with no digits, or None when the question may continue."""

    plain = _plain(question)
    # Product questions may explain a limitation; they are not requests to perform it.
    if re.match(
        r"^(?:[¿¡\s]*)(?:que |como |por que |puede flowsight|flowsight puede|se puede)", plain
    ):
        return None
    if any(word in plain for word in _SQL_VIDEO):
        return "No puedo ejecutar consultas libres ni analizar el video desde el chat."
    # Soft purchase questions (estimations) are allowed; hard confirmations are not.
    if any(word in plain for word in _PURCHASE) and not any(
        soft in plain for soft in _PURCHASE_SOFT
    ):
        return "No puedo confirmar una compra."
    if _has_identity_claim(plain) or re.search(
        r"\bidentifica\w* (?:a |esa |esta |la )persona", plain
    ):
        return "No puedo identificar a una persona."
    if any(word in plain for word in _CAMERAS):
        return "No puedo seguir a una persona entre cámaras."
    if any(
        word in plain for word in ("va a llover", "pronostico del tiempo", "precio del bitcoin")
    ):
        return "Puedo ayudarte con FlowSight, su uso y los análisis guardados."
    # Free language reaches the scoped assistant: an unknown phrasing is not a refusal.
    return None


def draft_refusal(
    text: str,
    figures: Sequence[ChatFigure],
    *,
    context_names: Sequence[str] = (),
    backed_values: Sequence[Decimal] = (),
) -> str | None:
    """Return a refusal when the draft must not be shown."""

    plain = _without_limit_explanations(_plain(text))
    if any(word in plain for word in _PURCHASE) and not any(
        soft in plain for soft in _PURCHASE_SOFT
    ):
        if "estim" not in plain and "posible" not in plain:
            return "No puedo mostrar esa respuesta."
    if _has_identity_claim(plain):
        return "No puedo mostrar esa respuesta."
    if any(phrase in plain for phrase in _ESTIMATE_AS_FACT):
        return "No puedo mostrar una estimación como si fuera una observación."
    numeric_text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    if not _numbers_are_backed(
        _without_context_names(numeric_text, context_names), figures, backed_values
    ):
        return "No puedo mostrar esa respuesta porque incluye un número que no está en las cifras."
    return None


def _has_identity_claim(plain: str) -> bool:
    return any(re.search(r"\b" + re.escape(word) + r"\b", plain) for word in _IDENTITY)


def _without_limit_explanations(plain: str) -> str:
    """Keep prohibitions from being mistaken for positive claims about a visitor."""
    plain = re.sub(
        r"\bno\s+(?:es|son|implica|significa|garantiza|representa|equivale a)\s+"
        r"(?:una?\s+)?(?:venta|compra)(?:\s+confirmada)?\b",
        "",
        plain,
    )
    return re.sub(
        r"\b(?:no|ni)\s+(?:(?:puede|puedo|permite)\s+)?"
        r"(?:confirma\w*|identifica\w*|reconoce\w*|reconocer|sigue|seguir)\s+"
        r"(?:(?:a|una|la|las|una? |esa|esta)\s+)*"
        r"(?:compras?|ventas?|personas?|identidades|rostros?|caras?|"
        r"personas entre camaras)\b",
        "",
        plain,
    )


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
            r"(?<!\w)(?:local|zona|sesi[oó]n|para)\s+"
            r"(?:(?:seleccionad[ao]|elegid[ao]|llamad[ao]|actual|abiert[ao])\s+)*"
            r"(?:" + quoted + r")(?!\w)",
            "",
            text,
            flags=re.IGNORECASE,
        )
    return text


def _numbers_are_backed(
    text: str, figures: Sequence[ChatFigure], backed_values: Sequence[Decimal] = ()
) -> bool:
    allowed: list[Decimal] = list(backed_values)
    percentages: list[Decimal] = []
    for figure in figures:
        if figure.availability != "available":
            continue
        if figure.value is not None:
            allowed.append(figure.value)
            code = figure.code.split("__", 1)[0]
            if code.endswith("_rate"):
                percent = figure.value * Decimal(100)
                percentages.extend((percent, percent.quantize(Decimal("0.01"))))
            elif code == "coverage_percent":
                percentages.append(figure.value)
        if figure.start_seconds is not None:
            allowed.append(figure.start_seconds)
        if figure.track_count is not None:
            allowed.append(Decimal(figure.track_count))
    valid_percentages = True

    def percentage(match: re.Match[str]) -> str:
        nonlocal valid_percentages
        value = Decimal(match.group(1).replace(",", ".").replace("−", "-"))
        if value not in percentages:
            valid_percentages = False
        return ""

    text = re.sub(r"(" + _NUMBER.pattern + r")\s*(?:%|por ciento)", percentage, text)
    if not valid_percentages:
        return False
    for raw in _NUMBER.findall(text):
        found = Decimal(raw.replace(",", ".").replace("−", "-"))
        if not any(found == value for value in allowed):
            return False
    return True


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
