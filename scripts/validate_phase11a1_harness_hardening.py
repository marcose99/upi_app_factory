#!/usr/bin/env python3
# ruff: noqa: E402
"""Validate Phase 11A.1 agentic harness hardening artifacts."""

from __future__ import annotations

# BEGIN upi_app_factory local src import path
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# END upi_app_factory local src import path

import argparse
import json
from pathlib import Path

from upi_factory.phase11a1_agentic_harness_hardening import (
    validate_phase11a1_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 11A.1 agentic harness hardening artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a_1"
        ),
    )
    parser.add_argument(
        "--phase11a-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a"
        ),
    )
    parser.add_argument(
        "--phase10-3-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_3"
        ),
    )
    args = parser.parse_args()

    report = validate_phase11a1_artifacts(
        Path(args.output_dir),
        phase11a_dir=Path(args.phase11a_dir),
        phase10_3_dir=Path(args.phase10_3_dir),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
