from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_governed_self_healing_adoption import (
    evaluate_script_path,
    evaluate_script_text,
)


def test_accepts_script_using_governed_phase_runner() -> None:
    result = evaluate_script_text("python scripts/governed_phase_runner.py --phase 13AF")

    assert result.compliant is True
    assert result.uses_governed_runner is True
    assert result.declares_equivalent_control is False


def test_accepts_complete_equivalent_control_declaration() -> None:
    result = evaluate_script_text(
        "# GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL\n"
        "# classify failures, unknown failures escalate to human review, "
        "post-repair gates rerun, audit evidence produced"
    )

    assert result.compliant is True
    assert result.uses_governed_runner is False
    assert result.declares_equivalent_control is True


def test_rejects_incomplete_equivalent_control_declaration() -> None:
    result = evaluate_script_text("# GOVERNED_SELF_HEALING_EQUIVALENT_CONTROL\n# classify only")

    assert result.compliant is False
    assert result.missing_equivalent_phrases


def test_rejects_script_without_runner_or_equivalent_control() -> None:
    result = evaluate_script_text("echo hello")

    assert result.compliant is False
    assert "does not use" in result.reason


def test_rejects_blocked_bypass_patterns_even_when_runner_present() -> None:
    result = evaluate_script_text(
        "python scripts/governed_phase_runner.py --phase 13AF\n"
        "echo skip mypy and bypass gate"
    )

    assert result.compliant is False
    assert "skip mypy" in result.blocked_bypass_patterns
    assert "bypass gate" in result.blocked_bypass_patterns


def test_evaluate_script_path_reports_missing_path(tmp_path: Path) -> None:
    result = evaluate_script_path(tmp_path / "missing.sh")

    assert result.compliant is False
    assert "does not exist" in result.reason


def test_checker_cli_outputs_json_for_compliant_script(tmp_path: Path) -> None:
    script = tmp_path / "phase13af.sh"
    script.write_text("python scripts/governed_phase_runner.py --phase 13AF\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_governed_self_healing_adoption.py",
            "--script",
            str(script),
            "--json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["compliant"] is True
    assert payload["uses_governed_runner"] is True


def test_phase13ae_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ae_governed_self_healing_adoption.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AE governed self-healing adoption artifacts validated." in result.stdout
