#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path

from upi_factory.phase11b_real_app_mock_ecosystem_boundary import (
    DEFAULT_APP_ID,
    generate_phase11b_boundary_artifacts,
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
    generated = generate_phase11b_boundary_artifacts(output_dir, DEFAULT_APP_ID)

    print("Generated Phase 11B boundary artifacts:")
    for path in generated:
        print(f"- {path.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
