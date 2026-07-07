#!/usr/bin/env python3
"""Validate Phase 13X agent runtime abstraction evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13X"
POLICY_ID = "POL-13X-AGENT-RUNTIME-ABSTRACTION"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13x"


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(output: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = ARTIFACT_DIR / "agent_runtime_abstraction_manifest.json"
    audit_path = ARTIFACT_DIR / "agent_runtime_abstraction_audit.json"
    traceability_path = ARTIFACT_DIR / "requirement_traceability_matrix.json"
    policy_path = ARTIFACT_DIR / "effective_agent_runtime_abstraction_policy.json"
    report_path = ARTIFACT_DIR / "agent_runtime_abstraction_report.md"

    for path in [manifest_path, audit_path, traceability_path, policy_path, report_path]:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing_or_empty:{path}")

    manifest: dict[str, Any] = {}
    audit: dict[str, Any] = {}
    traceability: dict[str, Any] = {}
    policy: dict[str, Any] = {}
    if not errors:
        manifest = load_json(manifest_path)
        audit = load_json(audit_path)
        traceability = load_json(traceability_path)
        policy = load_json(policy_path)
        if manifest.get("phase") != PHASE:
            errors.append("manifest_phase_mismatch")
        if manifest.get("policy_id") != POLICY_ID:
            errors.append("manifest_policy_id_mismatch")
        if not manifest.get("runtime_independence_passed"):
            errors.append("runtime_independence_not_passed")
        if manifest.get("openai_api_key_required") is not False:
            errors.append("openai_key_should_not_be_required")
        if sorted(manifest.get("adapters_verified", [])) != ["deterministic", "langgraph"]:
            errors.append("required_adapters_not_verified")
        if traceability.get("policy_id") != POLICY_ID:
            errors.append("traceability_policy_id_mismatch")
        if "AgentRuntimePort" not in traceability.get("contracts", []):
            errors.append("agent_runtime_port_missing")
        events = audit.get("events", [])
        event_names = {event.get("event") for event in events}
        required_events = {
            "runtime_abstraction_contracts_defined",
            "runtime_adapters_verified",
            "framework_independence_policy_evaluated",
        }
        if not required_events.issubset(event_names):
            errors.append("audit_required_events_missing")
        rules = policy.get("runtime_independence_rules", {})
        if rules.get("factory_core_must_use_ports") is not True:
            errors.append("policy_does_not_require_ports")
        if rules.get("framework_specific_imports_allowed_only_in_adapters") is not True:
            errors.append("policy_does_not_confine_framework_imports")

    result = {
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "policy_id": POLICY_ID,
        "runtime_independence_passed": bool(manifest.get("runtime_independence_passed")) if manifest else False,
        "verified_runtime_adapters": manifest.get("adapters_verified", []) if manifest else [],
        "agent_framework_independence_status": "adapter_boundary_established" if not errors else "failed",
        "active_framework_adapter": "langgraph",
        "llm_runtime_mode": "deterministic_local",
        "openai_api_key_required": False,
        "human_approval_required": bool(manifest.get("human_approval_required")) if manifest else False,
        "release_ready": not errors,
        "audit_path": str(audit_path),
        "traceability_path": str(traceability_path),
    }
    if output is not None:
        write_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = validate(args.output)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
