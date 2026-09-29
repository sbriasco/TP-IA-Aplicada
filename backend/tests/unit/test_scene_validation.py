"""Rule tests for the pure scene validation module (specs/004, T024 -> T030).

Contract assumed by these tests (T030, data-model "Validación al guardar una versión",
contracts/openapi.yaml ``ShopInput``):

- ``validate_scene(shops_input, frame_width, frame_height) -> (errors, warnings)``
  lives in ``flowsight.scene.validation``; both results are lists of ``SceneIssue``.
- ``shops_input`` is a list of plain dicts with the JSON shape of ``ShopInput``
  (what ``SceneVersionCreate.model_dump()["shops"]`` gives)::

      {
          "shop_id": "<uuid str>" | None,            # optional key
          "name": "Local A",
          "zones": {"front": [[x, y], ...],          # keyed by role; each role at most once
                    "interior": [[x, y], ...],       # optional
                    "showcase": [[x, y], ...]},      # optional
          "entry_line": {"start": [x, y], "end": [x, y], "entry_direction": "a_to_b"} | None,
      }

  Points are normalized ``[x, y]`` pairs. Range is NOT checked by Pydantic (T031):
  a coordinate outside [0, 1] must come back as an ``out_of_range`` issue, never as
  an exception.
- ``SceneIssue`` is a dataclass with ``rule``, ``element`` (``version``, ``shop``,
  ``zone:front``, ``zone:interior``, ``zone:showcase`` or ``entry_line``),
  ``shop_index`` (position in ``shops_input``; ``None`` for the version),
  ``shop_name`` (``None`` for the version) and a non-empty Spanish ``message`` that
  names the shop when there is one. The exact text is not fixed here.
- Every error is returned, not only the first one (FR-021). Warnings
  (``line_not_touching_zones``, ``zones_overlap``) never block and never show up
  in ``errors``.
- An element whose vertex count is out of bounds (< 3) is not measured any further
  (area, gaps and self intersection are undefined), so it yields a single issue.
- For duplicates (name or ``shop_id``) the issue points at the repeated occurrence,
  i.e. the later shop in the request.
- Rules that need the database (``shop_other_camera``, ``reference_*``,
  ``newer_version_exists``) belong to the service (T032) and are not tested here.

Test frame: 1000x500 px, as in ``test_scene_geometry.py``. Every fixture starts
from ``_valid_shops()`` and changes a single thing.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from flowsight.scene.validation import SceneIssue, validate_scene

FRAME_W = 1000
FRAME_H = 500

Shop = dict[str, Any]


def _n(x_px: float, y_px: float) -> list[float]:
    """Normalized ``[x, y]`` for a pixel position in the 1000x500 test frame."""

    return [x_px / FRAME_W, y_px / FRAME_H]


def _rect(x: float, y: float, width: float, height: float) -> list[list[float]]:
    """Normalized rectangle, clockwise on screen, from pixel position and size."""

    return [_n(x, y), _n(x + width, y), _n(x + width, y + height), _n(x, y + height)]


def _line(start_px: tuple[float, float], end_px: tuple[float, float]) -> dict[str, Any]:
    return {"start": _n(*start_px), "end": _n(*end_px), "entry_direction": "a_to_b"}


def _valid_shops() -> list[Shop]:
    """Two shops, far apart, whose entry line lies on the front/interior border.

    Shop 0 "Local A": front (100,100)-(300,200), interior (100,200)-(300,350),
    showcase (310,100)-(390,200), line (120,200)-(280,200).
    Shop 1 "Local B": front (600,100)-(800,200), interior (600,200)-(800,350),
    line (620,200)-(780,200).
    """

    return [
        {
            "shop_id": None,
            "name": "Local A",
            "zones": {
                "front": _rect(100, 100, 200, 100),
                "interior": _rect(100, 200, 200, 150),
                "showcase": _rect(310, 100, 80, 100),
            },
            "entry_line": _line((120, 200), (280, 200)),
        },
        {
            "shop_id": "7b0f3c1e-2d4a-4f7e-9a51-0c6a1d2b3e41",
            "name": "Local B",
            "zones": {
                "front": _rect(600, 100, 200, 100),
                "interior": _rect(600, 200, 200, 150),
            },
            "entry_line": _line((620, 200), (780, 200)),
        },
    ]


def _validate(shops: list[Shop]) -> tuple[list[SceneIssue], list[SceneIssue]]:
    errors, warnings = validate_scene(shops, FRAME_W, FRAME_H)
    return list(errors), list(warnings)


def _assert_single_error(
    shops: list[Shop],
    *,
    rule: str,
    element: str,
    shop_index: int | None,
    shop_name: str | None,
) -> SceneIssue:
    errors, _ = _validate(shops)

    assert [(issue.rule, issue.element, issue.shop_index) for issue in errors] == [
        (rule, element, shop_index)
    ]
    issue = errors[0]
    assert isinstance(issue, SceneIssue)
    assert issue.shop_name == shop_name
    assert issue.message.strip()
    if shop_name is not None:
        assert shop_name.strip() in issue.message
    return issue


# --- Valid baseline --------------------------------------------------------------


def test_valid_scene_has_no_errors_and_no_warnings() -> None:
    errors, warnings = _validate(_valid_shops())

    assert errors == []
    assert warnings == []


def test_zones_of_the_same_shop_may_overlap_without_warning() -> None:
    shops = _valid_shops()
    shops[0]["zones"]["interior"] = _rect(100, 150, 200, 200)

    errors, warnings = _validate(shops)

    assert errors == []
    assert warnings == []


def test_validation_does_not_mutate_the_input() -> None:
    shops = _valid_shops()
    snapshot = _valid_shops()

    _validate(shops)

    assert shops == snapshot


# --- Structural errors -----------------------------------------------------------


def test_no_shops() -> None:
    _assert_single_error([], rule="no_shops", element="version", shop_index=None, shop_name=None)


def test_duplicate_shop_name_is_case_and_space_insensitive() -> None:
    shops = _valid_shops()
    shops[1]["name"] = " local a "

    errors, _ = _validate(shops)

    assert [(issue.rule, issue.element, issue.shop_index) for issue in errors] == [
        ("duplicate_shop_name", "shop", 1)
    ]
    issue = errors[0]
    assert issue.shop_name is not None
    assert issue.shop_name.strip() == "local a"
    assert "local a" in issue.message


def test_duplicate_shop_id() -> None:
    shops = _valid_shops()
    shops[0]["shop_id"] = shops[1]["shop_id"]

    _assert_single_error(
        shops, rule="duplicate_shop_id", element="shop", shop_index=1, shop_name="Local B"
    )


def test_missing_front_zone() -> None:
    shops = _valid_shops()
    del shops[0]["zones"]["front"]

    _assert_single_error(
        shops, rule="missing_front_zone", element="shop", shop_index=0, shop_name="Local A"
    )


def test_missing_entry_line() -> None:
    shops = _valid_shops()
    shops[1]["entry_line"] = None

    _assert_single_error(
        shops, rule="missing_entry_line", element="shop", shop_index=1, shop_name="Local B"
    )


# --- Range -----------------------------------------------------------------------


def _set_zone_point(shops: list[Shop], role: str, index: int, point: list[float]) -> None:
    shops[0]["zones"][role][index] = point


# Each vertex is pushed just outside [0, 1] in a direction that keeps the polygon simple.
@pytest.mark.parametrize(
    ("mutate", "element"),
    [
        (lambda shops: _set_zone_point(shops, "front", 2, [0.3, 1.000001]), "zone:front"),
        (lambda shops: _set_zone_point(shops, "interior", 2, [0.3, 1.000001]), "zone:interior"),
        (
            lambda shops: _set_zone_point(shops, "showcase", 1, [0.39, -0.000001]),
            "zone:showcase",
        ),
        (
            lambda shops: shops[0]["entry_line"].update(start=[-0.000001, 0.4]),
            "entry_line",
        ),
    ],
    ids=["front", "interior", "showcase", "entry-line"],
)
def test_out_of_range_is_an_issue_not_an_exception(mutate: Any, element: str) -> None:
    shops = _valid_shops()
    mutate(shops)

    _assert_single_error(
        shops, rule="out_of_range", element=element, shop_index=0, shop_name="Local A"
    )


def test_coordinates_exactly_zero_and_one_are_accepted() -> None:
    shops = _valid_shops()
    shops[0]["zones"]["interior"] = [[0.0, 0.4], [0.3, 0.4], [0.3, 1.0], [0.0, 1.0]]

    errors, _ = _validate(shops)

    assert errors == []


# --- Polygon geometry ------------------------------------------------------------


def _circle(cx: float, cy: float, radius: float, vertices: int) -> list[list[float]]:
    return [
        _n(
            cx + radius * math.cos(2 * math.pi * k / vertices),
            cy + radius * math.sin(2 * math.pi * k / vertices),
        )
        for k in range(vertices)
    ]


def test_too_few_vertices() -> None:
    shops = _valid_shops()
    shops[0]["zones"]["front"] = [_n(100, 100), _n(300, 200)]

    _assert_single_error(
        shops, rule="too_few_vertices", element="zone:front", shop_index=0, shop_name="Local A"
    )


def test_too_many_vertices() -> None:
    shops = _valid_shops()
    # 65 vertices on a 50 px radius: ~4.8 px between neighbours, no other rule fails.
    shops[0]["zones"]["front"] = _circle(200, 150, 50, 65)

    _assert_single_error(
        shops, rule="too_many_vertices", element="zone:front", shop_index=0, shop_name="Local A"
    )


def test_sixty_four_vertices_are_accepted() -> None:
    shops = _valid_shops()
    shops[0]["zones"]["front"] = _circle(200, 150, 50, 64)

    errors, _ = _validate(shops)

    assert errors == []


def test_vertices_too_close() -> None:
    shops = _valid_shops()
    # Collinear extra vertex 2 px away from the top-left corner.
    shops[1]["zones"]["interior"] = [
        _n(600, 200),
        _n(602, 200),
        _n(800, 200),
        _n(800, 350),
        _n(600, 350),
    ]

    _assert_single_error(
        shops,
        rule="vertices_too_close",
        element="zone:interior",
        shop_index=1,
        shop_name="Local B",
    )


@pytest.mark.parametrize(
    "polygon_px",
    [
        # Asymmetric bow tie: edges 0 and 2 cross, area stays above 100 px².
        [(100, 100), (300, 200), (300, 100), (100, 160)],
        # Vertex (300, 150) touches the non-adjacent edge (300,100)-(300,200).
        [(100, 100), (300, 100), (300, 200), (200, 200), (300, 150)],
    ],
    ids=["bow-tie", "vertex-touches-edge"],
)
def test_self_intersection(polygon_px: list[tuple[float, float]]) -> None:
    shops = _valid_shops()
    shops[0]["zones"]["front"] = [_n(*point) for point in polygon_px]

    _assert_single_error(
        shops, rule="self_intersection", element="zone:front", shop_index=0, shop_name="Local A"
    )


def test_area_too_small() -> None:
    shops = _valid_shops()
    # 9 x 11 px = 99 px².
    shops[0]["zones"]["showcase"] = _rect(310, 100, 9, 11)

    _assert_single_error(
        shops, rule="area_too_small", element="zone:showcase", shop_index=0, shop_name="Local A"
    )


# --- Entry line geometry ---------------------------------------------------------


def test_line_too_short() -> None:
    shops = _valid_shops()
    shops[1]["entry_line"] = _line((620, 200), (629.99, 200))

    _assert_single_error(
        shops, rule="line_too_short", element="entry_line", shop_index=1, shop_name="Local B"
    )


# --- All errors at once ----------------------------------------------------------


def test_all_errors_are_returned_not_only_the_first() -> None:
    shops = _valid_shops()
    del shops[0]["zones"]["front"]
    shops[0]["zones"]["showcase"] = _rect(310, 100, 9, 11)
    shops[1]["entry_line"] = _line((620, 200), (629.99, 200))
    shops[1]["zones"]["interior"][2] = [0.8, 1.000001]
    shops.append({**_valid_shops()[1], "shop_id": None, "name": " LOCAL b "})

    errors, _ = _validate(shops)

    assert sorted((issue.rule, issue.element, issue.shop_index) for issue in errors) == sorted(
        [
            ("missing_front_zone", "shop", 0),
            ("area_too_small", "zone:showcase", 0),
            ("line_too_short", "entry_line", 1),
            ("out_of_range", "zone:interior", 1),
            ("duplicate_shop_name", "shop", 2),
        ]
    )
    for issue in errors:
        assert isinstance(issue, SceneIssue)
        assert issue.message.strip()


# --- Warnings --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start_px", "end_px"),
    [
        # Far below every zone of the shop.
        ((120, 450), (280, 450)),
        # Crosses only the showcase: showcase does not count.
        ((320, 150), (380, 150)),
    ],
    ids=["far-away", "only-showcase"],
)
def test_line_not_touching_front_nor_interior_is_a_warning(
    start_px: tuple[float, float], end_px: tuple[float, float]
) -> None:
    shops = _valid_shops()
    shops[0]["entry_line"] = _line(start_px, end_px)

    errors, warnings = _validate(shops)

    assert errors == []
    assert [(issue.rule, issue.element, issue.shop_index) for issue in warnings] == [
        ("line_not_touching_zones", "entry_line", 0)
    ]
    assert warnings[0].shop_name == "Local A"
    assert "Local A" in warnings[0].message


def test_line_touching_only_the_interior_is_accepted_without_warning() -> None:
    shops = _valid_shops()
    shops[0]["entry_line"] = _line((120, 300), (280, 300))

    errors, warnings = _validate(shops)

    assert errors == []
    assert warnings == []


def test_zones_of_different_shops_overlapping_is_a_warning() -> None:
    shops = _valid_shops()
    # Local B showcase overlaps Local A interior (100,200)-(300,350).
    shops[1]["zones"]["showcase"] = _rect(250, 250, 100, 50)

    errors, warnings = _validate(shops)

    assert errors == []
    assert warnings
    for issue in warnings:
        assert isinstance(issue, SceneIssue)
        assert issue.rule == "zones_overlap"
        assert issue.shop_index in (0, 1)
        assert issue.message.strip()
        assert "Local A" in issue.message or "Local B" in issue.message


def test_warnings_do_not_hide_errors() -> None:
    shops = _valid_shops()
    shops[0]["entry_line"] = _line((120, 450), (280, 450))
    shops[1]["entry_line"] = _line((620, 200), (629.99, 200))

    errors, warnings = _validate(shops)

    assert [(issue.rule, issue.shop_index) for issue in errors] == [("line_too_short", 1)]
    assert [(issue.rule, issue.shop_index) for issue in warnings] == [
        ("line_not_touching_zones", 0)
    ]
