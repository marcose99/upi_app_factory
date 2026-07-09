#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.end_to_end_run_flow import run_end_to_end_portal_flow  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase 37 governed end-to-end local portal flow.",
    )
    parser.add_argument(
        "--validation-command-id",
        action="append",
        dest="validation_command_ids",
        help="Approved Phase 34 validation command id. Defaults to phase34_runner_self_check.",
    )
    parser.add_argument(
        "--stop-on-first-failure",
        action="store_true",
        help="Stop the validation runner after the first failed allowlisted command.",
    )
    parser.add_argument(
        "--no-write-report",
        action="store_true",
        help="Return the report without writing the Phase 37 lifecycle report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command_ids = tuple(args.validation_command_ids or ["phase34_runner_self_check"])
    report = run_end_to_end_portal_flow(
        validation_command_ids=command_ids,
        collect_all=not args.stop_on_first_failure,
        write_report=not args.no_write_report,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
