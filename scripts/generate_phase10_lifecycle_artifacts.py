#!/usr/bin/env python3
"""Generate Phase 10 lifecycle artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase10_lifecycle_planner import generate_lifecycle_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 10 requirement-to-architecture-to-plan artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default="workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10",
        help="Directory where lifecycle artifacts will be written.",
    )
    parser.add_argument(
        "--app-id",
        default="upi_dispute_resolution",
        help="Mock application id.",
    )
    args = parser.parse_args()

    written = generate_lifecycle_artifacts(Path(args.output_dir), app_id=args.app_id)
    print("Generated Phase 10 lifecycle artifacts:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
