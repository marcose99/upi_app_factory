#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13S"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13s"
)
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13s_evidence_upload_validation"
)
AUDIT_PATH = ARTIFACT_DIR / "agent_owned_application_generation_audit.json"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
REQUIREMENT_PATH = ARTIFACT_DIR / "requirement_package.json"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected JSON object in {path}")
    return cast(dict[str, Any], payload)


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != PHASE:
        raise AssertionError("Audit phase is not Phase 13S.")
    if audit.get("orchestration_framework") != "langgraph":
        raise AssertionError("Audit does not record LangGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit graph_type is not StateGraph.")
    if audit.get("validation_status") != "passed":
        raise AssertionError("Generated capability validation did not pass.")
    if audit.get("release_ready") is not True:
        raise AssertionError("Audit does not mark the capability release-ready.")
    if audit.get("human_approval_required") is not True:
        raise AssertionError("Human release approval is not required.")
    truth_boundary = str(audit.get("truth_boundary", ""))
    if "local and runnable" not in truth_boundary:
        raise AssertionError("Truth boundary does not state local runnable scope.")
    if "simulated mocks only" not in truth_boundary:
        raise AssertionError("Truth boundary does not preserve mock ecosystem scope.")

    action_agents = [
        str(action.get("agent"))
        for action in audit.get("agent_actions", [])
        if isinstance(action, dict)
    ]
    for required_agent in [
        "requirement_package_agent",
        "design_agent",
        "code_generation_agent",
        "test_generation_agent",
        "docs_generation_agent",
        "validation_agent",
        "evidence_agent",
    ]:
        if required_agent not in action_agents:
            raise AssertionError(f"Missing agent action: {required_agent}")

    generated_files = audit.get("generated_files", [])
    if not isinstance(generated_files, list) or len(generated_files) < 6:
        raise AssertionError("Audit does not contain enough generated files.")
    generated_paths = "\n".join(
        str(item.get("path", "")) for item in generated_files if isinstance(item, dict)
    )
    for expected in [
        "contracts.py",
        "service.py",
        "test_phase13s_agent_owned_application_generation.py",
        "agent_owned_application_capability_generation.md",
    ]:
        if expected not in generated_paths:
            raise AssertionError(f"Generated file is missing from audit: {expected}")

    validation_results = audit.get("validation_results", [])
    if not isinstance(validation_results, list) or len(validation_results) < 2:
        raise AssertionError("Audit does not include validation command evidence.")
    for result in validation_results:
        if not isinstance(result, dict) or result.get("return_code") != 0:
            raise AssertionError("One or more validation commands failed.")


def validate_traceability() -> None:
    requirement = load_json(REQUIREMENT_PATH)
    traceability = load_json(TRACEABILITY_PATH)
    if requirement.get("requirement_id") != "REQ-13S-EVIDENCE-UPLOAD-VALIDATION":
        raise AssertionError("Requirement package id is wrong.")
    mappings = traceability.get("mappings", [])
    if not isinstance(mappings, list) or not mappings:
        raise AssertionError("Traceability matrix has no mappings.")
    mapping = cast(dict[str, Any], mappings[0])
    if mapping.get("requirement_id") != requirement.get("requirement_id"):
        raise AssertionError("Traceability mapping does not reference the requirement.")
    code_files = " ".join(str(item) for item in mapping.get("code_files", []))
    test_files = " ".join(str(item) for item in mapping.get("test_files", []))
    if "contracts.py" not in code_files or "service.py" not in code_files:
        raise AssertionError("Traceability does not map requirement to generated code.")
    if "test_phase13s_agent_owned_application_generation.py" not in test_files:
        raise AssertionError("Traceability does not map requirement to generated test.")


def validate_generated_application_files() -> None:
    for relative_path in [
        "phase13s_evidence_upload_validation_app/__init__.py",
        "phase13s_evidence_upload_validation_app/contracts.py",
        "phase13s_evidence_upload_validation_app/service.py",
        "README.md",
    ]:
        path = GENERATED_ROOT / relative_path
        if not path.is_file():
            raise AssertionError(f"Missing generated application file: {path}")


def main() -> None:
    audit = load_json(AUDIT_PATH)
    validate_audit(audit)
    validate_traceability()
    validate_generated_application_files()
    result = {
        "passed": True,
        "phase": PHASE,
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "generated_file_count": len(audit.get("generated_files", [])),
        "validation_status": audit.get("validation_status"),
        "release_ready": audit.get("release_ready"),
        "human_approval_required": audit.get("human_approval_required"),
        "requirement_ids": audit.get("requirement_ids"),
        "audit_path": str(AUDIT_PATH),
        "traceability_path": str(TRACEABILITY_PATH),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
