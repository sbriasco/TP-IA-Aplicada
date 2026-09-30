"""Latest-frame preview for a video analysis job. One file, replaced in place."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

from flowsight.preview.broker import PreviewUpdate


def snapshot_path(videos_dir: Path, session_id: uuid.UUID, job_id: uuid.UUID) -> Path:
    return videos_dir / "derived" / str(session_id) / str(job_id) / "preview.json"


def write_preview_snapshot(path: Path, update: PreviewUpdate) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": str(update.session_id),
        "job_id": str(update.job_id),
        "frame_index": update.frame_index,
        "video_timestamp_seconds": float(update.video_timestamp_seconds),
        "progress_percent": update.progress_percent,
        "image_base64": update.image_base64,
        "schema_version": update.schema_version,
        "measures": list(update.measures),
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def read_preview_snapshot(path: Path) -> PreviewUpdate | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return PreviewUpdate(
            session_id=uuid.UUID(str(payload["session_id"])),
            job_id=uuid.UUID(str(payload["job_id"])),
            frame_index=int(payload["frame_index"]),
            video_timestamp_seconds=Decimal(str(payload["video_timestamp_seconds"])),
            progress_percent=float(payload["progress_percent"]),
            image_base64=str(payload["image_base64"]),
            schema_version=str(payload.get("schema_version", "2")),
            measures=tuple(payload.get("measures") or ()),
        )
    except (KeyError, TypeError, ValueError):
        return None
