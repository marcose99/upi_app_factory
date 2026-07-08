#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.validation_runner import run_validation  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 34 governed operator portal validation runner.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the approved validation commands without executing them.",
    )
    parser.add_argument(
        "--collect-all",
        action="store_true",
        help="Continue through the approved command set after failures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_validation(dry_run=args.dry_run, collect_all=args.collect_all)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if args.dry_run or report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
