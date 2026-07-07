from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_governed_autonomous_self_evolving_mode import (
    BLOCKED_ACTIONS,
    HUMAN_GATED_ACTIONS,
    build_governed_autonomous_self_evolving_mode,
    execute_parallel_readonly_gates,
    validate_governed_autonomous_self_evolving_mode,
)


def test_governed_autonomous_self_evolving_plan_is_bounded() -> None:
    audit = build_governed_autonomous_self_evolving_mode(execute_readonly_gates=False)

    assert audit["status"] == "GOVERNED_AUTONOMOUS_SELF_EVOLVING_MODE_READY"
    assert audit["self_evolving_mode_enabled"] is True
    assert audit["governed_autonomy_enabled"] is True
    assert audit["parallel_execution_limited_to_readonly_gates"] is True
    assert audit["safe_repairs_auto_apply_allowed_without_policy"] is False
    assert audit["factory_does_not_self_certify"] is True
    assert audit["official_certification_claimed"] is False
    assert validate_governed_autonomous_self_evolving_mode(audit) == []


def test_irreversible_actions_remain_human_gated() -> None:
    audit = build_governed_autonomous_self_evolving_mode(execute_readonly_gates=False)

    for action in BLOCKED_ACTIONS:
        assert action in audit["blocked_autonomous_actions"]
    for action in HUMAN_GATED_ACTIONS:
        assert action in audit["human_gated_actions"]
    assert audit["auto_merge_performed"] is False
    assert audit["auto_tag_performed"] is False
    assert audit["auto_push_performed"] is False
    assert audit["auto_release_performed"] is False
    assert audit["live_provider_calls_performed"] is False
    assert audit["destructive_cleanup_performed"] is False


def test_parallel_executor_accepts_only_readonly_parallel_safe_gates() -> None:
    unsafe_gate = {
        "gate_id": "unsafe_merge",
        "command": [sys.executable, "--version"],
        "parallel_safe": False,
        "read_only": False,
    }

    try:
        execute_parallel_readonly_gates([unsafe_gate], max_workers=1, timeout_seconds=30)
    except ValueError as exc:
        assert "Only read-only parallel-safe gates" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("unsafe gate was accepted")


def test_parallel_executor_records_successful_readonly_gate() -> None:
    gate = {
        "gate_id": "python_version_readonly",
        "command": [sys.executable, "--version"],
        "parallel_safe": True,
        "read_only": True,
    }

    results = execute_parallel_readonly_gates([gate], max_workers=1, timeout_seconds=30)

    assert results[0]["gate_id"] == "python_version_readonly"
    assert results[0]["status"] == "PASS"
    assert results[0]["returncode"] == 0


def test_policy_and_documentation_preserve_governance_boundary() -> None:
    policy = json.loads(
        Path("policies/phase14r_governed_autonomous_self_evolving_policy.json").read_text(
            encoding="utf-8"
        )
    )
    doc = Path("docs/phase14r/governed_autonomous_self_evolving_mode.md").read_text(
        encoding="utf-8"
    )

    assert "run_parallel_read_only_gates_where_safe" in policy["allowed_autonomous_actions"]
    assert "auto_merge" in policy["blocked_autonomous_actions"]
    assert "auto_certify" in policy["blocked_autonomous_actions"]
    assert "merge" in policy["human_approval_required_for"]
    assert "certification" in doc.lower()
    assert "read-only" in doc.lower()


def test_phase14r_validator_cli_passes_after_audit_generation() -> None:
    audit_path = Path(
        "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14r/"
        "governed_autonomous_self_evolving_mode_audit.json"
    )
    if not audit_path.exists():
        result = subprocess.run(
            [
                sys.executable,
                "scripts/build_governed_autonomous_self_evolving_mode.py",
                "--audit-out",
                str(audit_path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    result = subprocess.run(
        [sys.executable, "scripts/validate_phase14r_governed_autonomous_self_evolving_mode.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
