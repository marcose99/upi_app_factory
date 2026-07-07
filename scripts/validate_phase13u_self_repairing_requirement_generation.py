#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13U"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13u"
)
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13u_self_repairing_sla_escalation"
)
AUDIT_PATH = ARTIFACT_DIR / "self_repairing_generation_audit.json"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
REQUIREMENT_PATH = ARTIFACT_DIR / "self_repairing_requirement_package.json"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], payload)


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != PHASE:
        raise AssertionError("Audit phase is not Phase 13U.")
    if audit.get("orchestration_framework") != "langgraph":
        raise AssertionError("Audit does not record LangGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit graph type is not StateGraph.")
    if audit.get("validation_status") != "passed":
        raise AssertionError("Final validation did not pass.")
    if audit.get("repair_attempts") != 1:
        raise AssertionError("Expected exactly one bounded repair attempt.")
    if audit.get("release_ready") is not True:
        raise AssertionError("Audit does not mark release_ready true.")
    if audit.get("human_approval_required") is not True:
        raise AssertionError("Human release approval is not required.")
    if audit.get("passed") is not True:
        raise AssertionError("Audit did not pass.")

    boundary = str(audit.get("truth_boundary", ""))
    if "local and runnable" not in boundary or "simulated mocks only" not in boundary:
        raise AssertionError("Truth boundary is incomplete.")

    agents = [
        str(action.get("agent"))
        for action in audit.get("agent_actions", [])
        if isinstance(action, dict)
    ]
    for required in [
        "requirement_package_agent",
        "design_agent",
        "code_generation_agent",
        "test_generation_agent",
        "docs_generation_agent",
        "validation_agent",
        "failure_diagnosis_agent",
        "bounded_repair_agent",
        "evidence_agent",
    ]:
        if required not in agents:
            raise AssertionError(f"Missing agent action: {required}")

    diagnoses = audit.get("diagnoses", [])
    if not isinstance(diagnoses, list) or len(diagnoses) != 1:
        raise AssertionError("Expected exactly one diagnosis.")
    diagnosis = cast(dict[str, Any], diagnoses[0])
    if diagnosis.get("category") != "generated_behavior_mismatch":
        raise AssertionError("Diagnosis category is not generated_behavior_mismatch.")

    validation_results = audit.get("validation_results", [])
    if not isinstance(validation_results, list) or len(validation_results) < 4:
        raise AssertionError("Expected failed and repaired validation evidence.")
    first_attempt_codes = [
        int(result.get("return_code", -1))
        for result in validation_results
        if isinstance(result, dict) and result.get("attempt") == 0
    ]
    repaired_attempt_codes = [
        int(result.get("return_code", -1))
        for result in validation_results
        if isinstance(result, dict) and result.get("attempt") == 1
    ]
    if not any(code != 0 for code in first_attempt_codes):
        raise AssertionError("First validation attempt did not fail as expected.")
    if not repaired_attempt_codes or any(code != 0 for code in repaired_attempt_codes):
        raise AssertionError("Repaired validation attempt did not pass cleanly.")


def validate_traceability() -> None:
    requirement = load_json(REQUIREMENT_PATH)
    traceability = load_json(TRACEABILITY_PATH)
    if requirement.get("requirement_id") != "REQ-13U-SELF-REPAIRING-SLA-ESCALATION":
        raise AssertionError("Unexpected requirement id.")
    mappings = traceability.get("mappings", [])
    if not isinstance(mappings, list) or not mappings:
        raise AssertionError("Traceability mappings are missing.")
    mapping = cast(dict[str, Any], mappings[0])
    if mapping.get("requirement_id") != requirement.get("requirement_id"):
        raise AssertionError("Traceability mapping does not match requirement.")
    code_files = " ".join(str(item) for item in mapping.get("code_files", []))
    if "contracts.py" not in code_files or "service.py" not in code_files:
        raise AssertionError("Traceability does not map requirement to generated code.")


def validate_generated_files() -> None:
    for relative_path in [
        "phase13u_self_repairing_sla_escalation_app/__init__.py",
        "phase13u_self_repairing_sla_escalation_app/contracts.py",
        "phase13u_self_repairing_sla_escalation_app/service.py",
        "generated_tests/test_generated_sla_escalation.py",
        "README.md",
    ]:
        path = GENERATED_ROOT / relative_path
        if not path.is_file():
            raise AssertionError(f"Missing generated file: {path}")
    service_text = (
        GENERATED_ROOT
        / "phase13u_self_repairing_sla_escalation_app"
        / "service.py"
    ).read_text(encoding="utf-8")
    if "breach_detected = True" in service_text:
        raise AssertionError("Faulty first-draft service was not repaired.")
    if "remaining_minutes < 0" not in service_text:
        raise AssertionError("Repaired service does not contain SLA breach logic.")


def main() -> None:
    audit = load_json(AUDIT_PATH)
    validate_audit(audit)
    validate_traceability()
    validate_generated_files()
    result = {
        "passed": True,
        "phase": PHASE,
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "generated_file_count": len(audit.get("generated_files", [])),
        "validation_status": audit.get("validation_status"),
        "repair_attempts": audit.get("repair_attempts"),
        "diagnosis_count": len(audit.get("diagnoses", [])),
        "release_ready": audit.get("release_ready"),
        "human_approval_required": audit.get("human_approval_required"),
        "requirement_ids": audit.get("requirement_ids"),
        "audit_path": str(AUDIT_PATH),
        "traceability_path": str(TRACEABILITY_PATH),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
