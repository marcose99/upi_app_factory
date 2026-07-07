#!/usr/bin/env python3
"""Governed autonomous self-healing classifier.

This module is intentionally deterministic and stdlib-only. It classifies
validation failures into allowed autonomous repair categories or blocked
human-escalation categories.

It does not perform live provider calls and it does not weaken gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class FailureCategory(str, Enum):
    """Known validation failure categories."""

    MYPY_ACTIVE_SOURCE_SCOPE = "MYPY_ACTIVE_SOURCE_SCOPE"
    MYPY_PACKAGE_MAPPING = "MYPY_PACKAGE_MAPPING"
    RUFF_SAFE_AUTOFIX = "RUFF_SAFE_AUTOFIX"
    DETERMINISTIC_ARTIFACT_REGENERATION = "DETERMINISTIC_ARTIFACT_REGENERATION"
    VALIDATOR_SCHEMA_DRIFT_KNOWN_SAFE = "VALIDATOR_SCHEMA_DRIFT_KNOWN_SAFE"
    UNKNOWN_FAILURE_PATTERN = "UNKNOWN_FAILURE_PATTERN"
    LIVE_PROVIDER_CALL_REQUIRED = "LIVE_PROVIDER_CALL_REQUIRED"
    EXTERNAL_SYSTEM_CALL_REQUIRED = "EXTERNAL_SYSTEM_CALL_REQUIRED"
    POLICY_WEAKENING_REQUIRED = "POLICY_WEAKENING_REQUIRED"
    SECURITY_SUPPRESSION_REQUIRED = "SECURITY_SUPPRESSION_REQUIRED"
    DEPENDENCY_CHANGE_REQUIRED = "DEPENDENCY_CHANGE_REQUIRED"
    DATA_DELETION_REQUIRED = "DATA_DELETION_REQUIRED"
    REGULATORY_RULE_CHANGE_REQUIRED = "REGULATORY_RULE_CHANGE_REQUIRED"
    MERGE_TAG_RELEASE_APPROVAL_REQUIRED = "MERGE_TAG_RELEASE_APPROVAL_REQUIRED"
    SECRETS_OR_CREDENTIALS_EXPOSURE = "SECRETS_OR_CREDENTIALS_EXPOSURE"


class RepairDecision(str, Enum):
    """Governed repair decision."""

    AUTONOMOUS_REPAIR_ALLOWED = "AUTONOMOUS_REPAIR_ALLOWED"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


class RepairAction(str, Enum):
    """Known deterministic local repair actions."""

    NORMALIZE_MYPY_ACTIVE_SOURCE_SCOPE = "NORMALIZE_MYPY_ACTIVE_SOURCE_SCOPE"
    ADD_PACKAGE_BOUNDARY_INIT = "ADD_PACKAGE_BOUNDARY_INIT"
    RUN_RUFF_SAFE_FIX = "RUN_RUFF_SAFE_FIX"
    REGENERATE_DETERMINISTIC_LOCAL_ARTIFACTS = "REGENERATE_DETERMINISTIC_LOCAL_ARTIFACTS"
    NO_AUTONOMOUS_ACTION = "NO_AUTONOMOUS_ACTION"


@dataclass(frozen=True)
class ClassifiedFailure:
    """Classification result for a validation failure."""

    category: FailureCategory
    decision: RepairDecision
    action: RepairAction
    reason: str
    requires_human_approval: bool


ALLOWED_CATEGORIES: frozenset[FailureCategory] = frozenset(
    {
        FailureCategory.MYPY_ACTIVE_SOURCE_SCOPE,
        FailureCategory.MYPY_PACKAGE_MAPPING,
        FailureCategory.RUFF_SAFE_AUTOFIX,
        FailureCategory.DETERMINISTIC_ARTIFACT_REGENERATION,
        FailureCategory.VALIDATOR_SCHEMA_DRIFT_KNOWN_SAFE,
    }
)

BLOCKED_CATEGORIES: frozenset[FailureCategory] = frozenset(
    category for category in FailureCategory if category not in ALLOWED_CATEGORIES
)


def classify_failure(output: str) -> ClassifiedFailure:
    """Classify validation output into a governed repair decision."""

    normalized = output.lower()

    if "live provider" in normalized or "openai api" in normalized:
        return _blocked(
            FailureCategory.LIVE_PROVIDER_CALL_REQUIRED,
            "Live provider usage requires explicit policy gate and human approval.",
        )

    if "external system" in normalized or "banking system" in normalized or "npci" in normalized:
        return _blocked(
            FailureCategory.EXTERNAL_SYSTEM_CALL_REQUIRED,
            "External ecosystem calls must remain mocked unless explicitly approved.",
        )

    if "secret" in normalized or "credential" in normalized:
        return _blocked(
            FailureCategory.SECRETS_OR_CREDENTIALS_EXPOSURE,
            "Potential secrets or credentials exposure requires human review.",
        )

    if "security suppression" in normalized or "nosec" in normalized:
        return _blocked(
            FailureCategory.SECURITY_SUPPRESSION_REQUIRED,
            "Security suppressions require human risk acceptance.",
        )

    if "dependency" in normalized and ("install" in normalized or "upgrade" in normalized):
        return _blocked(
            FailureCategory.DEPENDENCY_CHANGE_REQUIRED,
            "Dependency changes require supply-chain review.",
        )

    if "policy weakening" in normalized or "skip gate" in normalized or "bypass" in normalized:
        return _blocked(
            FailureCategory.POLICY_WEAKENING_REQUIRED,
            "Self-healing must not weaken policy or bypass gates.",
        )

    if "delete" in normalized and ("evidence" in normalized or "data" in normalized):
        return _blocked(
            FailureCategory.DATA_DELETION_REQUIRED,
            "Data or evidence deletion requires explicit human approval.",
        )

    if "merge" in normalized and "release" in normalized:
        return _blocked(
            FailureCategory.MERGE_TAG_RELEASE_APPROVAL_REQUIRED,
            "Merge/tag/release actions remain human-approval-gated.",
        )

    if "source file found twice under different module names" in normalized:
        return ClassifiedFailure(
            category=FailureCategory.MYPY_PACKAGE_MAPPING,
            decision=RepairDecision.AUTONOMOUS_REPAIR_ALLOWED,
            action=RepairAction.ADD_PACKAGE_BOUNDARY_INIT,
            reason="Known MyPy package mapping ambiguity can be repaired locally.",
            requires_human_approval=False,
        )

    if "duplicate module named" in normalized or ("mypy" in normalized and "workspace/" in normalized):
        return ClassifiedFailure(
            category=FailureCategory.MYPY_ACTIVE_SOURCE_SCOPE,
            decision=RepairDecision.AUTONOMOUS_REPAIR_ALLOWED,
            action=RepairAction.NORMALIZE_MYPY_ACTIVE_SOURCE_SCOPE,
            reason="Known active-source boundary issue can be repaired locally.",
            requires_human_approval=False,
        )

    if "ruff" in normalized and ("fixable" in normalized or "--fix" in normalized):
        return ClassifiedFailure(
            category=FailureCategory.RUFF_SAFE_AUTOFIX,
            decision=RepairDecision.AUTONOMOUS_REPAIR_ALLOWED,
            action=RepairAction.RUN_RUFF_SAFE_FIX,
            reason="Known Ruff safe auto-fix path with mandatory re-validation.",
            requires_human_approval=False,
        )

    if "schema_version" in normalized and "validator" in normalized and "known safe" in normalized:
        return ClassifiedFailure(
            category=FailureCategory.VALIDATOR_SCHEMA_DRIFT_KNOWN_SAFE,
            decision=RepairDecision.AUTONOMOUS_REPAIR_ALLOWED,
            action=RepairAction.REGENERATE_DETERMINISTIC_LOCAL_ARTIFACTS,
            reason="Known-safe deterministic validator/schema drift can be regenerated locally.",
            requires_human_approval=False,
        )

    return _blocked(
        FailureCategory.UNKNOWN_FAILURE_PATTERN,
        "Unknown failure patterns require human governance review.",
    )


def _blocked(category: FailureCategory, reason: str) -> ClassifiedFailure:
    return ClassifiedFailure(
        category=category,
        decision=RepairDecision.ESCALATE_TO_HUMAN,
        action=RepairAction.NO_AUTONOMOUS_ACTION,
        reason=reason,
        requires_human_approval=True,
    )


def enforce_iteration_limit(iteration_count: int, max_iterations: int) -> bool:
    """Return whether a self-healing loop may continue."""

    if iteration_count < 0:
        raise ValueError("iteration_count must be non-negative")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    return iteration_count < max_iterations


def summarize_classifications(classifications: Iterable[ClassifiedFailure]) -> dict[str, int]:
    """Summarize classifications for audit evidence."""

    summary = {
        "autonomous_repair_allowed": 0,
        "escalate_to_human": 0,
    }

    for classification in classifications:
        if classification.decision is RepairDecision.AUTONOMOUS_REPAIR_ALLOWED:
            summary["autonomous_repair_allowed"] += 1
        else:
            summary["escalate_to_human"] += 1

    return summary


def main() -> int:
    """Small CLI surface for local manual validation."""

    import argparse

    parser = argparse.ArgumentParser(description="Classify a validation failure for governed self-healing.")
    parser.add_argument("failure_text", nargs="*", help="Failure text to classify.")
    args = parser.parse_args()

    text = " ".join(args.failure_text)
    classification = classify_failure(text)
    print(classification.category.value)
    print(classification.decision.value)
    print(classification.action.value)
    print(classification.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
