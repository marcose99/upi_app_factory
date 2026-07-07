from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.validate_clean_slate_human_approval import (
    APPROVAL_TARGET_PATH,
    REQUIRED_ACKNOWLEDGEMENTS,
    approval_template,
    validate_approval_file,
    validate_approval_payload,
)


def valid_token() -> dict[str, Any]:
    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled test token."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def test_blank_approval_template_is_not_valid_approval() -> None:
    result = validate_approval_payload(approval_template())

    assert result.valid is False
    assert any("approved_by" in error for error in result.errors)


def test_valid_approval_token_passes() -> None:
    result = validate_approval_payload(valid_token())

    assert result.valid is True
    assert result.errors == ()


def test_wrong_target_is_rejected() -> None:
    token = valid_token()
    token["target_path"] = "docs"

    result = validate_approval_payload(token)

    assert result.valid is False
    assert "Invalid target_path" in result.errors


def test_missing_acknowledgement_is_rejected() -> None:
    token = valid_token()
    token["acknowledgements"] = [item for item in REQUIRED_ACKNOWLEDGEMENTS if item != "ACK_RELEASE_REMAINS_HUMAN_GATED"]

    result = validate_approval_payload(token)

    assert result.valid is False
    assert any("ACK_RELEASE_REMAINS_HUMAN_GATED" in error for error in result.errors)


def test_approval_file_validation_handles_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")

    result = validate_approval_file(path)

    assert result.valid is False
    assert result.errors


def test_emit_template_cli_contains_expected_target() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_clean_slate_human_approval.py", "--emit-template"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["target_path"] == APPROVAL_TARGET_PATH
    assert payload["approved_by"] == ""


def test_approval_validator_cli_accepts_valid_token(tmp_path: Path) -> None:
    token_path = tmp_path / "approval.json"
    token_path.write_text(json.dumps(valid_token(), indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_clean_slate_human_approval.py",
            "--approval-token",
            str(token_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True


def test_phase13ah_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ah_clean_slate_human_approval.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AH clean-slate human approval artifacts validated." in result.stdout
