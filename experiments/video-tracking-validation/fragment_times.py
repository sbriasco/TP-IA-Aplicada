from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

REQUIRED_FRAGMENT_FIELDS = (
    "video_id",
    "fragment_id",
    "start_video_seconds",
    "end_video_seconds",
    "time_unit",
    "selection_reason",
    "covered_cases",
    "coverage_limitations",
)


class FragmentTimeError(ValueError):
    """Raised when a fragment interval or time conversion is invalid."""


def load_fragments_manifest(
    path: str | Path,
    video_durations: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    manifest_path = Path(path)
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise FragmentTimeError("El manifest de fragmentos no tiene encabezados.")
        missing = [field for field in REQUIRED_FRAGMENT_FIELDS if field not in reader.fieldnames]
        if missing:
            raise FragmentTimeError(
                "Faltan columnas en el manifest de fragmentos: " + ", ".join(missing)
            )
        fragments = []
        for row in reader:
            fragment = {
                **row,
                "start_video_seconds": _parse_seconds(
                    row["start_video_seconds"], "start_video_seconds"
                ),
                "end_video_seconds": _parse_seconds(
                    row["end_video_seconds"], "end_video_seconds"
                ),
            }
            validate_fragment_interval(fragment)
            duration = video_durations.get(fragment["video_id"]) if video_durations else None
            if duration is not None:
                validate_fragment_within_duration(fragment, duration)
            fragments.append(fragment)
    if not fragments:
        raise FragmentTimeError("El manifest de fragmentos no contiene filas.")
    return fragments


def validate_fragment_interval(fragment: Mapping[str, Any]) -> None:
    if fragment.get("time_unit") != "seconds":
        raise FragmentTimeError("La unidad temporal debe ser seconds.")
    start = fragment.get("start_video_seconds")
    end = fragment.get("end_video_seconds")
    if not isinstance(start, (int, float)) or isinstance(start, bool):
        raise FragmentTimeError("start_video_seconds debe ser numérico.")
    if not isinstance(end, (int, float)) or isinstance(end, bool):
        raise FragmentTimeError("end_video_seconds debe ser numérico.")
    if start < 0:
        raise FragmentTimeError("start_video_seconds debe ser mayor o igual a cero.")
    if end <= start:
        raise FragmentTimeError(
            "end_video_seconds debe ser mayor que start_video_seconds."
        )


def validate_fragment_within_duration(
    fragment: Mapping[str, Any], duration_seconds: float
) -> None:
    validate_fragment_interval(fragment)
    if duration_seconds <= 0:
        raise FragmentTimeError("La duración del video debe ser mayor que cero.")
    start = fragment["start_video_seconds"]
    end = fragment["end_video_seconds"]
    if start >= duration_seconds:
        raise FragmentTimeError(
            "start_video_seconds debe ser menor que la duración del video."
        )
    if end > duration_seconds:
        raise FragmentTimeError(
            "end_video_seconds no puede exceder la duración del video."
        )


def is_timestamp_in_fragment(
    video_timestamp_seconds: float, fragment: Mapping[str, Any]
) -> bool:
    validate_fragment_interval(fragment)
    start = fragment["start_video_seconds"]
    end = fragment["end_video_seconds"]
    return start <= video_timestamp_seconds < end


def relative_seconds(
    video_timestamp_seconds: float,
    start_video_seconds: float,
    processing_time_seconds: float | None = None,
) -> float:
    del processing_time_seconds
    return video_timestamp_seconds - start_video_seconds


def behavior_duration_seconds(
    video_timestamp_start: float,
    video_timestamp_end: float,
    *,
    processing_time_seconds: float | None = None,
) -> float:
    """Duración observable en segundos del video. No usa tiempo de procesamiento."""
    del processing_time_seconds
    return float(video_timestamp_end) - float(video_timestamp_start)


BEHAVIOR_INTERVAL_FIELDS = (
    "observation_id",
    "fragment_id",
    "observation_type",
    "video_timestamp_start",
    "video_timestamp_end",
    "duration_seconds",
    "notes",
)


def write_behavior_intervals_from_manual(
    manual_path: str | Path,
    output_path: str | Path,
) -> int:
    manual_file = Path(manual_path)
    rows: list[dict[str, str]] = []
    with manual_file.open(encoding="utf-8", newline="") as handle:
        for item in csv.DictReader(handle):
            start = float(item["video_timestamp_start"])
            end = float(item["video_timestamp_end"])
            duration = behavior_duration_seconds(start, end, processing_time_seconds=None)
            rows.append(
                {
                    "observation_id": item["observation_id"],
                    "fragment_id": item["fragment_id"],
                    "observation_type": item["observation_type"],
                    "video_timestamp_start": item["video_timestamp_start"],
                    "video_timestamp_end": item["video_timestamp_end"],
                    "duration_seconds": str(duration),
                    "notes": "duration_seconds = video_timestamp_end - video_timestamp_start; no usa processing_time_seconds.",
                }
            )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BEHAVIOR_INTERVAL_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _parse_seconds(value: str, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise FragmentTimeError(f"{field_name} debe expresarse en segundos.") from error
