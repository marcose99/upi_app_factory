#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13AA"
POLICY_ID = "POL-13AA-LLM-EVIDENCE-REPLAY-REDACTION"
REQUIREMENT_ID = "REQ-13AA-LLM-EVIDENCE-REPLAY-REDACTION"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13aa"
AUDIT_PATH = ARTIFACT_DIR / "llm_evidence_replay_redaction_audit.json"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
SECRET_ENV_VAR = "OPENAI_API_KEY"
SECRET_LIKE_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(output: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    if not AUDIT_PATH.exists():
        errors.append(f"missing audit path: {AUDIT_PATH}")
        audit: dict[str, Any] = {}
    else:
        audit = read_json(AUDIT_PATH)

    result = cast(dict[str, Any], audit.get("result", {}))
    replay_evidence = cast(dict[str, Any], audit.get("replay_evidence", {}))
    serialized_artifacts = ""
    for path in ARTIFACT_DIR.glob("*"):
        if path.is_file():
            serialized_artifacts += path.read_text(encoding="utf-8", errors="ignore")

    env_secret = os.environ.get(SECRET_ENV_VAR)
    if SECRET_LIKE_PATTERN.search(serialized_artifacts):
        errors.append("secret_like_token_pattern_detected_in_phase13aa_artifacts")
    if env_secret and env_secret in serialized_artifacts:
        errors.append("actual_openai_api_key_value_serialized_in_phase13aa_artifacts")
    for literal in ["raw_prompt_text", "raw_response_text", "api_key_value", "secret_value_plaintext"]:
        if literal in serialized_artifacts:
            errors.append(f"forbidden_literal_detected:{literal}")

    if result.get("passed") is not True:
        errors.append("result did not pass")
    if result.get("live_llm_call_performed") is not False:
        errors.append("live LLM call must not be performed")
    if result.get("secret_value_serialized") is not False:
        errors.append("secret value serialization must be false")
    if result.get("policy_id") != POLICY_ID:
        errors.append("unexpected policy id")
    if REQUIREMENT_ID not in cast(list[str], result.get("requirement_ids", [])):
        errors.append("requirement id missing")
    if not TRACEABILITY_PATH.exists():
        errors.append("traceability matrix missing")

    llm_call = cast(dict[str, Any], replay_evidence.get("llm_call_evidence", {}))
    for key in ["trace_id", "policy_decision_id", "provider", "model", "prompt_hash", "response_hash", "token_usage", "cost_estimate"]:
        if key not in llm_call:
            errors.append(f"missing replay evidence field: {key}")
    if "prompt" in llm_call or "response" in llm_call:
        errors.append("raw prompt/response fields are forbidden")

    passed = not errors
    validation: dict[str, Any] = {
        "phase": PHASE,
        "passed": passed,
        "validation_status": "passed" if passed else "failed",
        "release_ready": passed,
        "errors": errors,
        "policy_id": POLICY_ID,
        "requirement_ids": [REQUIREMENT_ID],
        "audit_path": str(AUDIT_PATH),
        "traceability_path": str(TRACEABILITY_PATH),
        "live_llm_call_performed": False,
        "openai_api_key_required": False,
        "secret_value_serialized": False,
        "metadata_replay_passed": passed,
        "human_approval_required": True,
    }
    if output is not None:
        write_json(output, validation)
    print(json.dumps(validation, indent=2, sort_keys=True))
    return validation


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate Phase 13AA LLM evidence replay and redaction artifacts.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    validation = validate(args.output)
    if not validation["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
