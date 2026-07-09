#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.demo_reviewer_pack import (  # noqa: E402
    build_staged_command_report,
    run_safe_checks,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print or run the Phase 43 one-command demo reviewer pack.",
    )
    parser.add_argument(
        "--run-safe-checks",
        action="store_true",
        help="Run bounded mock-only checks; long-running server startup remains staged.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_safe_checks() if args.run_safe_checks else build_staged_command_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"staged_commands", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
