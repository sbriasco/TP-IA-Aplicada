from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scene_config import classify_line_sides

OSCILLATION_MAX_FRAMES = 10
LOST_GAP_FRAMES = 2
EVENT_FIELDS = (
    "session_id",
    "fragment_id",
    "automatic_observation_id",
    "frame_index",
    "video_timestamp_seconds",
    "relative_seconds",
    "track_id",
    "event_type",
    "target",
    "direction",
    "visibility_state",
    "track_continuity_status",
    "notes",
)


def point_in_polygon(point: Sequence[float], polygon: Sequence[Sequence[float]]) -> bool:
    x, y = float(point[0]), float(point[1])
    inside = False
    count = len(polygon)
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % count]
        intersects = (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 0.0) + x1
        if intersects:
            inside = not inside
    return inside


def segments_intersect(
    p1: Sequence[float],
    p2: Sequence[float],
    q1: Sequence[float],
    q2: Sequence[float],
) -> bool:
    """True if closed segments p1-p2 and q1-q2 intersect, including touching endpoints."""

    def orientation(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> bool:
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(
            a[1], b[1]
        )

    o1 = orientation(p1, p2, q1)
    o2 = orientation(p1, p2, q2)
    o3 = orientation(q1, q2, p1)
    o4 = orientation(q1, q2, p2)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if o1 == 0 and on_segment(p1, p2, q1):
        return True
    if o2 == 0 and on_segment(p1, p2, q2):
        return True
    if o3 == 0 and on_segment(q1, q2, p1):
        return True
    if o4 == 0 and on_segment(q1, q2, p2):
        return True
    return False


def line_crossing_sense(
    previous: Sequence[float],
    current: Sequence[float],
    start: Sequence[float],
    end: Sequence[float],
) -> str | None:
    if not segments_intersect(previous, current, start, end):
        return None
    classify = classify_line_sides((float(start[0]), float(start[1])), (float(end[0]), float(end[1])))
    prev_side = classify((float(previous[0]), float(previous[1])))
    curr_side = classify((float(current[0]), float(current[1])))
    if prev_side == "A" and curr_side == "B":
        return "A_to_B"
    if prev_side == "B" and curr_side == "A":
        return "B_to_A"
    return None


def load_detections_jsonl(path: str | Path) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                detections.append(json.loads(line))
    return detections


def events_from_detections(
    detections: Sequence[Mapping[str, Any]],
    scene: Mapping[str, Any],
) -> list[dict[str, str | int | float]]:
    polygon = scene["front_zone"]["polygon"]
    zone_name = scene["front_zone"]["name"]
    line = scene["entry_line"]
    start = line["start"]
    end = line["end"]
    line_name = line["name"]
    mapping = line["directions"]
    by_track: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for detection in sorted(
        detections,
        key=lambda item: (str(item["session_id"]), str(item["track_id"]), int(item["frame_index"])),
    ):
        key = (str(detection["session_id"]), str(detection["track_id"]))
        by_track.setdefault(key, []).append(detection)

    events: list[dict[str, str | int | float]] = []
    for (_session_id, track_id), records in by_track.items():
        events.extend(
            _events_for_track(
                records,
                track_id=track_id,
                polygon=polygon,
                zone_name=zone_name,
                start=start,
                end=end,
                line_name=line_name,
                mapping=mapping,
            )
        )
    events.sort(key=lambda item: (int(item["frame_index"]), str(item["track_id"]), str(item["event_type"])))
    return events


def write_events_csv(path: str | Path, events: Sequence[Mapping[str, Any]]) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVENT_FIELDS))
        writer.writeheader()
        for event in events:
            writer.writerow({field: event.get(field, "") for field in EVENT_FIELDS})
    return len(events)


def _events_for_track(
    records: Sequence[Mapping[str, Any]],
    *,
    track_id: str,
    polygon: Sequence[Sequence[float]],
    zone_name: str,
    start: Sequence[float],
    end: Sequence[float],
    line_name: str,
    mapping: Mapping[str, str],
) -> list[dict[str, str | int | float]]:
    events: list[dict[str, str | int | float]] = []
    pending_zone: dict[str, str | int | float] | None = None
    pending_line: dict[str, str | int | float] | None = None
    previous: Mapping[str, Any] | None = None
    previous_inside: bool | None = None

    for record in records:
        point = record["reference_point"]
        inside = point_in_polygon(point, polygon)
        if previous is not None:
            gap = int(record["frame_index"]) - int(previous["frame_index"])
            if gap >= LOST_GAP_FRAMES:
                events.append(
                    _event(
                        previous,
                        event_type="track_lost",
                        target="track",
                        direction="no aplicable",
                        visibility_state="lost",
                        track_continuity_status="posible pérdida",
                        notes="Hueco de frames en el mismo track_id; no se confirma salida de zona ni duplicado.",
                    )
                )
                events.append(
                    _event(
                        record,
                        event_type="track_resumed",
                        target="track",
                        direction="no aplicable",
                        visibility_state="visible",
                        track_continuity_status="continua",
                        notes="Reaparición del mismo track_id; no se asocia con otro ID.",
                    )
                )
                previous_inside = None
            sense = line_crossing_sense(previous["reference_point"], point, start, end)
            if sense is not None:
                candidate = _event(
                    record,
                    event_type="line_cross",
                    target=line_name,
                    direction=mapping.get(sense, "unknown"),
                    visibility_state="visible",
                    track_continuity_status="continua",
                    notes=f"Cruce de segmento {sense}.",
                )
                pending_line = _debounce(
                    events,
                    pending_line,
                    candidate,
                    opposite_directions=True,
                    oscillation_type="line_cross_oscillation",
                )
            if previous_inside is not None and inside != previous_inside:
                candidate = _event(
                    record,
                    event_type="zone_enter" if inside else "zone_exit",
                    target=zone_name,
                    direction="no aplicable",
                    visibility_state="visible",
                    track_continuity_status="continua",
                    notes="Cambio de pertenencia de la zona usando reference_point.",
                )
                pending_zone = _debounce(
                    events,
                    pending_zone,
                    candidate,
                    opposite_directions=False,
                    oscillation_type="zone_oscillation",
                )
        previous = record
        previous_inside = inside

    if pending_line is not None:
        events.append(pending_line)
    if pending_zone is not None:
        events.append(pending_zone)
    return events


def _debounce(
    events: list[dict[str, str | int | float]],
    pending: dict[str, str | int | float] | None,
    candidate: dict[str, str | int | float],
    *,
    opposite_directions: bool,
    oscillation_type: str,
) -> dict[str, str | int | float] | None:
    if pending is None:
        return candidate
    frame_delta = int(candidate["frame_index"]) - int(pending["frame_index"])
    opposite = (
        str(pending["direction"]) != str(candidate["direction"])
        if opposite_directions
        else str(pending["event_type"]) != str(candidate["event_type"])
    )
    if 0 < frame_delta <= OSCILLATION_MAX_FRAMES and opposite:
        pending["event_type"] = oscillation_type
        pending["notes"] = "Oscilación o duplicado de una misma ocurrencia; no se confirma el par."
        candidate["event_type"] = oscillation_type
        candidate["notes"] = "Oscilación o duplicado de una misma ocurrencia; no se confirma el par."
        events.append(pending)
        events.append(candidate)
        return None
    events.append(pending)
    return candidate


def _event(
    record: Mapping[str, Any],
    *,
    event_type: str,
    target: str,
    direction: str,
    visibility_state: str,
    track_continuity_status: str,
    notes: str,
) -> dict[str, str | int | float]:
    return {
        "session_id": record["session_id"],
        "fragment_id": record["fragment_id"],
        "automatic_observation_id": record["automatic_observation_id"],
        "frame_index": int(record["frame_index"]),
        "video_timestamp_seconds": float(record["video_timestamp_seconds"]),
        "relative_seconds": float(record["relative_seconds"]),
        "track_id": str(record["track_id"]),
        "event_type": event_type,
        "target": target,
        "direction": direction,
        "visibility_state": visibility_state,
        "track_continuity_status": track_continuity_status,
        "notes": notes,
    }
