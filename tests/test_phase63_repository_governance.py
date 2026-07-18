from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_phase63_repository_governance_validator() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validate_phase63_repository_governance.py"),
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"status": "passed"' in completed.stdout
