#!/usr/bin/env python3
"""Run Phase 11A governed agentic generation harness in shadow mode."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase11a_agentic_code_generation_harness import (
    generate_phase11a_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Phase 11A governed agentic generation harness."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a"
        ),
    )
    parser.add_argument("--app-id", default="upi_dispute_resolution")
    parser.add_argument(
        "--phase10-3-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_3"
        ),
    )
    args = parser.parse_args()

    written = generate_phase11a_artifacts(
        Path(args.output_dir),
        app_id=args.app_id,
        phase10_3_dir=Path(args.phase10_3_dir),
    )
    print("Generated Phase 11A governed agentic harness artifacts:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
