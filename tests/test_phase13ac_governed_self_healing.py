from __future__ import annotations

import subprocess
import sys

from scripts.governed_self_healing import (
    FailureCategory,
    RepairAction,
    RepairDecision,
    classify_failure,
    enforce_iteration_limit,
    summarize_classifications,
)


def test_classifies_workspace_mypy_failure_as_autonomous_source_scope_repair() -> None:
    result = classify_failure(
        "python -m mypy . failed: workspace/generated/foo.py duplicate module named foo"
    )

    assert result.category is FailureCategory.MYPY_ACTIVE_SOURCE_SCOPE
    assert result.decision is RepairDecision.AUTONOMOUS_REPAIR_ALLOWED
    assert result.action is RepairAction.NORMALIZE_MYPY_ACTIVE_SOURCE_SCOPE
    assert result.requires_human_approval is False


def test_classifies_package_mapping_failure_as_autonomous_package_boundary_repair() -> None:
    result = classify_failure(
        "Source file found twice under different module names: validate and scripts.validate"
    )

    assert result.category is FailureCategory.MYPY_PACKAGE_MAPPING
    assert result.decision is RepairDecision.AUTONOMOUS_REPAIR_ALLOWED
    assert result.action is RepairAction.ADD_PACKAGE_BOUNDARY_INIT


def test_blocks_live_provider_calls() -> None:
    result = classify_failure("repair requires OpenAI API live provider call")

    assert result.category is FailureCategory.LIVE_PROVIDER_CALL_REQUIRED
    assert result.decision is RepairDecision.ESCALATE_TO_HUMAN
    assert result.requires_human_approval is True


def test_blocks_unknown_failure_patterns() -> None:
    result = classify_failure("unexpected validator failure without a known safe classifier")

    assert result.category is FailureCategory.UNKNOWN_FAILURE_PATTERN
    assert result.decision is RepairDecision.ESCALATE_TO_HUMAN
    assert result.action is RepairAction.NO_AUTONOMOUS_ACTION


def test_iteration_limit_is_enforced() -> None:
    assert enforce_iteration_limit(0, 5) is True
    assert enforce_iteration_limit(4, 5) is True
    assert enforce_iteration_limit(5, 5) is False


def test_classification_summary_supports_audit_counts() -> None:
    results = [
        classify_failure("workspace/foo.py duplicate module named foo"),
        classify_failure("repair requires credential exposure"),
    ]

    summary = summarize_classifications(results)

    assert summary == {
        "autonomous_repair_allowed": 1,
        "escalate_to_human": 1,
    }


def test_phase13ac_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ac_governed_self_healing.py"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AC governed self-healing artifacts validated." in result.stdout
