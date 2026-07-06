#!/usr/bin/env python
# ruff: noqa: E402
from __future__ import annotations

# BEGIN FactoryFromNothing local src import path
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# END FactoryFromNothing local src import path

import json
from pathlib import Path

from upi_factory.phase11c_requirement_intake_capability_classification import (
    DEFAULT_APP_ID,
    validate_phase11c_artifacts,
)


def main() -> int:
    project_root = Path.cwd()
    output_dir = (
        project_root
        / "workspace"
        / "factory_generated"
        / DEFAULT_APP_ID
        / "lifecycle_artifacts"
        / "phase11c"
    )

    report = validate_phase11c_artifacts(output_dir, project_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
