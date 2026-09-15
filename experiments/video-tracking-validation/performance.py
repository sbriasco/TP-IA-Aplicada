from __future__ import annotations

import csv
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PERFORMANCE_FIELDS = (
    "session_id",
    "video_id",
    "fragment_id",
    "device",
    "video_duration_seconds",
    "frames_processed",
    "processing_time_seconds",
    "detection_tracking_time_seconds",
    "postprocess_time_seconds",
    "measurement_timestamp",
    "notes",
)


def describe_device(device: str) -> str:
    return f"{device}; {platform.system()} {platform.release()}; {platform.node()}"


def build_performance_row(
    *,
    session_id: str,
    video_id: str,
    fragment_id: str,
    device: str,
    video_duration_seconds: float,
    frames_processed: int,
    processing_time_seconds: float,
    detection_tracking_time_seconds: float,
    postprocess_time_seconds: float,
    notes: str,
) -> dict[str, str | int | float]:
    return {
        "session_id": session_id,
        "video_id": video_id,
        "fragment_id": fragment_id,
        "device": describe_device(device),
        "video_duration_seconds": video_duration_seconds,
        "frames_processed": frames_processed,
        "processing_time_seconds": processing_time_seconds,
        "detection_tracking_time_seconds": detection_tracking_time_seconds,
        "postprocess_time_seconds": postprocess_time_seconds,
        "measurement_timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }


def build_performance_summary_row(fragment_rows: Sequence[Mapping[str, Any]]) -> dict[str, str | int | float]:
    if not fragment_rows:
        raise ValueError("El resumen de rendimiento requiere al menos un registro por fragmento.")
    ids = [str(row["fragment_id"]) for row in fragment_rows]
    devices = sorted({str(row["device"]) for row in fragment_rows})
    return {
        "session_id": "summary-traceable-to-fragment-rows",
        "video_id": ";".join(sorted({str(row["video_id"]) for row in fragment_rows})),
        "fragment_id": "summary",
        "device": "; ".join(devices),
        "video_duration_seconds": sum(float(row["video_duration_seconds"]) for row in fragment_rows),
        "frames_processed": sum(int(row["frames_processed"]) for row in fragment_rows),
        "processing_time_seconds": sum(float(row["processing_time_seconds"]) for row in fragment_rows),
        "detection_tracking_time_seconds": sum(
            float(row["detection_tracking_time_seconds"]) for row in fragment_rows
        ),
        "postprocess_time_seconds": sum(float(row["postprocess_time_seconds"]) for row in fragment_rows),
        "measurement_timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "Resumen opcional trazable a: "
            + ", ".join(ids)
            + ". No es una medición independiente ni sustituye timestamps de comportamiento."
        ),
    }


def write_performance_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PERFORMANCE_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PERFORMANCE_FIELDS})
    return len(rows)
