#!/usr/bin/env python3
"""Run a deterministic governed workflow and write checkpoint evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from factory.workflows.state_machine import run_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed workflow orchestration.")
    parser.add_argument("--run-id", default="manual_workflow_run", help="Workflow run identifier.")
    parser.add_argument("--output-root", default=None, help="Optional parent directory for workflow runs.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing run directory.")
    parser.add_argument(
        "--stop-after-step",
        default=None,
        help="Optional workflow step ID used to create a paused run for checkpoint review.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root).resolve() if args.output_root else None
    result = run_workflow(
        project_root=project_root,
        run_id=args.run_id,
        output_root=output_root,
        force=args.force,
        stop_after_step=args.stop_after_step,
    )
    print(json.dumps({"run_id": result.run_id, "run_dir": str(result.run_dir), "status": result.status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
