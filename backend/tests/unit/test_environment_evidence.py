from __future__ import annotations

import pytest

from flowsight.core.environment_evidence import (
    anonymize_evidence,
    collect_evidence,
    median_ms,
)


def test_requires_three_non_negative_samples() -> None:
    with pytest.raises(ValueError):
        median_ms([1, 2])
    with pytest.raises(ValueError):
        median_ms([1, -2, 3])


def test_collects_medians_and_threshold_result() -> None:
    evidence = collect_evidence("cpu", {"fixture_ms": [120, 100, 110], "health_ms": [5, 3, 4]})

    assert evidence["fixture_median_ms"] == 110
    assert evidence["health_median_ms"] == 4
    assert evidence["result"] == "passed"


def test_anonymization_removes_machine_and_private_details() -> None:
    evidence = collect_evidence("cpu", {"fixture_ms": [1, 2, 3], "health_ms": [1, 2, 3]})
    evidence["absolute_path"] = "C:/Users/person/project"
    evidence["secret"] = "do-not-keep"

    summary = anonymize_evidence(evidence)

    assert "machine_name" not in summary
    assert "absolute_path" not in summary
    assert "secret" not in summary
    assert summary["execution_mode"] == "cpu"
