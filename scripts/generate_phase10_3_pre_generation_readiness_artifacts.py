#!/usr/bin/env python3
"""Generate Phase 10.3 pre-code-generation readiness artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase10_3_pre_generation_readiness import (
    generate_pre_generation_readiness_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 10.3 pre-code-generation readiness artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_3"
        ),
        help="Directory where Phase 10.3 artifacts will be written.",
    )
    parser.add_argument(
        "--app-id",
        default="upi_dispute_resolution",
        help="Mock application id.",
    )
    parser.add_argument(
        "--phase10-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10"
        ),
        help="Directory containing Phase 10 artifacts.",
    )
    parser.add_argument(
        "--phase10-1-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_1"
        ),
        help="Directory containing Phase 10.1 artifacts.",
    )
    parser.add_argument(
        "--phase10-2-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_2"
        ),
        help="Directory containing Phase 10.2 artifacts.",
    )
    args = parser.parse_args()

    written = generate_pre_generation_readiness_artifacts(
        Path(args.output_dir),
        app_id=args.app_id,
        phase10_dir=Path(args.phase10_dir),
        phase10_1_dir=Path(args.phase10_1_dir),
        phase10_2_dir=Path(args.phase10_2_dir),
    )
    print("Generated Phase 10.3 pre-generation readiness artifacts:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
