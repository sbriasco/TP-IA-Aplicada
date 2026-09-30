"""Real detector on the reference machine. The default suite does not collect this."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


def test_reference_clip_finishes_and_writes_the_summary(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("No hay CUDA en este equipo; la medición queda fuera de la suite.")

    weights = os.environ.get("FLOWSIGHT_YOLO_WEIGHTS", "")
    if weights == "" or not Path(weights).is_file():
        pytest.skip("Falta el peso del modelo en FLOWSIGHT_YOLO_WEIGHTS.")

    import cv2

    from flowsight.video.fixtures import write_clip
    from flowsight.video.probe import probe_video
    from flowsight.vision.evidence import build_reference_summary, write_reference_summary
    from flowsight.vision.ultralytics_tracker import UltralyticsTracker

    clip = write_clip(tmp_path, size=(320, 240))
    probed = probe_video(clip)
    started = datetime.now(UTC)
    tracker = UltralyticsTracker(Path(weights))
    capture = cv2.VideoCapture(str(clip))
    try:
        for frame_index in range(probed.frame_count):
            ok, frame = capture.read()
            assert ok
            tracker.detect(frame_index, probed.width, probed.height, frame)
    finally:
        capture.release()
    elapsed = (datetime.now(UTC) - started).total_seconds()
    summary = build_reference_summary(
        execution_mode=tracker.execution_mode or "cpu",
        detector_name=tracker.name,
        detector_version=tracker.version,
        tracker_name=tracker.tracker_name,
        tracker_version=tracker.tracker_version,
        frames_total=probed.frame_count,
        processing_duration_s=elapsed,
        limitations=list(tracker.limitations),
    )
    path = write_reference_summary(tmp_path / "evidence.json", summary)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored["execution_mode"] in {"cuda", "cpu"}
    assert stored["detector_version"]
    assert stored["tracker_version"]
    assert "frames_per_processing_second" in stored
    text = json.dumps(stored)
    assert "hostname" not in text
    assert ":\\" not in text
