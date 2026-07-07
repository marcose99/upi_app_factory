#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13Y"
POLICY_ID = "POL-13Y-LLM-PROVIDER-ABSTRACTION"
REQUIREMENT_ID = "REQ-13Y-LLM-PROVIDER-ABSTRACTION-SECRET-SAFE-OPENAI-READINESS"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13y"
AUDIT_PATH = ARTIFACT_DIR / "agent_runtime_llm_provider_abstraction_audit.json"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
POLICY_ARTIFACT_PATH = ARTIFACT_DIR / "effective_llm_provider_policy.json"


def load_json_object(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(output: Path | None = None) -> dict[str, object]:
    errors: list[str] = []
    if not AUDIT_PATH.exists():
        errors.append(f"missing audit artifact: {AUDIT_PATH}")
        audit: dict[str, object] = {}
    else:
        audit = load_json_object(AUDIT_PATH)
    if not TRACEABILITY_PATH.exists():
        errors.append(f"missing traceability artifact: {TRACEABILITY_PATH}")
        traceability: dict[str, object] = {}
    else:
        traceability = load_json_object(TRACEABILITY_PATH)
    if not POLICY_ARTIFACT_PATH.exists():
        errors.append(f"missing effective policy artifact: {POLICY_ARTIFACT_PATH}")
        policy: dict[str, object] = {}
    else:
        policy = load_json_object(POLICY_ARTIFACT_PATH)

    required_true_fields = [
        "passed",
        "release_ready",
        "human_approval_required",
        "forbidden_secret_locations_verified",
        "prompt_response_traceability_contract",
        "llm_call_evidence_schema_verified",
        "token_cost_metadata_placeholders",
    ]
    for field in required_true_fields:
        if audit.get(field) is not True:
            errors.append(f"audit field must be true: {field}")

    expected_equal: dict[str, object] = {
        "phase": PHASE,
        "validation_status": "passed",
        "status": "awaiting_human_release_approval",
        "llm_runtime_mode": "deterministic_local",
        "active_llm_provider": "deterministic",
        "openai_provider_mode": "configuration_only",
        "openai_api_key_required": False,
        "openai_api_key_value_serialized": False,
        "live_llm_call_performed": False,
        "policy_id": POLICY_ID,
    }
    for field, expected in expected_equal.items():
        if audit.get(field) != expected:
            errors.append(f"audit field {field!r} expected {expected!r}, got {audit.get(field)!r}")

    if REQUIREMENT_ID not in cast(list[object], audit.get("requirement_ids", [])):
        errors.append("audit missing requirement id")
    if REQUIREMENT_ID not in cast(list[object], traceability.get("requirement_ids", [])):
        errors.append("traceability missing requirement id")
    if policy.get("policy_id") != POLICY_ID:
        errors.append("effective policy id mismatch")

    adapters = cast(list[object], audit.get("verified_llm_provider_adapters", []))
    if "deterministic" not in adapters or "openai_config_only" not in adapters:
        errors.append("expected deterministic and openai_config_only adapters")

    call_evidence = cast(dict[str, object], audit.get("call_evidence", {}))
    for field in [
        "call_id",
        "provider",
        "model",
        "prompt_hash",
        "response_hash",
        "token_usage",
        "cost_estimate",
        "policy_decision_id",
        "requirement_ids",
        "trace_id",
    ]:
        if field not in call_evidence:
            errors.append(f"call evidence missing field: {field}")
    if call_evidence.get("live_call_performed") is not False:
        errors.append("call evidence must confirm no live LLM call was performed")

    public_openai_metadata = cast(dict[str, object], audit.get("openai_config_public_metadata", {}))
    if public_openai_metadata.get("secret_value_serialized") is not False:
        errors.append("OpenAI secret value must never be serialized")
    if public_openai_metadata.get("secret_env_var") != "OPENAI_API_KEY":
        errors.append("OpenAI secret must be represented only as an environment variable reference")

    passed = not errors
    result: dict[str, object] = {
        "phase": PHASE,
        "passed": passed,
        "errors": errors,
        "policy_id": POLICY_ID,
        "requirement_ids": [REQUIREMENT_ID],
        "llm_runtime_mode": audit.get("llm_runtime_mode"),
        "active_llm_provider": audit.get("active_llm_provider"),
        "verified_llm_provider_adapters": audit.get("verified_llm_provider_adapters", []),
        "openai_api_key_required": audit.get("openai_api_key_required"),
        "live_llm_call_performed": audit.get("live_llm_call_performed"),
        "secret_value_serialized": public_openai_metadata.get("secret_value_serialized"),
        "human_approval_required": audit.get("human_approval_required"),
        "release_ready": audit.get("release_ready"),
        "validation_status": "passed" if passed else "failed",
        "traceability_path": str(TRACEABILITY_PATH),
        "audit_path": str(AUDIT_PATH),
    }
    if output is not None:
        write_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Phase 13Y LLM provider abstraction proof.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    validate(args.output)


if __name__ == "__main__":
    main()
