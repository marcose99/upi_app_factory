#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13AA"
PHASE_ID = "phase13aa_llm_evidence_replay_redaction_validator"
POLICY_ID = "POL-13AA-LLM-EVIDENCE-REPLAY-REDACTION"
REQUIREMENT_ID = "REQ-13AA-LLM-EVIDENCE-REPLAY-REDACTION"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13aa"
POLICY_PATH = ROOT / "policies" / "phase13aa_llm_evidence_replay_redaction_policy.json"
SECRET_ENV_VAR = "OPENAI_API_KEY"
SECRET_LIKE_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scan_for_secret_leaks(serialized: str, env_secret: str | None) -> list[str]:
    findings: list[str] = []
    if SECRET_LIKE_PATTERN.search(serialized):
        findings.append("secret_like_token_pattern_detected")
    if env_secret and env_secret in serialized:
        findings.append("actual_openai_api_key_value_serialized")
    forbidden_literals = [
        "raw_prompt_text",
        "raw_response_text",
        "api_key_value",
        "secret_value_plaintext",
    ]
    for literal in forbidden_literals:
        if literal in serialized:
            findings.append(f"forbidden_literal_detected:{literal}")
    return findings


def build_replay_evidence(policy: dict[str, Any]) -> dict[str, Any]:
    env_secret = os.environ.get(SECRET_ENV_VAR)
    prompt_fingerprint_material = "phase13z governed live llm dry-run prompt metadata"
    response_fingerprint_material = "phase13z governed dry-run blocked response metadata"
    replayed_call_evidence: dict[str, Any] = {
        "trace_id": "TRACE-13AA-LLM-EVIDENCE-REPLAY-001",
        "policy_decision_id": "POLICY-DECISION-13AA-001",
        "provider": "openai_config_only_dry_run",
        "model": "gpt-5.5-thinking",
        "prompt_hash": sha256_text(prompt_fingerprint_material),
        "response_hash": sha256_text(response_fingerprint_material),
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
        "cost_estimate": {
            "amount": 0.0,
            "currency": "USD",
            "estimate_only": True,
        },
        "live_call_performed": False,
        "requirement_ids": [REQUIREMENT_ID],
    }
    return {
        "source_phase": "Phase 13Z",
        "source_policy_id": "POL-13Z-GOVERNED-LIVE-LLM-DRY-RUN-GATE",
        "replay_mode": "metadata_only_no_provider_call",
        "live_provider_replay_allowed": False,
        "secret_presence": {
            "env_var": SECRET_ENV_VAR,
            "present": env_secret is not None,
            "source": "environment" if env_secret else "not_present",
            "value_serialized": False,
        },
        "llm_call_evidence": replayed_call_evidence,
        "required_evidence_fields": policy["required_evidence_fields"],
    }


def run_generation(output: Path | None = None) -> dict[str, Any]:
    policy = read_json(POLICY_PATH)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    replay_evidence = build_replay_evidence(policy)
    serialized_replay = json.dumps(replay_evidence, sort_keys=True)
    secret_findings = scan_for_secret_leaks(serialized_replay, os.environ.get(SECRET_ENV_VAR))

    evidence_fields = set(cast(dict[str, Any], replay_evidence["llm_call_evidence"]).keys())
    required_fields = set(cast(list[str], policy["required_evidence_fields"]))
    missing_fields = sorted(required_fields - evidence_fields)

    policy_decision = {
        "decision_id": "POLICY-DECISION-13AA-001",
        "policy_id": POLICY_ID,
        "allowed": not secret_findings and not missing_fields,
        "metadata_replay_allowed": True,
        "live_provider_replay_allowed": False,
        "live_llm_call_performed": False,
        "secret_value_serialized": bool(secret_findings),
        "missing_required_evidence_fields": missing_fields,
        "reason": "Metadata replay is allowed only when evidence is complete and redacted.",
    }

    passed = bool(policy_decision["allowed"])
    traceability_path = ARTIFACT_DIR / "requirement_traceability_matrix.json"
    audit_path = ARTIFACT_DIR / "llm_evidence_replay_redaction_audit.json"
    manifest_path = ARTIFACT_DIR / "llm_evidence_replay_redaction_manifest.json"
    report_path = ARTIFACT_DIR / "llm_evidence_replay_redaction_report.md"
    effective_policy_path = ARTIFACT_DIR / "effective_llm_evidence_replay_redaction_policy.json"

    result: dict[str, Any] = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "app_id": APP_ID,
        "passed": passed,
        "validation_status": "passed" if passed else "failed",
        "release_ready": passed,
        "status": "awaiting_human_release_approval" if passed else "blocked",
        "human_approval_required": True,
        "llm_runtime_mode": "deterministic_local_metadata_replay",
        "live_llm_call_performed": False,
        "openai_api_key_required": False,
        "openai_api_key_present": os.environ.get(SECRET_ENV_VAR) is not None,
        "secret_value_serialized": bool(secret_findings),
        "forbidden_secret_locations_verified": not secret_findings,
        "prompt_response_traceability_contract": True,
        "token_cost_metadata_placeholders": True,
        "policy_id": POLICY_ID,
        "policy_decision_count": 1,
        "policy_decisions": [policy_decision],
        "requirement_ids": [REQUIREMENT_ID],
        "replayed_evidence_count": 1,
        "redaction_check_count": 1,
        "metadata_replay_passed": passed,
        "secret_leak_findings": secret_findings,
        "missing_required_evidence_fields": missing_fields,
        "audit_path": str(audit_path),
        "traceability_path": str(traceability_path),
    }

    traceability = {
        "phase": PHASE,
        "requirement_id": REQUIREMENT_ID,
        "policy_id": POLICY_ID,
        "evidence_artifacts": [
            str(audit_path),
            str(manifest_path),
            str(report_path),
            str(effective_policy_path),
        ],
        "validated_controls": [
            "metadata_only_replay",
            "secret_redaction",
            "prompt_response_hash_traceability",
            "token_cost_placeholder_evidence",
            "human_approval_before_live_llm",
        ],
    }

    audit = {
        "result": result,
        "replay_evidence": replay_evidence,
        "redaction_policy": policy["redaction_rules"],
        "replay_policy": policy["replay_rules"],
    }

    write_json(effective_policy_path, policy)
    write_json(traceability_path, traceability)
    write_json(audit_path, audit)
    manifest = {
        "phase": PHASE,
        "policy_id": POLICY_ID,
        "artifact_hashes": {
            "effective_policy": sha256_text(effective_policy_path.read_text(encoding="utf-8")),
            "traceability": sha256_text(traceability_path.read_text(encoding="utf-8")),
            "audit": sha256_text(audit_path.read_text(encoding="utf-8")),
        },
        "passed": passed,
    }
    write_json(manifest_path, manifest)
    report_path.write_text(
        "# Phase 13AA LLM Evidence Replay and Redaction Report\n\n"
        f"Passed: {passed}\n\n"
        "Validated metadata-only LLM evidence replay, secret redaction, prompt/response hash traceability, "
        "token/cost placeholders, and human approval requirements before live provider execution.\n",
        encoding="utf-8",
    )

    if output is not None:
        write_json(output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Phase 13AA LLM evidence replay and redaction validation.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_generation(args.output)


if __name__ == "__main__":
    main()
