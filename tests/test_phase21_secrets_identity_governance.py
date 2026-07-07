from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def test_phase21_runner_generates_secret_safe_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    identity = tmp_path / "identity.json"
    secrets = tmp_path / "secrets.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase21_secrets_identity_governance.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--identity-out",
            str(identity),
            "--secrets-out",
            str(secrets),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit_data = load_json(audit)
    secrets_data = load_json(secrets)
    assert audit_data["real_secret_storage_performed"] is False
    assert audit_data["live_identity_provider_calls_performed"] is False
    assert secrets_data["real_secrets_stored_in_repo"] is False


def test_phase21_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase21_secrets_identity_governance.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
