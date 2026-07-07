#!/usr/bin/env python3
"""Validate Phase 13W governed multi-capability generated application assembly evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13W"
ARTIFACT_DIR = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13w"
GENERATED_APP_DIR = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "generated_application" / "phase13w_multi_capability_dispute_app"
POLICY_PATH = PROJECT_ROOT / "policies" / "phase13w_multi_capability_assembly_policy.json"


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate() -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = ARTIFACT_DIR / "multi_capability_assembly_manifest.json"
    audit_path = ARTIFACT_DIR / "multi_capability_assembly_audit.json"
    traceability_path = ARTIFACT_DIR / "requirement_traceability_matrix.json"
    generated_test_path = GENERATED_APP_DIR / "generated_tests" / "test_generated_multi_capability_app.py"

    for path in [POLICY_PATH, manifest_path, audit_path, traceability_path, generated_test_path]:
        if not path.exists():
            errors.append(f"Missing required evidence or generated file: {path}")

    manifest: dict[str, Any] = {}
    audit: dict[str, Any] = {}
    policy: dict[str, Any] = {}
    traceability: dict[str, Any] = {}
    if not errors:
        manifest = read_json(manifest_path)
        audit = read_json(audit_path)
        policy = read_json(POLICY_PATH)
        traceability = read_json(traceability_path)
        capabilities = [str(item) for item in manifest.get("assembled_capabilities", [])]
        required = [str(item) for item in policy.get("required_capabilities", [])]
        if manifest.get("validation_status") != "passed":
            errors.append("Manifest validation_status must be passed.")
        if manifest.get("external_ecosystem_boundary") != "mock_only":
            errors.append("External ecosystem boundary must remain mock_only.")
        if len(capabilities) < 2:
            errors.append("At least two capabilities must be assembled.")
        if sorted(capabilities) != sorted(required):
            errors.append("Assembled capabilities must match required policy capabilities.")
        if len(audit.get("policy_decisions", [])) < 1:
            errors.append("Audit must contain at least one policy decision.")
        if len(traceability.get("requirement_links", [])) < 2:
            errors.append("Traceability must include links for both generated capabilities.")
        test_text = generated_test_path.read_text(encoding="utf-8")
        if "sys.path.insert" not in test_text:
            errors.append("Generated tests must be repository-level pytest import isolated.")

    passed = not errors
    return {
        "phase": PHASE,
        "passed": passed,
        "errors": errors,
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "policy_id": policy.get("policy_id", "POL-13W-GOVERNED-MULTI-CAPABILITY-ASSEMBLY"),
        "policy_decision_count": len(audit.get("policy_decisions", [])) if audit else 0,
        "capability_count": len(manifest.get("assembled_capabilities", [])) if manifest else 0,
        "assembled_capabilities": manifest.get("assembled_capabilities", []) if manifest else [],
        "generated_app_dir": str(GENERATED_APP_DIR),
        "traceability_path": str(traceability_path),
        "audit_path": str(audit_path),
        "validation_status": manifest.get("validation_status", "missing") if manifest else "missing",
        "release_ready": passed,
        "human_approval_required": True,
        "external_ecosystem_boundary": "mock_only",
        "llm_runtime_mode": "deterministic_local",
        "openai_api_key_required": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = validate()
    if args.output is not None:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
