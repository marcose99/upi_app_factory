from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_application_quality_prompting_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_generated_application_quality_prompting.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert payload == {"errors": [], "passed": True}
