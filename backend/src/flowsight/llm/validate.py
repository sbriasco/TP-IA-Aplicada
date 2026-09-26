"""CLI de validación Foundry: inventario, llamada simple y tool calling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flowsight.llm.client import simple_completion
from flowsight.llm.evidence import empty_summary_template, write_evidence_json
from flowsight.llm.inventory import run_inventory, write_inventory_draft
from flowsight.llm.tool_loop import run_tool_loop


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validación Azure AI Foundry (FlowSight)")
    parser.add_argument("output_dir", type=str)
    parser.add_argument(
        "--step",
        choices=("inventory", "simple", "tools", "all"),
        default="all",
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = empty_summary_template()
    exit_code = 0

    if args.step in {"inventory", "all"}:
        inventory = run_inventory(probe=True)
        write_inventory_draft(output_dir, inventory)
        summary.update(
            {
                "checked_at": inventory.checked_at,
                "access_status": inventory.access_status,
                "region": inventory.region,
                "deployment_name": inventory.deployment_name,
                "model_name": inventory.model_name,
                "model_selection_notes": inventory.model_selection_notes,
            }
        )
        write_evidence_json(output_dir / "run-summary-draft.json", summary)
        _print({"step": "inventory", **inventory.to_dict()})
        if inventory.access_status == "blocked":
            return 1

    if args.step in {"simple", "all"}:
        result = simple_completion()
        write_evidence_json(output_dir / "simple-call-draft.json", result.to_dict())
        summary["simple_call"] = {"ok": result.ok, "latency_ms": result.latency_ms}
        summary["sc_003_within_5_min"] = (
            result.latency_ms is not None and result.latency_ms < 5 * 60 * 1000
        )
        write_evidence_json(output_dir / "run-summary-draft.json", summary)
        _print({"step": "simple", **result.to_dict()})
        if not result.ok:
            exit_code = 1

    if args.step in {"tools", "all"}:
        loop = run_tool_loop()
        write_evidence_json(output_dir / "tool-loop-draft.json", loop.to_dict())
        summary["tool_calling_status"] = loop.status
        if summary.get("simple_call") is None:
            summary["simple_call"] = {"ok": False, "latency_ms": None}
        write_evidence_json(output_dir / "run-summary-draft.json", summary)
        _print({"step": "tools", **loop.to_dict()})
        if loop.status == "not_evaluated" and not loop.call.ok:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
