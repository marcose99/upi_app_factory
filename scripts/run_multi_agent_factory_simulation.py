#!/usr/bin/env python3
"""Run a deterministic governed multi-agent role simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from factory.agents.role_runner import run_multi_agent_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a governed deterministic multi-agent role simulation."
    )
    parser.add_argument("--run-id", default="manual_agent_run", help="Stable run id.")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing workspace for the same run id.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    run_dir = run_multi_agent_simulation(
        project_root=project_root,
        run_id=args.run_id,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "run_dir": str(run_dir),
                "status": "passed",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
