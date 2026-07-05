#!/usr/bin/env python3
"""Generate Phase 11A.2 realistic mock engineering guardrail artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from upi_factory.phase11a2_realistic_mock_engineering_guardrails import (
    apply_prompt_enhancements,
    generate_phase11a2_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 11A.2 realistic mock engineering guardrails."
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a_2"
        ),
    )
    parser.add_argument("--app-id", default="upi_dispute_resolution")
    parser.add_argument(
        "--phase11a1-dir",
        default=(
            "workspace/factory_generated/upi_dispute_resolution/"
            "lifecycle_artifacts/phase11a_1"
        ),
    )
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    changed_prompts = apply_prompt_enhancements(project_root)
    written = generate_phase11a2_artifacts(
        Path(args.output_dir),
        app_id=args.app_id,
        phase11a1_dir=Path(args.phase11a1_dir),
    )

    print("Generated Phase 11A.2 artifacts:")
    for path in written:
        print(f"- {path}")

    if changed_prompts:
        print("Enhanced prompt files:")
        for path in changed_prompts:
            print(f"- {path}")
    else:
        print("Prompt enhancements already present.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
