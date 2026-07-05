#!/usr/bin/env python3
"""Validate Phase 10.1 official-source governance artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from upi_factory.phase10_1_official_source_registry import (
    validate_official_source_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Phase 10.1 official-source evidence artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_1"
        ),
        help="Directory containing Phase 10.1 artifacts.",
    )
    args = parser.parse_args()

    report = validate_official_source_artifacts(Path(args.output_dir))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
