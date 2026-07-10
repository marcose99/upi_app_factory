from __future__ import annotations

import argparse
import json
from pathlib import Path

from factory.operator_portal.lifecycle_run_resolution import (
    LifecycleRunResolutionService,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path.home() / ".local/state/upi_app_factory",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--base-commit")
    parsed = parser.parse_args()
    service = LifecycleRunResolutionService(
        project_root=parsed.project_root,
        state_root=parsed.state_root,
    )
    print(
        json.dumps(
            service.report(
                parsed.phase,
                expected_manifest_path=parsed.manifest,
                expected_base_commit=parsed.base_commit,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
