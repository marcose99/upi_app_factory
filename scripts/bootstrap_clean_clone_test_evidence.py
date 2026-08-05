#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.prerequisite_artifacts import (  # noqa: E402
    DEFAULT_LIFECYCLE_ARTIFACT_ROOT,
    materialize_clean_clone_test_evidence,
)

DEFAULT_TARGET_ROOT = DEFAULT_LIFECYCLE_ARTIFACT_ROOT


def bootstrap(target_root: Path) -> dict[str, Any]:
    return materialize_clean_clone_test_evidence(
        PROJECT_ROOT,
        target_root=target_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize deterministic lifecycle evidence required by "
            "clean-clone tests."
        )
    )
    parser.add_argument(
        "--target-root",
        type=Path,
        default=DEFAULT_TARGET_ROOT,
    )
    args = parser.parse_args()

    try:
        result = bootstrap(args.target_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "status": "FAILED",
            "errors": [f"{type(exc).__name__}:{exc}"],
            "llm_calls": 0,
            "real_payment_calls": "disabled",
            "official_certification_claimed": False,
        }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
