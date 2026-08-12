from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from factory.generated_application_artifacts import (
    REQUIRED_ARTIFACT_RELATIVE_PATHS,
    materialize_generated_application_artifacts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACKED = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
)
DEPENDENCY_ARTIFACTS = (
    "requirements-bootstrap.lock",
    "requirements.lock",
    "dependency_contract.json",
    "scripts/bootstrap_cleanroom.sh",
    "scripts/validate_dependency_contract.py",
)


def test_tracked_dependency_contract_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_dependency_contract.py"],
        cwd=TRACKED,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "PASS"


def test_materializer_owns_dependency_artifacts(tmp_path: Path) -> None:
    for artifact in DEPENDENCY_ARTIFACTS:
        assert artifact in REQUIRED_ARTIFACT_RELATIVE_PATHS

    output = tmp_path / "generated_application"
    materialize_generated_application_artifacts(
        project_root=PROJECT_ROOT,
        application_root=output,
    )
    for artifact in DEPENDENCY_ARTIFACTS:
        assert (output / artifact).read_bytes() == (TRACKED / artifact).read_bytes()


def test_tampered_lock_fails_closed(tmp_path: Path) -> None:
    for artifact in DEPENDENCY_ARTIFACTS:
        target = tmp_path / artifact
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((TRACKED / artifact).read_bytes())

    start_script = tmp_path / "scripts/start_local.sh"
    start_script.write_bytes((TRACKED / "scripts/start_local.sh").read_bytes())

    lock = tmp_path / "requirements.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8") + "tampered>=1\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(tmp_path / "scripts/validate_dependency_contract.py")],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode != 0
