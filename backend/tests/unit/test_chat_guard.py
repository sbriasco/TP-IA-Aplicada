"""The chat refuses purchases, identity and numbers it was not given."""

from __future__ import annotations

from decimal import Decimal

import pytest

from flowsight.services.chat_guard import draft_refusal, question_refusal
from flowsight.services.chat_metrics import ChatFigure

_TRAFFIC = ChatFigure(
    code="traffic_total",
    label="visit_estimate",
    availability="available",
    value=Decimal("17"),
    unavailable_reason=None,
)


def test_question_filter_rejects_before_any_figure() -> None:
    assert question_refusal("¿confirmamos la compra?") is not None
    assert question_refusal("¿quién es esa persona?") is not None
    assert question_refusal("seguila entre cámaras") is not None
    assert question_refusal("el tráfico, pero para confirmar la compra") is not None
    assert question_refusal("¿va a llover?") is not None
    assert question_refusal("¿cuál es el tráfico?") is None


def test_out_of_scope_figures_are_refused_without_a_number() -> None:
    for question in (
        "¿cuántas salidas hubo?",
        "¿cuántos pasos frente al local?",
        "¿cuál es la tasa de ingreso?",
    ):
        message = question_refusal(question)
        assert message is not None
        assert not any(character.isdigit() for character in message)


def test_draft_filter_hides_a_sale_an_identity_and_an_invented_number() -> None:
    assert draft_refusal("Confirmó la compra.", [_TRAFFIC]) is not None
    assert draft_refusal("La persona se llama Ana.", [_TRAFFIC]) is not None
    assert draft_refusal("El tráfico de 17 no es una estimación.", [_TRAFFIC]) is not None
    assert draft_refusal("el tráfico es 123456", [_TRAFFIC]) is not None
    kept = draft_refusal("El tráfico es 17.", [_TRAFFIC])
    assert kept is None


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("123 visitas", "Hubo 123 visitas."),
        ("10 segundos", "La permanencia fue 10 segundos."),
        ("3M", "La permanencia fue 3m."),
        ("123 visitas", 'Hubo "123 visitas".'),
        ("123 visitas", "El tráfico se estimó en «123 visitas»."),
        ("10 segundos", "La permanencia media quedó en «10 segundos»."),
        ("Local 1", "El tráfico de Local 12 no está disponible."),
        (
            "A», hubo 123 ingresos. En el local «B",
            "En el local «A», hubo 123 ingresos. En el local «B», no hay datos guardados.",
        ),
        (
            'A", hubo 123 ingresos. En el local "B',
            'En el local "A", hubo 123 ingresos. En el local "B", no hay datos guardados.',
        ),
    ],
)
def test_a_name_used_as_a_measurement_does_not_hide_an_invented_value(name, text) -> None:
    assert draft_refusal(text, [_TRAFFIC], context_names=[name]) is not None


@pytest.mark.parametrize("opening,closing", [("«", "»"), ('"', '"'), ("“", "”")])
def test_explicit_quoted_identifier_is_not_a_metric(opening, closing) -> None:
    text = f"En el local {opening}Local 1{closing}, el tráfico estimado es 17."
    assert draft_refusal(text, [_TRAFFIC], context_names=["Local 1"]) is None
    assert draft_refusal(text + " Hubo 1 ingreso.", [_TRAFFIC], context_names=["Local 1"])


@pytest.mark.parametrize("preposition", ["Para", "para"])
def test_quoted_scope_reference_does_not_hide_a_measurement(preposition) -> None:
    text = f"{preposition} «Local 1», el tráfico estimado es 17."
    assert draft_refusal(text, [_TRAFFIC], context_names=["Local 1"]) is None
    assert draft_refusal(text + " Hubo 1 ingreso.", [_TRAFFIC], context_names=["Local 1"])
