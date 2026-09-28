"""Pure validation of a scene version before it is saved (specs/004, T030).

Applies the structural and geometric rules of data-model "Validación al guardar
una versión" plus the non-blocking warnings of R11. Rules that need the database
(``shop_other_camera``, ``reference_*``, ``newer_version_exists``) live in the
service layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from flowsight.scene.geometry import (
    MAX_VERTICES,
    MIN_AREA_PX2,
    MIN_LINE_PX,
    MIN_VERTEX_GAP_PX,
    Point,
    in_unit_range,
    line_length_px,
    min_consecutive_distance_px,
    polygon_area_px,
    polygon_self_intersects,
    polygons_overlap,
    segment_touches_polygon,
    to_px,
)

ZONE_ROLES = ("front", "interior", "showcase")
LINE_ZONE_ROLES = ("front", "interior")
MIN_VERTICES = 3

ELEMENT_VERSION = "version"
ELEMENT_SHOP = "shop"
ELEMENT_ENTRY_LINE = "entry_line"

_ROLE_LABELS = {"front": "frontal", "interior": "interior", "showcase": "vidriera"}
_ELEMENT_ORDER = (
    ELEMENT_VERSION,
    ELEMENT_SHOP,
    *(f"zone:{role}" for role in ZONE_ROLES),
    ELEMENT_ENTRY_LINE,
)


@dataclass(frozen=True)
class SceneIssue:
    """A validation error or warning tied to a version, shop or shop element."""

    rule: str
    element: str
    shop_index: int | None
    shop_name: str | None
    message: str


@dataclass
class _ShopContext:
    index: int
    name: str
    zones_px: dict[str, list[Point]]
    line_px: tuple[Point, Point] | None
    unmeasurable_line_zones: bool


def _zone_element(role: str) -> str:
    return f"zone:{role}"


def _element_label(element: str) -> str:
    if element.startswith("zone:"):
        return f"la zona {_ROLE_LABELS[element.split(':', 1)[1]]}"
    if element == ELEMENT_ENTRY_LINE:
        return "la línea de entrada"
    return "el local"


def _issue(rule: str, element: str, shop_index: int, shop_name: str, detail: str) -> SceneIssue:
    message = f'Local "{shop_name}", {_element_label(element)}: {detail} ({rule}).'
    return SceneIssue(rule, element, shop_index, shop_name, message)


def _sort_key(issue: SceneIssue) -> tuple[int, int]:
    shop = -1 if issue.shop_index is None else issue.shop_index
    return (shop, _ELEMENT_ORDER.index(issue.element))


def _check_zone(
    polygon: Sequence[Sequence[float]],
    role: str,
    shop_index: int,
    shop_name: str,
    frame_width: int,
    frame_height: int,
) -> tuple[list[SceneIssue], list[Point] | None]:
    """Errors of one zone and its pixel polygon, or ``None`` if it cannot be measured."""

    element = _zone_element(role)
    errors: list[SceneIssue] = []
    count = len(polygon)

    if count < MIN_VERTICES:
        detail = f"tiene {count} vértices y necesita al menos {MIN_VERTICES}"
        return [_issue("too_few_vertices", element, shop_index, shop_name, detail)], None
    if count > MAX_VERTICES:
        # Not measured any further: self intersection is quadratic in the vertex
        # count and the request size is not bounded before this point.
        detail = f"tiene {count} vértices y admite como máximo {MAX_VERTICES}"
        return [_issue("too_many_vertices", element, shop_index, shop_name, detail)], None
    if not all(in_unit_range(point) for point in polygon):
        detail = "tiene coordenadas fuera del rango [0, 1]"
        errors.append(_issue("out_of_range", element, shop_index, shop_name, detail))
        return errors, None

    polygon_px = [to_px(point, frame_width, frame_height) for point in polygon]
    vertices_too_close = min_consecutive_distance_px(polygon_px) <= MIN_VERTEX_GAP_PX
    if vertices_too_close:
        detail = f"tiene vértices consecutivos a {MIN_VERTEX_GAP_PX} px o menos"
        errors.append(_issue("vertices_too_close", element, shop_index, shop_name, detail))
    # Near-duplicate vertices make adjacent edges touch, so self intersection is
    # only measured once the vertex gaps are valid.
    elif polygon_self_intersects(polygon_px):
        detail = "tiene aristas que se cruzan o se tocan"
        errors.append(_issue("self_intersection", element, shop_index, shop_name, detail))
    if polygon_area_px(polygon_px) < MIN_AREA_PX2:
        detail = f"tiene un área menor a {MIN_AREA_PX2} px²"
        errors.append(_issue("area_too_small", element, shop_index, shop_name, detail))
    return errors, polygon_px


def _check_line(
    line: Mapping[str, Any],
    shop_index: int,
    shop_name: str,
    frame_width: int,
    frame_height: int,
) -> tuple[list[SceneIssue], tuple[Point, Point] | None]:
    """Errors of the entry line and its pixel endpoints, or ``None`` if out of range."""

    start, end = line["start"], line["end"]
    if not (in_unit_range(start) and in_unit_range(end)):
        detail = "tiene coordenadas fuera del rango [0, 1]"
        return [_issue("out_of_range", ELEMENT_ENTRY_LINE, shop_index, shop_name, detail)], None

    start_px = to_px(start, frame_width, frame_height)
    end_px = to_px(end, frame_width, frame_height)
    if line_length_px(start_px, end_px) < MIN_LINE_PX:
        detail = f"mide menos de {MIN_LINE_PX} px"
        issue = _issue("line_too_short", ELEMENT_ENTRY_LINE, shop_index, shop_name, detail)
        return [issue], (start_px, end_px)
    return [], (start_px, end_px)


def validate_scene(
    shops_input: Sequence[Mapping[str, Any]],
    frame_width: int,
    frame_height: int,
) -> tuple[list[SceneIssue], list[SceneIssue]]:
    """Validate every shop of a version and return ``(errors, warnings)``.

    All errors are returned, ordered by shop and, within a shop, by element
    (shop, front, interior, showcase, entry line). An element with fewer than 3 or
    more than 64 vertices, or with a coordinate outside [0, 1], is not measured
    any further.
    """

    if not shops_input:
        issue = SceneIssue(
            "no_shops",
            ELEMENT_VERSION,
            None,
            None,
            "La versión no tiene locales: agregá al menos uno (no_shops).",
        )
        return [issue], []

    errors: list[SceneIssue] = []
    warnings: list[SceneIssue] = []
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    contexts: list[_ShopContext] = []

    for index, shop in enumerate(shops_input):
        name = str(shop.get("name") or "").strip()

        name_key = name.casefold()
        if name_key in seen_names:
            detail = "repite el nombre de otro local de la versión"
            errors.append(_issue("duplicate_shop_name", ELEMENT_SHOP, index, name, detail))
        seen_names.add(name_key)

        shop_id = shop.get("shop_id")
        if shop_id is not None:
            if str(shop_id) in seen_ids:
                detail = "repite el identificador de otro local de la versión"
                errors.append(_issue("duplicate_shop_id", ELEMENT_SHOP, index, name, detail))
            seen_ids.add(str(shop_id))

        zones: Mapping[str, Any] = shop.get("zones") or {}
        if zones.get("front") is None:
            detail = "no tiene zona frontal"
            errors.append(_issue("missing_front_zone", ELEMENT_SHOP, index, name, detail))
        line = shop.get("entry_line")
        if line is None:
            detail = "no tiene línea de entrada"
            errors.append(_issue("missing_entry_line", ELEMENT_SHOP, index, name, detail))

        zones_px: dict[str, list[Point]] = {}
        unmeasurable_line_zones = False
        for role in ZONE_ROLES:
            polygon = zones.get(role)
            if polygon is None:
                continue
            zone_errors, polygon_px = _check_zone(
                polygon, role, index, name, frame_width, frame_height
            )
            errors.extend(zone_errors)
            if polygon_px is not None:
                zones_px[role] = polygon_px
            elif role in LINE_ZONE_ROLES:
                unmeasurable_line_zones = True

        line_px = None
        if line is not None:
            line_errors, line_px = _check_line(line, index, name, frame_width, frame_height)
            errors.extend(line_errors)

        contexts.append(_ShopContext(index, name, zones_px, line_px, unmeasurable_line_zones))

    warnings.extend(_line_warnings(contexts))
    warnings.extend(_overlap_warnings(contexts))
    warnings.sort(key=_sort_key)
    return errors, warnings


def _line_warnings(contexts: Sequence[_ShopContext]) -> list[SceneIssue]:
    """``line_not_touching_zones`` when the line misses both front and interior.

    Only raised when the line and every drawn front/interior zone can be measured.
    """

    warnings: list[SceneIssue] = []
    for shop in contexts:
        targets = [shop.zones_px[role] for role in LINE_ZONE_ROLES if role in shop.zones_px]
        if shop.line_px is None or shop.unmeasurable_line_zones or not targets:
            continue
        if not any(segment_touches_polygon(*shop.line_px, polygon) for polygon in targets):
            detail = "no toca ni cruza la zona frontal ni la interior"
            warnings.append(
                _issue("line_not_touching_zones", ELEMENT_ENTRY_LINE, shop.index, shop.name, detail)
            )
    return warnings


def _overlap_warnings(contexts: Sequence[_ShopContext]) -> list[SceneIssue]:
    """``zones_overlap`` once per overlapping zone pair of different shops.

    The warning points at the zone of the later shop and names the earlier one.
    """

    warnings: list[SceneIssue] = []
    for later_pos, later in enumerate(contexts):
        for earlier in contexts[:later_pos]:
            for later_role, later_polygon in later.zones_px.items():
                for earlier_role, earlier_polygon in earlier.zones_px.items():
                    if not polygons_overlap(later_polygon, earlier_polygon):
                        continue
                    detail = (
                        f'se superpone con la zona {_ROLE_LABELS[earlier_role]} del local "'
                        f'{earlier.name}"'
                    )
                    warnings.append(
                        _issue(
                            "zones_overlap",
                            _zone_element(later_role),
                            later.index,
                            later.name,
                            detail,
                        )
                    )
    return warnings
