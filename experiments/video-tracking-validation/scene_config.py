from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

ALLOWED_DIRECTIONS = frozenset({"entry", "exit", "unknown"})
REQUIRED_DIRECTION_KEYS = ("A_to_B", "B_to_A")


class SceneConfigError(ValueError):
    """Raised when a scene configuration violates the geometric contract."""


def load_scene_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SceneConfigError("La configuración de escena debe ser un objeto JSON.")
    return payload


def validate_scene_config(scene: Mapping[str, Any]) -> dict[str, Any]:
    frame = scene.get("frame_reference")
    if not isinstance(frame, Mapping):
        raise SceneConfigError("frame_reference es obligatorio.")

    width = _require_positive_number(frame.get("width"), "frame_reference.width")
    height = _require_positive_number(frame.get("height"), "frame_reference.height")

    zone = scene.get("front_zone")
    if not isinstance(zone, Mapping):
        raise SceneConfigError("front_zone es obligatorio.")
    polygon = zone.get("polygon")
    _validate_polygon(polygon, width, height)

    line = scene.get("entry_line")
    if not isinstance(line, Mapping):
        raise SceneConfigError("entry_line es obligatorio.")
    start = _validate_point(line.get("start"), width, height, "entry_line.start")
    end = _validate_point(line.get("end"), width, height, "entry_line.end")
    if start == end:
        raise SceneConfigError("La línea debe tener dos puntos distintos y longitud no nula.")

    directions = line.get("directions")
    if not isinstance(directions, Mapping):
        raise SceneConfigError("entry_line.directions es obligatorio.")
    for key in REQUIRED_DIRECTION_KEYS:
        if key not in directions:
            raise SceneConfigError(f"Debe declararse el sentido de cruce {key}.")
        value = directions[key]
        if value not in ALLOWED_DIRECTIONS:
            raise SceneConfigError(
                f"{key} debe ser entry, exit o unknown; se recibió {value!r}."
            )

    sides = classify_line_sides(start, end)
    side_a = line.get("side_A")
    side_b = line.get("side_B")
    if isinstance(side_a, Mapping) and "sample_point" in side_a:
        sample_a = _validate_point(
            side_a["sample_point"], width, height, "entry_line.side_A.sample_point"
        )
        if sides(sample_a) != "A":
            raise SceneConfigError("side_A.sample_point no queda del lado A del segmento.")
    if isinstance(side_b, Mapping) and "sample_point" in side_b:
        sample_b = _validate_point(
            side_b["sample_point"], width, height, "entry_line.side_B.sample_point"
        )
        if sides(sample_b) != "B":
            raise SceneConfigError("side_B.sample_point no queda del lado B del segmento.")

    return dict(scene)


def classify_line_sides(
    start: tuple[float, float], end: tuple[float, float]
):
    """Label points as A (right of start→end), B (left) or on the supporting line."""

    start_x, start_y = start
    dx = end[0] - start_x
    dy = end[1] - start_y

    def classify(point: tuple[float, float]) -> str:
        cross = dx * (point[1] - start_y) - dy * (point[0] - start_x)
        if cross > 0:
            return "A"
        if cross < 0:
            return "B"
        return "on"

    return classify


def _require_positive_number(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise SceneConfigError(f"{field_name} debe ser un número mayor que cero.")
    return float(value)


def _validate_polygon(polygon: Any, width: float, height: float) -> list[tuple[float, float]]:
    if not isinstance(polygon, Sequence) or isinstance(polygon, (str, bytes)):
        raise SceneConfigError("El polígono debe ser una lista de puntos.")
    points = [
        _validate_point(point, width, height, f"front_zone.polygon[{index}]")
        for index, point in enumerate(polygon)
    ]
    distinct = list(dict.fromkeys(points))
    if len(distinct) < 3:
        raise SceneConfigError("El polígono debe tener al menos tres puntos distintos.")
    if _polygon_area(points) == 0:
        raise SceneConfigError("El polígono debe tener área no nula.")
    return points


def _validate_point(
    point: Any, width: float, height: float, field_name: str
) -> tuple[float, float]:
    if not isinstance(point, Sequence) or isinstance(point, (str, bytes)) or len(point) != 2:
        raise SceneConfigError(f"{field_name} debe ser un punto [x, y].")
    x, y = point
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise SceneConfigError(f"{field_name} debe usar coordenadas numéricas.")
    if x < 0 or x > width or y < 0 or y > height:
        raise SceneConfigError(
            f"{field_name} debe estar dentro de [0, {width}] × [0, {height}]."
        )
    return (float(x), float(y))


def _polygon_area(points: Sequence[tuple[float, float]]) -> float:
    area = 0.0
    count = len(points)
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % count]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0
