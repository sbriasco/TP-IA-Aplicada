"""Reference-machine summary: rate, versions, and no machine identity."""

from __future__ import annotations

import json
from pathlib import Path

from flowsight.vision.evidence import build_reference_summary, write_reference_summary
from flowsight.vision.ultralytics_tracker import choose_device


def test_summary_records_the_rate_and_leaves_out_the_machine(tmp_path: Path) -> None:
    summary = build_reference_summary(
        execution_mode="cpu",
        detector_name="yolov8n",
        detector_version="8.4.153",
        tracker_name="bytetrack",
        tracker_version="ultralytics-bytetrack",
        frames_total=50,
        processing_duration_s=2.5,
        limitations=["No hay procesador gráfico disponible; el análisis corrió en CPU."],
    )

    assert summary["execution_mode"] == "cpu"
    assert summary["detector_version"] == "8.4.153"
    assert summary["tracker_version"] == "ultralytics-bytetrack"
    assert summary["frames_per_processing_second"] == 20.0
    text = json.dumps(summary)
    assert "\\\\" not in text
    assert ":/" not in text
    assert "hostname" not in text

    path = write_reference_summary(tmp_path / "evidence.json", summary)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["frames_per_processing_second"] == 20.0
    assert stored["limitations"] == [
        "No hay procesador gráfico disponible; el análisis corrió en CPU."
    ]


def test_zero_processing_time_leaves_the_rate_unavailable() -> None:
    summary = build_reference_summary(
        execution_mode="cuda",
        detector_name="yolov8n",
        detector_version="8.4.153",
        tracker_name="bytetrack",
        tracker_version="ultralytics-bytetrack",
        frames_total=10,
        processing_duration_s=0,
        limitations=[],
    )

    assert summary["frames_per_processing_second"] is None
    assert summary["limitations"] == ["La tasa de procesamiento no está disponible."]


def test_missing_or_unusable_gpu_selects_cpu_with_a_limitation() -> None:
    device, limitation = choose_device(cuda_available=False, cuda_ready=False)
    assert device == "cpu"
    assert limitation == "No hay procesador gráfico disponible; el análisis corrió en CPU."

    device, limitation = choose_device(cuda_available=True, cuda_ready=False)
    assert device == "cpu"
    assert limitation == "El procesador gráfico no pudo usarse; el análisis siguió en CPU."

    device, limitation = choose_device(cuda_available=True, cuda_ready=True)
    assert device == "cuda"
    assert limitation is None
