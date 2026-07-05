#!/usr/bin/env python3
"""Generate Phase 11A.1 agentic harness hardening artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase11a1_agentic_harness_hardening import (
    generate_phase11a1_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 11A.1 agentic harness hardening artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a_1"
        ),
    )
    parser.add_argument("--app-id", default="upi_dispute_resolution")
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

    written = generate_phase11a1_artifacts(
        Path(args.output_dir),
        app_id=args.app_id,
        phase11a_dir=Path(args.phase11a_dir),
        phase10_3_dir=Path(args.phase10_3_dir),
    )
    print("Generated Phase 11A.1 hardening artifacts:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
