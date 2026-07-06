#!/usr/bin/env python3
# ruff: noqa: E402
"""Validate Phase 10 lifecycle artifacts."""

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

from upi_factory.phase10_lifecycle_planner import validate_lifecycle_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 10 requirement-to-architecture-to-plan artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default="workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10",
        help="Directory containing lifecycle artifacts.",
    )
    args = parser.parse_args()

    report = validate_lifecycle_artifacts(Path(args.output_dir))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
