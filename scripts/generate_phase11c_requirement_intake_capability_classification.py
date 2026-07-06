#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path

from upi_factory.phase11c_requirement_intake_capability_classification import (
    DEFAULT_APP_ID,
    generate_phase11c_artifacts,
)


def main() -> int:
    project_root = Path.cwd()
    requirement_doc = (
        project_root
        / "workspace"
        / "factory_inputs"
        / DEFAULT_APP_ID
        / "requirements"
        / "requirement_v1.md"
    )
    output_dir = (
        project_root
        / "workspace"
        / "factory_generated"
        / DEFAULT_APP_ID
        / "lifecycle_artifacts"
        / "phase11c"
    )

    generated = generate_phase11c_artifacts(output_dir, requirement_doc)

    print("Generated Phase 11C requirement-intake artifacts:")
    for path in generated:
        print(f"- {path.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
