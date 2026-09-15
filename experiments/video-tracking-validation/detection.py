from __future__ import annotations

import json
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from detection_prep import DEFAULT_TRACKER_PATH, require_local_weights
from video_io import iter_fragment_frames

PERSON_CLASS_ID = 0


def make_automatic_observation_id(
    session_id: str, fragment_id: str, frame_index: int, track_id: str
) -> str:
    return f"{session_id}:{fragment_id}:{frame_index}:{track_id}"


def bbox_and_reference_point(xyxy: Iterable[float]) -> tuple[list[float], list[float]]:
    x_min, y_min, x_max, y_max = (float(value) for value in xyxy)
    bbox = [x_min, y_min, x_max, y_max]
    reference_point = [(x_min + x_max) / 2.0, y_max]
    return bbox, reference_point


def build_observation(
    *,
    session_id: str,
    video_id: str,
    fragment_id: str,
    frame_index: int,
    video_timestamp_seconds: float,
    relative_seconds: float,
    track_id: str,
    xyxy: Iterable[float],
) -> dict[str, Any]:
    bbox, reference_point = bbox_and_reference_point(xyxy)
    return {
        "automatic_observation_id": make_automatic_observation_id(
            session_id, fragment_id, frame_index, track_id
        ),
        "session_id": session_id,
        "video_id": video_id,
        "fragment_id": fragment_id,
        "frame_index": frame_index,
        "video_timestamp_seconds": video_timestamp_seconds,
        "relative_seconds": relative_seconds,
        "track_id": str(track_id),
        "bbox": bbox,
        "reference_point": reference_point,
    }


def write_detections_jsonl(path: str | Path, observations: Iterable[Mapping[str, Any]]) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for observation in observations:
            handle.write(json.dumps(observation, ensure_ascii=False) + "\n")
            count += 1
    return count


def run_person_tracking(
    *,
    video_path: str | Path,
    fragment: Mapping[str, Any],
    weights_path: str | Path,
    session_id: str,
    fps: float,
    device: str = "cpu",
    tracker_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ultralytics import YOLO

    local_weights = require_local_weights(weights_path)
    tracker = Path(tracker_path) if tracker_path else DEFAULT_TRACKER_PATH
    if not tracker.is_file():
        raise FileNotFoundError(f"No se encontró el tracker ByteTrack: {tracker}")

    started = time.perf_counter()
    model = YOLO(str(local_weights))
    observations: list[dict[str, Any]] = []
    frames_processed = 0
    track_ids: set[str] = set()

    for frame_record in iter_fragment_frames(video_path, fragment, fps=fps):
        frames_processed += 1
        results = model.track(
            source=frame_record["frame"],
            persist=True,
            tracker=str(tracker),
            device=device,
            classes=[PERSON_CLASS_ID],
            verbose=False,
        )
        if not results:
            continue
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            continue
        xyxy = boxes.xyxy.cpu().numpy()
        ids = boxes.id.cpu().numpy()
        for box, raw_id in zip(xyxy, ids, strict=True):
            track_id = str(int(raw_id))
            track_ids.add(track_id)
            observations.append(
                build_observation(
                    session_id=session_id,
                    video_id=str(fragment["video_id"]),
                    fragment_id=str(fragment["fragment_id"]),
                    frame_index=int(frame_record["frame_index"]),
                    video_timestamp_seconds=float(frame_record["video_timestamp_seconds"]),
                    relative_seconds=float(frame_record["relative_seconds"]),
                    track_id=track_id,
                    xyxy=box,
                )
                )

    detection_tracking_time_seconds = time.perf_counter() - started
    summary = {
        "session_id": session_id,
        "fragment_id": fragment.get("fragment_id"),
        "frames_processed": frames_processed,
        "detection_count": len(observations),
        "track_count": len(track_ids),
        "device": device,
        "weights": str(local_weights),
        "tracker": str(tracker),
        "detection_tracking_time_seconds": detection_tracking_time_seconds,
    }
    return observations, summary
