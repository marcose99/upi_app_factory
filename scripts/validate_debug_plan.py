#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.debugging import validate_debug_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--app-root", type=Path, default=None)
    args = parser.parse_args(argv)

    result = validate_debug_plan(
        args.plan.resolve(),
        project_root=args.project_root.resolve() if args.project_root else None,
        app_root=args.app_root.resolve() if args.app_root else None,
    )
    print(
        json.dumps(
            {
                "valid": result.valid,
                "errors": result.errors,
                "plan_sha256": result.plan_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
