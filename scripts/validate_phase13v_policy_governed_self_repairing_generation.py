#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import pathlib
import sys
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13V"
REQUIREMENT_ID = "REQ-13V-POLICY-GOVERNED-DISPUTE-TRIAGE"
POLICY_ID = "POL-13V-POLICY-GOVERNED-GENERATION"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13v"
)
CAPABILITY_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13v_policy_governed_dispute_triage"
)
PACKAGE_NAME = "phase13v_policy_governed_dispute_triage_app"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate_generated_behavior(errors: list[str]) -> None:
    if str(CAPABILITY_DIR) not in sys.path:
        sys.path.insert(0, str(CAPABILITY_DIR))
    for module_name in list(sys.modules):
        if module_name == PACKAGE_NAME or module_name.startswith(f"{PACKAGE_NAME}."):
            del sys.modules[module_name]
    package = importlib.import_module(PACKAGE_NAME)
    request_class = getattr(package, "DisputeTriageRequest")
    triage_dispute = getattr(package, "triage_dispute")
    decision = triage_dispute(
        request_class(
            dispute_id="UPI-DISP-13V-VALIDATOR",
            age_hours=1,
            amount_minor=500,
            customer_segment="retail",
            regulatory_complaint=True,
            fraud_signal_score=1,
        )
    )
    if decision.action != "ESCALATE" or decision.priority != "CRITICAL":
        errors.append("Generated behavior does not escalate regulatory complaints.")
    if POLICY_ID not in decision.policy_ids:
        errors.append("Generated decision does not expose governing policy id.")


def validate() -> dict[str, Any]:
    errors: list[str] = []
    audit_path = ARTIFACT_DIR / "policy_governed_generation_audit.json"
    manifest_path = ARTIFACT_DIR / "policy_governed_generation_manifest.json"
    traceability_path = ARTIFACT_DIR / "requirement_traceability_matrix.json"
    audit = load_json(audit_path)
    manifest = load_json(manifest_path)
    traceability = load_json(traceability_path)

    if audit.get("passed") is not True:
        errors.append("Audit did not pass.")
    if audit.get("orchestration_framework") != "langgraph":
        errors.append("LangGraph orchestration was not recorded.")
    if audit.get("graph_type") != "StateGraph":
        errors.append("StateGraph type was not recorded.")
    if audit.get("human_approval_required") is not True:
        errors.append("Human release gate is missing.")
    if audit.get("repair_attempts") != 1:
        errors.append("Expected exactly one policy-authorized repair attempt.")
    if len(cast(list[Any], audit.get("diagnoses", []))) != 1:
        errors.append("Expected exactly one diagnosis.")
    if len(cast(list[Any], audit.get("policy_decisions", []))) != 1:
        errors.append("Expected exactly one policy decision.")
    if len(cast(list[Any], audit.get("repair_evidence", []))) != 1:
        errors.append("Expected exactly one repair evidence item.")

    governance = cast(dict[str, Any], audit.get("policy_governance", {}))
    llm_runtime = cast(dict[str, Any], governance.get("llm_runtime", {}))
    if governance.get("policy_id") != POLICY_ID:
        errors.append("Policy governance id mismatch.")
    if llm_runtime.get("mode") != "deterministic_local":
        errors.append("Expected deterministic_local LLM runtime mode.")
    if llm_runtime.get("openai_api_key_required") is not False:
        errors.append("OpenAI key must not be required for deterministic local mode.")
    if llm_runtime.get("secrets_required") != []:
        errors.append("No secrets should be required for this phase.")

    decisions = cast(list[dict[str, Any]], audit.get("policy_decisions", []))
    if decisions and decisions[0].get("status") != "allowed":
        errors.append("Repair policy decision was not allowed.")
    if REQUIREMENT_ID not in cast(list[str], audit.get("requirement_ids", [])):
        errors.append("Requirement id missing from audit.")
    if traceability.get("policy_id") != POLICY_ID:
        errors.append("Traceability matrix does not link policy id.")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("Manifest does not link policy id.")

    validate_generated_behavior(errors)

    generated_test = (
        CAPABILITY_DIR
        / "generated_tests"
        / "test_generated_policy_governed_triage.py"
    )
    if "sys.path.insert" not in generated_test.read_text(encoding="utf-8"):
        errors.append("Generated test import isolation shim is missing.")

    return {
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "policy_id": governance.get("policy_id"),
        "llm_runtime_mode": llm_runtime.get("mode"),
        "openai_api_key_required": llm_runtime.get("openai_api_key_required"),
        "requirement_ids": audit.get("requirement_ids"),
        "diagnosis_count": len(cast(list[Any], audit.get("diagnoses", []))),
        "policy_decision_count": len(cast(list[Any], audit.get("policy_decisions", []))),
        "repair_attempts": audit.get("repair_attempts"),
        "generated_file_count": len(cast(list[Any], audit.get("generated_files", []))),
        "validation_status": audit.get("validation_status"),
        "release_ready": audit.get("release_ready"),
        "human_approval_required": audit.get("human_approval_required"),
        "audit_path": str(audit_path),
        "traceability_path": str(traceability_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    result = validate()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
