#!/usr/bin/env python3
"""Validate FPQ-R1 generated-application dependency and SBOM contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_portal_requirements_driven_application_engineering import (
    AdapterError,
    validate_generated_application_cyclonedx,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPLICATION_ROOT = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the generated application's lock-derived CycloneDX SBOM"
    )
    parser.add_argument(
        "--application-root",
        type=Path,
        default=DEFAULT_APPLICATION_ROOT,
    )
    args = parser.parse_args()
    try:
        result = validate_generated_application_cyclonedx(
            args.application_root.resolve()
        )
    except (AdapterError, OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
