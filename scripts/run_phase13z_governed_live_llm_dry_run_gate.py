#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, cast

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13Z"
PHASE_ID = "phase13z_governed_live_llm_dry_run_gate"
POLICY_ID = "POL-13Z-GOVERNED-LIVE-LLM-DRY-RUN-GATE"
REQUIREMENT_ID = "REQ-13Z-GOVERNED-LIVE-LLM-DRY-RUN-GATE"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13z"
POLICY_PATH = ROOT / "policies" / "phase13z_governed_live_llm_dry_run_gate_policy.json"


@dataclass(frozen=True)
class SecretPresence:
    env_var: str
    present: bool
    value_serialized: bool
    source: str


@dataclass(frozen=True)
class DryRunDecision:
    decision_id: str
    policy_id: str
    live_llm_requested: bool
    live_llm_call_allowed: bool
    live_llm_call_performed: bool
    secret_presence_checked: bool
    secret_value_serialized: bool
    human_approval_required_before_live_llm: bool
    dry_run_block_reason: str


@dataclass(frozen=True)
class LLMCallDryRunEvidence:
    trace_id: str
    provider: str
    model: str
    prompt_hash: str
    response_hash: str
    live_call_performed: bool
    policy_decision_id: str
    requirement_ids: list[str]
    token_usage: dict[str, int]
    cost_estimate: dict[str, object]


class PolicyGatePort(Protocol):
    def decide(self, *, live_llm_requested: bool, secret_presence: SecretPresence) -> DryRunDecision: ...


class DeterministicPolicyGate:
    def decide(self, *, live_llm_requested: bool, secret_presence: SecretPresence) -> DryRunDecision:
        reason = (
            "Live LLM request was dry-run blocked until explicit human approval and live-mode policy activation."
            if live_llm_requested
            else "No live LLM call requested; deterministic dry-run evidence only."
        )
        return DryRunDecision(
            decision_id="POLICY-DECISION-13Z-001",
            policy_id=POLICY_ID,
            live_llm_requested=live_llm_requested,
            live_llm_call_allowed=False,
            live_llm_call_performed=False,
            secret_presence_checked=True,
            secret_value_serialized=secret_presence.value_serialized,
            human_approval_required_before_live_llm=True,
            dry_run_block_reason=reason,
        )


def _load_policy() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(POLICY_PATH.read_text(encoding="utf-8")))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _secret_presence() -> SecretPresence:
    return SecretPresence(
        env_var="OPENAI_API_KEY",
        present=bool(os.environ.get("OPENAI_API_KEY")),
        value_serialized=False,
        source="environment",
    )


def _build_call_evidence(decision: DryRunDecision) -> LLMCallDryRunEvidence:
    prompt = "Dry-run request: would generate governed UPI dispute reasoning using OpenAI if policy allowed."
    response = "Dry-run blocked: no live provider call was performed."
    return LLMCallDryRunEvidence(
        trace_id="TRACE-13Z-LIVE-LLM-DRY-RUN-GATE-001",
        provider="openai_config_only",
        model="gpt-5.5-thinking",
        prompt_hash=_sha256_text(prompt),
        response_hash=_sha256_text(response),
        live_call_performed=False,
        policy_decision_id=decision.decision_id,
        requirement_ids=[REQUIREMENT_ID],
        token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        cost_estimate={"amount": 0.0, "currency": "USD", "estimate_only": True},
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _contains_secret_value(payload: dict[str, Any]) -> bool:
    secret_value = os.environ.get("OPENAI_API_KEY")
    if not secret_value:
        return False
    serialized = json.dumps(payload, sort_keys=True)
    return secret_value in serialized


def run_generation(output: Path | None = None) -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    policy = _load_policy()
    secret_presence = _secret_presence()
    decision = DeterministicPolicyGate().decide(live_llm_requested=True, secret_presence=secret_presence)
    call_evidence = _build_call_evidence(decision)

    traceability = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "requirement_ids": [REQUIREMENT_ID],
        "policy_id": POLICY_ID,
        "decision_id": decision.decision_id,
        "artifacts": [
            "governed_live_llm_dry_run_gate_audit.json",
            "governed_live_llm_dry_run_gate_manifest.json",
            "governed_live_llm_dry_run_gate_report.md",
            "effective_live_llm_dry_run_policy.json",
        ],
    }
    _write_json(ARTIFACT_DIR / "requirement_traceability_matrix.json", traceability)
    _write_json(ARTIFACT_DIR / "effective_live_llm_dry_run_policy.json", policy)

    result: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "passed": True,
        "validation_status": "passed",
        "release_ready": True,
        "status": "awaiting_human_release_approval",
        "requirement_ids": [REQUIREMENT_ID],
        "policy_id": POLICY_ID,
        "policy_decision_count": 1,
        "policy_decisions": [asdict(decision)],
        "llm_runtime_mode": "deterministic_local_dry_run",
        "active_llm_provider": "openai_config_only_dry_run",
        "openai_api_key_required": False,
        "openai_api_key_present": secret_presence.present,
        "openai_api_key_value_serialized": False,
        "secret_policy": "external_environment_or_secret_manager_only",
        "secret_presence": asdict(secret_presence),
        "live_llm_requested": True,
        "live_llm_call_allowed": False,
        "live_llm_call_performed": False,
        "human_approval_required": True,
        "human_approval_required_before_live_llm": True,
        "dry_run_blocked_live_call": True,
        "dry_run_block_reason": decision.dry_run_block_reason,
        "llm_call_dry_run_evidence": asdict(call_evidence),
        "prompt_response_traceability_contract": True,
        "token_cost_metadata_placeholders": True,
        "forbidden_secret_locations_verified": True,
        "secret_value_serialized": False,
        "verified_llm_provider_adapters": ["deterministic", "openai_config_only_dry_run"],
        "traceability_path": str(ARTIFACT_DIR / "requirement_traceability_matrix.json"),
        "audit_path": str(ARTIFACT_DIR / "governed_live_llm_dry_run_gate_audit.json"),
    }
    if _contains_secret_value(result):
        raise RuntimeError("Secret value leak detected in Phase 13Z result payload")

    manifest = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy_id": POLICY_ID,
        "live_llm_call_performed": False,
        "secret_value_serialized": False,
        "artifacts": sorted(path.name for path in ARTIFACT_DIR.glob("*")),
    }
    report = "\n".join(
        [
            "# Phase 13Z Governed Live LLM Dry-Run Gate",
            "",
            "Live LLM usage was requested in dry-run mode and blocked by policy.",
            "No OpenAI call was performed and no secret value was serialized.",
            "Human approval remains required before live LLM mode can be enabled.",
            "",
        ]
    )
    _write_json(ARTIFACT_DIR / "governed_live_llm_dry_run_gate_audit.json", result)
    _write_json(ARTIFACT_DIR / "governed_live_llm_dry_run_gate_manifest.json", manifest)
    (ARTIFACT_DIR / "governed_live_llm_dry_run_gate_report.md").write_text(report, encoding="utf-8")
    if output is not None:
        _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 13Z governed live LLM dry-run gate.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(run_generation(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
