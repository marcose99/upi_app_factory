from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_phase52_deep_engineering_foundation_validator_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    validator = root / "scripts/validate_phase52_deep_engineering_foundation.py"

    result = subprocess.run(
        [sys.executable, str(validator), "--project-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 52 deep engineering foundation validation passed" in result.stdout
