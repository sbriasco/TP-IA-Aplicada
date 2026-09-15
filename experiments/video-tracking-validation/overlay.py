from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from video_io import iter_fragment_frames


def render_fragment_overlays(
    *,
    video_path: str | Path,
    fragment: Mapping[str, Any],
    scene: Mapping[str, Any],
    detections: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    fps: float,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    detections_by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for detection in detections:
        detections_by_frame[int(detection["frame_index"])].append(detection)
    events_by_frame: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_frame[int(event["frame_index"])].append(event)

    polygon = np.array(scene["front_zone"]["polygon"], dtype=np.int32)
    line_start = tuple(int(value) for value in scene["entry_line"]["start"])
    line_end = tuple(int(value) for value in scene["entry_line"]["end"])
    written = 0
    for frame_record in iter_fragment_frames(video_path, fragment, fps=fps):
        frame = frame_record["frame"].copy()
        overlay = frame.copy()
        cv2.fillPoly(overlay, [polygon], (40, 180, 40))
        frame = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
        cv2.polylines(frame, [polygon], isClosed=True, color=(40, 180, 40), thickness=2)
        cv2.line(frame, line_start, line_end, (0, 220, 255), 2)
        cv2.putText(frame, "A", (line_start[0], line_start[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)
        cv2.putText(frame, "B", (line_end[0] - 10, line_end[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1)

        frame_index = int(frame_record["frame_index"])
        for detection in detections_by_frame.get(frame_index, []):
            x_min, y_min, x_max, y_max = (int(round(value)) for value in detection["bbox"])
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (255, 180, 40), 2)
            ref_x, ref_y = (int(round(value)) for value in detection["reference_point"])
            cv2.circle(frame, (ref_x, ref_y), 4, (0, 0, 255), -1)
            cv2.putText(
                frame,
                f"id {detection['track_id']}",
                (x_min, max(12, y_min - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 180, 40),
                1,
            )

        y_text = 16
        for event in events_by_frame.get(frame_index, []):
            label = f"{event['event_type']} {event['direction']}"
            cv2.putText(frame, label, (8, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
            y_text += 14

        dest = out_dir / f"overlay_f{frame_index:06d}.jpg"
        cv2.imwrite(str(dest), frame)
        written += 1
    return {"overlay_count": written, "output_dir": str(out_dir)}
