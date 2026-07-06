#!/usr/bin/env python3
# ruff: noqa: E402
"""Validate Phase 11A.2 realistic mock engineering guardrails."""

from __future__ import annotations

# BEGIN FactoryFromNothing local src import path
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# END FactoryFromNothing local src import path

import argparse
import json
from pathlib import Path

from upi_factory.phase11a2_realistic_mock_engineering_guardrails import (
    validate_phase11a2_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 11A.2 realistic mock engineering guardrails."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a_2"
        ),
    )
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    report = validate_phase11a2_artifacts(
        Path(args.output_dir),
        project_root=Path(args.project_root),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
