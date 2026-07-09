#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[3]
REQUIRED_FILES = [
    APP_ROOT / ".env.example",
    APP_ROOT / "README.md",
    APP_ROOT / "docs/local_run_pack/README.md",
    APP_ROOT / "scripts/start_local.sh",
    APP_ROOT / "scripts/health_check.py",
    APP_ROOT / "scripts/smoke_test.py",
    APP_ROOT / "scripts/clean_local_artifacts.sh",
]


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required run-pack file: {path.relative_to(REPO_ROOT)}")
    result = subprocess.run(
        [sys.executable, str(APP_ROOT / "scripts/smoke_test.py")],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(result.stdout + result.stderr)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("Generated app local run pack validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
