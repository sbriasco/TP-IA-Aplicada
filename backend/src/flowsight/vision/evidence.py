"""Anonymous summary of a reference-machine run. No host, user, or absolute path."""

from __future__ import annotations

import json
from pathlib import Path

_RATE_UNAVAILABLE = "La tasa de procesamiento no está disponible."


def build_reference_summary(
    *,
    execution_mode: str,
    detector_name: str,
    detector_version: str,
    tracker_name: str,
    tracker_version: str,
    frames_total: int,
    processing_duration_s: float,
    limitations: list[str],
) -> dict[str, object]:
    """Frames per processing second. A zero duration stays unavailable."""

    notes = list(limitations)
    if processing_duration_s <= 0:
        rate = None
        if _RATE_UNAVAILABLE not in notes:
            notes.append(_RATE_UNAVAILABLE)
    else:
        rate = frames_total / processing_duration_s
    return {
        "execution_mode": execution_mode,
        "detector_name": detector_name,
        "detector_version": detector_version,
        "tracker_name": tracker_name,
        "tracker_version": tracker_version,
        "frames_total": frames_total,
        "frames_per_processing_second": rate,
        "limitations": notes,
    }


def write_reference_summary(path: Path, summary: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path
