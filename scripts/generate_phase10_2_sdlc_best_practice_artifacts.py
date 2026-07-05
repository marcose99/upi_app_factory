#!/usr/bin/env python3
"""Generate Phase 10.2 SDLC technology best-practice artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase10_2_sdlc_best_practice_governance import (
    generate_sdlc_best_practice_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 10.2 SDLC technology best-practice artifacts."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase10_2"
        ),
        help="Directory where Phase 10.2 artifacts will be written.",
    )
    parser.add_argument(
        "--app-id",
        default="upi_dispute_resolution",
        help="Mock application id.",
    )
    args = parser.parse_args()

    written = generate_sdlc_best_practice_artifacts(
        Path(args.output_dir),
        app_id=args.app_id,
    )
    print("Generated Phase 10.2 SDLC best-practice artifacts:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
