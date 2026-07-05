#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase11b_real_app_mock_ecosystem_boundary import (
    DEFAULT_APP_ID,
    validate_phase11b_boundary_artifacts,
)


def main() -> int:
    project_root = Path.cwd()
    output_dir = (
        project_root
        / "workspace"
        / "factory_generated"
        / DEFAULT_APP_ID
        / "lifecycle_artifacts"
        / "phase11b"
    )
    report = validate_phase11b_boundary_artifacts(output_dir, project_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
