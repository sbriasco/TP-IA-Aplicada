"""Collect and anonymize repeatable local environment evidence."""

from __future__ import annotations

import argparse
import json
import platform
import socket
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def median_ms(samples: list[float]) -> float:
    if len(samples) != 3 or any(sample < 0 for sample in samples):
        raise ValueError("Se requieren exactamente tres mediciones no negativas.")
    return round(float(statistics.median(samples)), 2)


def collect_evidence(mode: str, samples: dict[str, list[float]]) -> dict[str, Any]:
    fixture_median = median_ms(samples["fixture_ms"])
    health_median = median_ms(samples["health_ms"])
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "machine_name": socket.gethostname(),
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "execution_mode": mode,
        "result": "passed" if fixture_median < 30_000 and health_median < 1_000 else "failed",
        "fixture_ms": samples["fixture_ms"],
        "fixture_median_ms": fixture_median,
        "health_ms": samples["health_ms"],
        "health_median_ms": health_median,
        "limitations": ["El flujo es sintético y no mide procesamiento de video."],
    }


def anonymize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "recorded_at",
        "operating_system",
        "python_version",
        "execution_mode",
        "result",
        "fixture_median_ms",
        "health_median_ms",
        "limitations",
    }
    return {key: value for key, value in evidence.items() if key in allowed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--mode", choices=("cpu", "gpu"), default="cpu")
    arguments = parser.parse_args()
    samples = json.loads(arguments.samples.read_text(encoding="utf-8"))
    evidence = collect_evidence(arguments.mode, samples)
    arguments.private.parent.mkdir(parents=True, exist_ok=True)
    arguments.summary.parent.mkdir(parents=True, exist_ok=True)
    arguments.private.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    arguments.summary.write_text(
        json.dumps(anonymize_evidence(evidence), indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
