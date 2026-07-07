#!/usr/bin/env python3
"""Validate local generated-application capability certification artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VALID_STATUSES = {
    "CERTIFIED_LOCAL",
    "CERTIFIED_WITH_WARNINGS",
    "NOT_CERTIFIED",
    "BLOCKED_BY_POLICY",
}

REQUIRED_DIMENSIONS = {
    "unit_tests",
    "integration_tests",
    "contract_api_tests",
    "domain_rule_tests",
    "negative_error_path_tests",
    "boundary_mock_ecosystem_tests",
    "regression_tests",
    "policy_governance_tests",
    "audit_evidence_tests",
    "type_checks",
    "lint_static_quality_checks",
    "security_static_scanning_hooks",
    "dependency_supply_chain_checks",
    "performance_smoke_load_checks",
    "resilience_idempotency_replay_checks",
    "operator_handover_runbook_checks",
    "capability_certification_report_generation",
}

REQUIRED_FILES = {
    "policy": "capability_certification_policy.json",
    "matrix": "capability_certification_matrix.json",
    "audit": "capability_certification_audit.json",
    "traceability": "requirement_traceability_matrix.json",
    "report": "capability_certification_report.md",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_policy(policy: dict[str, Any], failures: list[str]) -> None:
    require(policy.get("schema_version") == "capability-certification-policy.v1", "Bad policy schema", failures)
    require(policy.get("mode") == "LOCAL_FIRST_ONLY", "Policy must be LOCAL_FIRST_ONLY", failures)
    require(policy.get("live_provider_calls_allowed") is False, "Policy must block live provider calls", failures)
    require(policy.get("human_approval_required_for_release") is True, "Policy must require human approval", failures)
    require(set(policy.get("allowed_statuses", [])) == VALID_STATUSES, "Policy status vocabulary mismatch", failures)
    require(set(policy.get("minimum_required_quality_dimensions", [])) == REQUIRED_DIMENSIONS, "Policy dimensions mismatch", failures)


def validate_matrix(matrix: dict[str, Any], failures: list[str]) -> None:
    require(matrix.get("schema_version") == "capability-certification-matrix.v1", "Bad matrix schema", failures)
    require(matrix.get("certification_mode") == "LOCAL_FIRST_DETERMINISTIC", "Matrix mode mismatch", failures)
    require(matrix.get("live_provider_calls_allowed") is False, "Matrix must block live provider calls", failures)
    require(matrix.get("human_approval_required_for_release") is True, "Matrix must require human approval", failures)
    require(set(matrix.get("status_vocabulary", [])) == VALID_STATUSES, "Matrix status vocabulary mismatch", failures)
    require(set(matrix.get("quality_dimensions", [])) == REQUIRED_DIMENSIONS, "Matrix dimensions mismatch", failures)

    capabilities = matrix.get("capabilities")
    require(isinstance(capabilities, list) and bool(capabilities), "Matrix must contain capabilities", failures)
    if not isinstance(capabilities, list):
        return

    seen: set[str] = set()
    for index, capability in enumerate(capabilities):
        require(isinstance(capability, dict), f"Capability {index} must be an object", failures)
        if not isinstance(capability, dict):
            continue

        capability_id = capability.get("capability_id")
        require(isinstance(capability_id, str) and bool(capability_id), f"Capability {index} missing id", failures)
        if isinstance(capability_id, str):
            require(capability_id not in seen, f"Duplicate capability: {capability_id}", failures)
            seen.add(capability_id)

        require(capability.get("release_status") in VALID_STATUSES, f"{capability_id} invalid release status", failures)

        results = capability.get("quality_results")
        require(isinstance(results, dict), f"{capability_id} quality_results must be object", failures)
        if not isinstance(results, dict):
            continue

        require(set(results) == REQUIRED_DIMENSIONS, f"{capability_id} quality dimensions mismatch", failures)
        for dimension, result in results.items():
            require(isinstance(result, dict), f"{capability_id}.{dimension} result must be object", failures)
            if not isinstance(result, dict):
                continue
            require(result.get("status") in VALID_STATUSES, f"{capability_id}.{dimension} invalid status", failures)
            evidence_refs = result.get("evidence_refs")
            evidence_ok = (
                isinstance(evidence_refs, list)
                and bool(evidence_refs)
                and all(isinstance(ref, str) and ref for ref in evidence_refs)
            )
            require(evidence_ok, f"{capability_id}.{dimension} missing evidence", failures)


def validate_audit(audit: dict[str, Any], failures: list[str]) -> None:
    require(audit.get("schema_version") == "capability-certification-audit.v1", "Bad audit schema", failures)
    require(audit.get("audit_mode") == "LOCAL_DETERMINISTIC_SOURCE_CONTROLLED", "Bad audit mode", failures)
    require(audit.get("live_provider_calls_performed") is False, "Audit must confirm no live calls", failures)
    require(audit.get("human_approval_required_for_release") is True, "Audit must require human approval", failures)
    decision = audit.get("decision")
    require(isinstance(decision, dict), "Audit decision must be object", failures)
    if isinstance(decision, dict):
        require(decision.get("overall_status") in VALID_STATUSES, "Bad audit overall status", failures)


def validate_traceability(traceability: dict[str, Any], matrix: dict[str, Any], failures: list[str]) -> None:
    require(traceability.get("schema_version") == "requirement-traceability-matrix.v1", "Bad traceability schema", failures)

    matrix_capability_ids = {
        capability.get("capability_id")
        for capability in matrix.get("capabilities", [])
        if isinstance(capability, dict)
    }

    requirements = traceability.get("requirements")
    require(isinstance(requirements, list) and bool(requirements), "Traceability must contain requirements", failures)
    if not isinstance(requirements, list):
        return

    for requirement in requirements:
        require(isinstance(requirement, dict), "Traceability requirement must be object", failures)
        if not isinstance(requirement, dict):
            continue
        requirement_id = requirement.get("requirement_id")
        require(isinstance(requirement_id, str) and requirement_id.startswith("REQ-13AB-"), "Bad requirement id", failures)
        capability_ids = requirement.get("capability_ids")
        require(isinstance(capability_ids, list) and bool(capability_ids), f"{requirement_id} missing capabilities", failures)
        if isinstance(capability_ids, list):
            for capability_id in capability_ids:
                require(capability_id in matrix_capability_ids, f"{requirement_id} unknown capability {capability_id}", failures)
        require(requirement.get("governance_status") in VALID_STATUSES, f"{requirement_id} bad governance status", failures)


def validate_report(path: Path, failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for phrase in [
        "phase 13ab",
        "local_first_deterministic",
        "certified_local",
        "certified_with_warnings",
        "not_certified",
        "blocked_by_policy",
        "human approval",
    ]:
        require(phrase in text, f"Report missing phrase: {phrase}", failures)


def validate_artifact_dir(artifact_dir: Path) -> list[str]:
    failures: list[str] = []
    paths = {name: artifact_dir / filename for name, filename in REQUIRED_FILES.items()}
    for name, path in paths.items():
        require(path.exists(), f"Missing {name}: {path}", failures)

    if failures:
        return failures

    policy = load_json(paths["policy"])
    matrix = load_json(paths["matrix"])
    audit = load_json(paths["audit"])
    traceability = load_json(paths["traceability"])

    validate_policy(policy, failures)
    validate_matrix(matrix, failures)
    validate_audit(audit, failures)
    validate_traceability(traceability, matrix, failures)
    validate_report(paths["report"], failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 13AB certification artifacts.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ab"),
    )
    args = parser.parse_args()

    failures = validate_artifact_dir(args.artifact_dir)
    if failures:
        print("Capability certification validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Capability certification validation passed: {args.artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
