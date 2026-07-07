#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13Z"
POLICY_ID = "POL-13Z-GOVERNED-LIVE-LLM-DRY-RUN-GATE"
REQUIREMENT_ID = "REQ-13Z-GOVERNED-LIVE-LLM-DRY-RUN-GATE"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13z"
AUDIT_PATH = ARTIFACT_DIR / "governed_live_llm_dry_run_gate_audit.json"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(output: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if not AUDIT_PATH.exists():
        errors.append(f"missing audit path: {AUDIT_PATH}")
        audit: dict[str, Any] = {}
    else:
        audit = _load_json(AUDIT_PATH)

    expected = {
        "passed": True,
        "validation_status": "passed",
        "release_ready": True,
        "policy_id": POLICY_ID,
        "live_llm_requested": True,
        "live_llm_call_allowed": False,
        "live_llm_call_performed": False,
        "dry_run_blocked_live_call": True,
        "human_approval_required": True,
        "human_approval_required_before_live_llm": True,
        "openai_api_key_required": False,
        "openai_api_key_value_serialized": False,
        "secret_value_serialized": False,
        "forbidden_secret_locations_verified": True,
    }
    for key, expected_value in expected.items():
        if audit.get(key) != expected_value:
            errors.append(f"audit[{key!r}] expected {expected_value!r}, got {audit.get(key)!r}")

    requirement_ids = audit.get("requirement_ids", [])
    if REQUIREMENT_ID not in requirement_ids:
        errors.append("required Phase 13Z requirement id not present")
    if not TRACEABILITY_PATH.exists():
        errors.append(f"missing traceability path: {TRACEABILITY_PATH}")
    call_evidence = audit.get("llm_call_dry_run_evidence")
    if not isinstance(call_evidence, dict):
        errors.append("missing llm_call_dry_run_evidence object")
    else:
        if call_evidence.get("live_call_performed") is not False:
            errors.append("call evidence must prove no live call was performed")
        if not call_evidence.get("prompt_hash") or not call_evidence.get("response_hash"):
            errors.append("call evidence must include prompt/response hashes")
        token_usage = call_evidence.get("token_usage")
        if not isinstance(token_usage, dict) or token_usage.get("total_tokens") != 0:
            errors.append("dry-run token usage must be present and zero")

    result: dict[str, Any] = {
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "policy_id": POLICY_ID,
        "requirement_ids": [REQUIREMENT_ID],
        "validation_status": "passed" if not errors else "failed",
        "release_ready": not errors,
        "human_approval_required": True,
        "live_llm_requested": audit.get("live_llm_requested"),
        "live_llm_call_performed": audit.get("live_llm_call_performed"),
        "dry_run_blocked_live_call": audit.get("dry_run_blocked_live_call"),
        "secret_value_serialized": audit.get("secret_value_serialized"),
        "openai_api_key_required": audit.get("openai_api_key_required"),
        "audit_path": str(AUDIT_PATH),
        "traceability_path": str(TRACEABILITY_PATH),
    }
    if output is not None:
        _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Phase 13Z governed live LLM dry-run gate.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = validate(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
