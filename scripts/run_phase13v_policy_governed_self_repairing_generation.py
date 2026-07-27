#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, StateGraph

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13V"
PHASE_ID = "phase13v_policy_governed_self_repairing_generation"
BASELINE_TAG = "v0.13.20-self-repairing-requirement-generation-runner"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_SOURCE_PATH = PROJECT_ROOT / "policies" / "phase13v_policy_governed_generation_policy.json"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13v"
)
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
)
CAPABILITY_DIR = GENERATED_ROOT / "phase13v_policy_governed_dispute_triage"
PACKAGE_NAME = "phase13v_policy_governed_dispute_triage_app"
PACKAGE_DIR = CAPABILITY_DIR / PACKAGE_NAME
GENERATED_TEST_DIR = CAPABILITY_DIR / "generated_tests"
REQUIREMENT_ID = "REQ-13V-POLICY-GOVERNED-DISPUTE-TRIAGE"
POLICY_ID = "POL-13V-POLICY-GOVERNED-GENERATION"

ValidationStatus = Literal["not_run", "failed", "passed"]
PolicyDecisionStatus = Literal["allowed", "denied"]


class GeneratedFile(TypedDict):
    path: str
    purpose: str
    sha256: str


class AgentAction(TypedDict):
    agent: str
    action: str
    status: str
    detail: str


class ValidationResult(TypedDict):
    attempt: int
    passed: bool
    check: str
    detail: str


class Diagnosis(TypedDict):
    attempt: int
    root_cause: str
    target_file: str
    repair_kind: str
    evidence: str


class PolicyDecision(TypedDict):
    attempt: int
    status: PolicyDecisionStatus
    policy_id: str
    target_file: str
    reason: str


class RepairEvidence(TypedDict):
    attempt: int
    target_file: str
    policy_decision: PolicyDecisionStatus
    diff_summary: str
    sha256_after: str


class GenerationState(TypedDict):
    app_id: str
    phase: str
    phase_id: str
    objective: str
    requirement_ids: list[str]
    policy: dict[str, Any]
    generated_files: list[GeneratedFile]
    agent_actions: list[AgentAction]
    validation_results: list[ValidationResult]
    diagnoses: list[Diagnosis]
    policy_decisions: list[PolicyDecision]
    repair_evidence: list[RepairEvidence]
    validation_status: ValidationStatus
    repair_attempts: int
    max_repair_attempts: int
    release_ready: bool
    status: str
    errors: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_file(path: pathlib.Path, content: str, purpose: str) -> GeneratedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": relative(path), "purpose": purpose, "sha256": sha256_text(content)}


def upsert_generated_file(
    files: list[GeneratedFile],
    generated_file: GeneratedFile,
) -> list[GeneratedFile]:
    return [item for item in files if item["path"] != generated_file["path"]] + [
        generated_file
    ]


def add_action(
    state: GenerationState,
    agent: str,
    action: str,
    status: str,
    detail: str,
) -> None:
    state["agent_actions"].append(
        {"agent": agent, "action": action, "status": status, "detail": detail}
    )


def load_policy() -> dict[str, Any]:
    if not POLICY_SOURCE_PATH.exists():
        raise FileNotFoundError(f"Policy file is missing: {POLICY_SOURCE_PATH}")
    return cast(dict[str, Any], json.loads(POLICY_SOURCE_PATH.read_text(encoding="utf-8")))


def path_matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def contracts_code() -> str:
    return '''from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisputeTriageRequest:
    dispute_id: str
    age_hours: int
    amount_minor: int
    customer_segment: str
    regulatory_complaint: bool
    fraud_signal_score: int


@dataclass(frozen=True)
class DisputeTriageDecision:
    dispute_id: str
    action: str
    priority: str
    rationale: str
    policy_ids: tuple[str, ...]
'''


def faulty_service_code() -> str:
    return '''from __future__ import annotations

from .contracts import DisputeTriageDecision, DisputeTriageRequest


TRIAGE_POLICY_ID = "POL-13V-DISPUTE-TRIAGE"


def triage_dispute(request: DisputeTriageRequest) -> DisputeTriageDecision:
    """Faulty first draft intentionally created to prove governed repair."""
    if request.age_hours > 72 and request.fraud_signal_score >= 95:
        return DisputeTriageDecision(
            dispute_id=request.dispute_id,
            action="ESCALATE",
            priority="HIGH",
            rationale="Old high-fraud dispute requires escalation.",
            policy_ids=(TRIAGE_POLICY_ID,),
        )
    return DisputeTriageDecision(
        dispute_id=request.dispute_id,
        action="STANDARD_REVIEW",
        priority="NORMAL",
        rationale="Dispute remains in standard review queue.",
        policy_ids=(TRIAGE_POLICY_ID,),
    )
'''


def repaired_service_code() -> str:
    return '''from __future__ import annotations

from .contracts import DisputeTriageDecision, DisputeTriageRequest


TRIAGE_POLICY_ID = "POL-13V-DISPUTE-TRIAGE"
GOVERNED_REPAIR_POLICY_ID = "POL-13V-POLICY-GOVERNED-GENERATION"


def triage_dispute(request: DisputeTriageRequest) -> DisputeTriageDecision:
    """Policy-governed triage decision for locally generated UPI disputes."""
    if request.regulatory_complaint:
        return DisputeTriageDecision(
            dispute_id=request.dispute_id,
            action="ESCALATE",
            priority="CRITICAL",
            rationale="Regulatory complaint requires immediate governed escalation.",
            policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
        )
    if (
        request.age_hours > 72
        or request.fraud_signal_score >= 85
        or request.amount_minor >= 100000
    ):
        return DisputeTriageDecision(
            dispute_id=request.dispute_id,
            action="SENIOR_REVIEW",
            priority="HIGH",
            rationale="High-risk dispute requires senior review before closure.",
            policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
        )
    return DisputeTriageDecision(
        dispute_id=request.dispute_id,
        action="STANDARD_REVIEW",
        priority="NORMAL",
        rationale="Dispute remains in standard review queue.",
        policy_ids=(TRIAGE_POLICY_ID, GOVERNED_REPAIR_POLICY_ID),
    )
'''


def init_code() -> str:
    return '''from .contracts import DisputeTriageDecision, DisputeTriageRequest
from .service import triage_dispute

__all__ = ["DisputeTriageDecision", "DisputeTriageRequest", "triage_dispute"]
'''


def generated_test_code() -> str:
    return f'''from __future__ import annotations

import importlib
import pathlib
import sys

GENERATED_APP_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(GENERATED_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_APP_ROOT))

generated_app = importlib.import_module("{PACKAGE_NAME}")
DisputeTriageRequest = generated_app.DisputeTriageRequest
triage_dispute = generated_app.triage_dispute


def test_regulatory_complaint_requires_critical_escalation() -> None:
    decision = triage_dispute(
        DisputeTriageRequest(
            dispute_id="UPI-DISP-13V-001",
            age_hours=2,
            amount_minor=2500,
            customer_segment="retail",
            regulatory_complaint=True,
            fraud_signal_score=10,
        )
    )
    assert decision.action == "ESCALATE"
    assert decision.priority == "CRITICAL"
    assert "POL-13V-POLICY-GOVERNED-GENERATION" in decision.policy_ids
'''


def readme_code() -> str:
    return '''# Phase 13V Policy-Governed Dispute Triage

This generated capability demonstrates policy-governed self-repair.

The first generated service draft intentionally misses the regulatory-complaint
escalation rule. The LangGraph runner validates the generated behavior,
diagnoses the mismatch, checks the repair against the policy file, applies a
bounded repair only to generated application files, reruns validation, and writes
audit evidence.

No OpenAI API key is required for this phase. The diagnosis and repair are
deterministic and local. Future LLM-backed diagnosis can be enabled only through
explicit provider configuration and secret injection outside the repository.
'''


def requirement_package() -> dict[str, Any]:
    return {
        "requirement_id": REQUIREMENT_ID,
        "title": "Policy-governed UPI dispute triage escalation",
        "capability": "phase13v_policy_governed_dispute_triage",
        "rules": [
            "Regulatory complaints must be escalated with CRITICAL priority.",
            "Older, high-value, or high-fraud disputes require senior review.",
            "All repairs must be bounded by generation policy before patching.",
            "External banks, rails, and regulatory interfaces remain simulated.",
        ],
        "acceptance_criteria": [
            "Generated first draft is allowed to fail one behavioral check.",
            "Diagnosis must identify the missing regulatory escalation rule.",
            "Policy gate must allow only generated application file repair.",
            "Validation must pass after bounded repair.",
            "Audit must include policy decision and repair evidence.",
        ],
    }


def requirement_package_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    next_state["requirement_ids"] = [REQUIREMENT_ID]
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "policy_governed_requirement_package.json"
    write_file(path, json.dumps(requirement_package(), indent=2, sort_keys=True) + "\n", "Requirement package")
    add_action(
        next_state,
        "requirement_package_agent",
        "load_requirement_package",
        "passed",
        "Loaded governed UPI dispute triage requirement package.",
    )
    return next_state


def policy_load_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    policy = load_policy()
    runtime = cast(dict[str, Any], policy.get("llm_runtime", {}))
    if runtime.get("openai_api_key_required") is not False:
        next_state["errors"].append("Policy must not require OpenAI key in deterministic local mode.")
        next_state["validation_status"] = "failed"
    next_state["policy"] = policy
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "effective_generation_policy.json"
    write_file(path, json.dumps(policy, indent=2, sort_keys=True) + "\n", "Effective policy")
    add_action(
        next_state,
        "policy_load_agent",
        "load_effective_policy",
        "passed",
        "Loaded deterministic-local policy with no required secrets.",
    )
    return next_state


def code_generation_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    files = list(next_state["generated_files"])
    files.append(write_file(PACKAGE_DIR / "contracts.py", contracts_code(), "Generated contracts"))
    files.append(write_file(PACKAGE_DIR / "service.py", faulty_service_code(), "Faulty first-draft service"))
    files.append(write_file(PACKAGE_DIR / "__init__.py", init_code(), "Generated package exports"))
    files.append(write_file(PACKAGE_DIR / "py.typed", "", "Typing marker"))
    next_state["generated_files"] = files
    add_action(
        next_state,
        "code_generation_agent",
        "generate_faulty_first_draft",
        "passed",
        "Generated intentionally incomplete first-draft triage service.",
    )
    return next_state


def test_generation_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    files = list(next_state["generated_files"])
    files.append(
        write_file(
            GENERATED_TEST_DIR / "test_generated_policy_governed_triage.py",
            generated_test_code(),
            "Generated behavioral regression test with import isolation",
        )
    )
    next_state["generated_files"] = files
    add_action(
        next_state,
        "test_generation_agent",
        "generate_behavioral_test",
        "passed",
        "Generated test for regulatory-complaint escalation rule.",
    )
    return next_state


def docs_generation_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    files = list(next_state["generated_files"])
    files.append(write_file(CAPABILITY_DIR / "README.md", readme_code(), "Generated README"))
    next_state["generated_files"] = files
    add_action(
        next_state,
        "docs_generation_agent",
        "generate_readme",
        "passed",
        "Generated local run and governance notes.",
    )
    return next_state


def clear_generated_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == PACKAGE_NAME or module_name.startswith(f"{PACKAGE_NAME}."):
            del sys.modules[module_name]


def validate_generated_behavior(attempt: int) -> ValidationResult:
    if str(CAPABILITY_DIR) not in sys.path:
        sys.path.insert(0, str(CAPABILITY_DIR))
    clear_generated_modules()
    importlib.invalidate_caches()
    package = importlib.import_module(PACKAGE_NAME)
    request_class = getattr(package, "DisputeTriageRequest")
    triage_dispute = getattr(package, "triage_dispute")
    decision = triage_dispute(
        request_class(
            dispute_id="UPI-DISP-13V-001",
            age_hours=2,
            amount_minor=2500,
            customer_segment="retail",
            regulatory_complaint=True,
            fraud_signal_score=10,
        )
    )
    passed = decision.action == "ESCALATE" and decision.priority == "CRITICAL"
    return {
        "attempt": attempt,
        "passed": passed,
        "check": "regulatory_complaint_requires_critical_escalation",
        "detail": f"Observed action={decision.action}, priority={decision.priority}",
    }


def validation_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    attempt = next_state["repair_attempts"]
    result = validate_generated_behavior(attempt)
    next_state["validation_results"] = next_state["validation_results"] + [result]
    next_state["validation_status"] = "passed" if result["passed"] else "failed"
    if result["passed"]:
        next_state["release_ready"] = True
        next_state["status"] = "awaiting_human_release_approval"
    add_action(
        next_state,
        "validation_agent",
        "validate_generated_behavior",
        "passed" if result["passed"] else "failed",
        result["detail"],
    )
    return next_state


def failure_diagnosis_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    service_path = PACKAGE_DIR / "service.py"
    diagnosis: Diagnosis = {
        "attempt": next_state["repair_attempts"] + 1,
        "root_cause": "Generated service omitted mandatory regulatory complaint escalation.",
        "target_file": relative(service_path),
        "repair_kind": "generated_service_logic_patch",
        "evidence": "Validation expected ESCALATE/CRITICAL but first draft returned standard handling.",
    }
    next_state["diagnoses"] = next_state["diagnoses"] + [diagnosis]
    add_action(
        next_state,
        "failure_diagnosis_agent",
        "diagnose_validation_failure",
        "passed",
        diagnosis["root_cause"],
    )
    return next_state


def policy_gate_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    policy = next_state["policy"]
    latest = next_state["diagnoses"][-1]
    target = latest["target_file"]
    allowed = cast(list[str], policy["allowed_repair_targets"])
    forbidden = cast(list[str], policy["forbidden_repair_targets"])
    budget = cast(dict[str, Any], policy["repair_budget"])
    within_budget = latest["attempt"] <= int(budget["max_attempts"])
    target_allowed = path_matches_any(target, allowed)
    target_forbidden = path_matches_any(target, forbidden)
    decision_status: PolicyDecisionStatus = (
        "allowed" if within_budget and target_allowed and not target_forbidden else "denied"
    )
    reason = (
        "Repair is within budget and targets only generated application files."
        if decision_status == "allowed"
        else "Repair denied by budget or file-scope policy."
    )
    decision: PolicyDecision = {
        "attempt": latest["attempt"],
        "status": decision_status,
        "policy_id": cast(str, policy["policy_id"]),
        "target_file": target,
        "reason": reason,
    }
    next_state["policy_decisions"] = next_state["policy_decisions"] + [decision]
    add_action(
        next_state,
        "policy_gate_agent",
        "authorize_or_deny_repair",
        decision_status,
        reason,
    )
    if decision_status == "denied":
        next_state["errors"] = next_state["errors"] + [reason]
    return next_state


def bounded_repair_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    decision = next_state["policy_decisions"][-1]
    if decision["status"] != "allowed":
        next_state["validation_status"] = "failed"
        add_action(
            next_state,
            "bounded_repair_agent",
            "skip_denied_repair",
            "failed",
            decision["reason"],
        )
        return next_state

    generated_file = write_file(
        PACKAGE_DIR / "service.py",
        repaired_service_code(),
        "Policy-authorized repaired service",
    )
    files = upsert_generated_file(next_state["generated_files"], generated_file)
    evidence: RepairEvidence = {
        "attempt": decision["attempt"],
        "target_file": generated_file["path"],
        "policy_decision": decision["status"],
        "diff_summary": "Added regulatory complaint critical escalation and governed policy id.",
        "sha256_after": generated_file["sha256"],
    }
    next_state["generated_files"] = files
    next_state["repair_evidence"] = next_state["repair_evidence"] + [evidence]
    next_state["repair_attempts"] = next_state["repair_attempts"] + 1
    add_action(
        next_state,
        "bounded_repair_agent",
        "apply_policy_authorized_repair",
        "passed",
        evidence["diff_summary"],
    )
    return next_state


def evidence_agent(state: GenerationState) -> GenerationState:
    next_state = state.copy()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    add_action(
        next_state,
        "evidence_agent",
        "write_audit_evidence",
        "passed",
        "Persisted policy, diagnosis, repair, validation, and traceability evidence.",
    )
    policy = next_state["policy"]
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "generated_at_utc": utc_now(),
        "baseline_tag": BASELINE_TAG,
        "objective": next_state["objective"],
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "agent_actions": next_state["agent_actions"],
        "generated_files": next_state["generated_files"],
        "validation_results": next_state["validation_results"],
        "diagnoses": next_state["diagnoses"],
        "policy_decisions": next_state["policy_decisions"],
        "repair_evidence": next_state["repair_evidence"],
        "policy_governance": {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
            "repair_budget": policy.get("repair_budget"),
            "llm_runtime": policy.get("llm_runtime"),
            "mock_boundary": policy.get("mock_boundary"),
        },
        "validation_status": next_state["validation_status"],
        "repair_attempts": next_state["repair_attempts"],
        "max_repair_attempts": next_state["max_repair_attempts"],
        "release_ready": next_state["release_ready"],
        "human_approval_required": True,
        "blocked_actions": ["git merge", "git push", "git tag", "release publish"],
        "requirement_ids": next_state["requirement_ids"],
        "status": next_state["status"],
        "passed": next_state["validation_status"] == "passed"
        and next_state["repair_attempts"] == 1
        and len(next_state["policy_decisions"]) == 1,
        "truth_boundary": (
            "Generated UPI dispute triage capability is local and runnable; "
            "external ecosystem interfaces remain simulated mocks only."
        ),
    }
    manifest = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "policy_id": policy.get("policy_id"),
        "requirement_ids": next_state["requirement_ids"],
        "generated_app_dir": relative(CAPABILITY_DIR),
        "audit_path": relative(ARTIFACT_DIR / "policy_governed_generation_audit.json"),
        "traceability_path": relative(ARTIFACT_DIR / "requirement_traceability_matrix.json"),
        "generated_file_count": len(next_state["generated_files"]),
        "repair_attempts": next_state["repair_attempts"],
        "diagnosis_count": len(next_state["diagnoses"]),
        "policy_decision_count": len(next_state["policy_decisions"]),
        "release_ready": next_state["release_ready"],
    }
    traceability = {
        "requirement_id": REQUIREMENT_ID,
        "policy_id": policy.get("policy_id"),
        "generated_files": next_state["generated_files"],
        "tests": [
            relative(GENERATED_TEST_DIR / "test_generated_policy_governed_triage.py"),
            "tests/test_phase13v_policy_governed_self_repairing_generation.py",
        ],
        "validation_results": next_state["validation_results"],
        "policy_decisions": next_state["policy_decisions"],
    }
    report = "\n".join(
        [
            "# Phase 13V Policy-Governed Self-Repairing Generation",
            "",
            f"Requirement: {REQUIREMENT_ID}",
            f"Policy: {policy.get('policy_id')} {policy.get('policy_version')}",
            "Status: passed after one policy-authorized bounded repair.",
            "LLM runtime: deterministic_local; no OpenAI key required for this phase.",
            "External ecosystem boundary: mock/simulated only.",
            "",
        ]
    )
    outputs = {
        ARTIFACT_DIR / "policy_governed_generation_audit.json": audit,
        ARTIFACT_DIR / "policy_governed_generation_manifest.json": manifest,
        ARTIFACT_DIR / "requirement_traceability_matrix.json": traceability,
    }
    for path, payload in outputs.items():
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ARTIFACT_DIR / "policy_governed_generation_report.md").write_text(
        report,
        encoding="utf-8",
    )
    next_state["status"] = "awaiting_human_release_approval"
    return next_state


def route_after_validation(state: GenerationState) -> str:
    if state["validation_status"] == "passed":
        return "evidence_agent"
    if state["repair_attempts"] < state["max_repair_attempts"]:
        return "failure_diagnosis_agent"
    return "evidence_agent"


def route_after_policy_gate(state: GenerationState) -> str:
    if state["policy_decisions"] and state["policy_decisions"][-1]["status"] == "allowed":
        return "bounded_repair_agent"
    return "evidence_agent"


def build_graph() -> Any:
    graph = StateGraph(GenerationState)
    graph.add_node("requirement_package_agent", requirement_package_agent)
    graph.add_node("policy_load_agent", policy_load_agent)
    graph.add_node("code_generation_agent", code_generation_agent)
    graph.add_node("test_generation_agent", test_generation_agent)
    graph.add_node("docs_generation_agent", docs_generation_agent)
    graph.add_node("validation_agent", validation_agent)
    graph.add_node("failure_diagnosis_agent", failure_diagnosis_agent)
    graph.add_node("policy_gate_agent", policy_gate_agent)
    graph.add_node("bounded_repair_agent", bounded_repair_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.set_entry_point("requirement_package_agent")
    graph.add_edge("requirement_package_agent", "policy_load_agent")
    graph.add_edge("policy_load_agent", "code_generation_agent")
    graph.add_edge("code_generation_agent", "test_generation_agent")
    graph.add_edge("test_generation_agent", "docs_generation_agent")
    graph.add_edge("docs_generation_agent", "validation_agent")
    graph.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "failure_diagnosis_agent": "failure_diagnosis_agent",
            "evidence_agent": "evidence_agent",
        },
    )
    graph.add_edge("failure_diagnosis_agent", "policy_gate_agent")
    graph.add_conditional_edges(
        "policy_gate_agent",
        route_after_policy_gate,
        {
            "bounded_repair_agent": "bounded_repair_agent",
            "evidence_agent": "evidence_agent",
        },
    )
    graph.add_edge("bounded_repair_agent", "validation_agent")
    graph.add_edge("evidence_agent", END)
    return graph.compile()


def initial_state() -> GenerationState:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": "Generate policy-governed self-repairing UPI dispute triage capability",
        "requirement_ids": [],
        "policy": {},
        "generated_files": [],
        "agent_actions": [],
        "validation_results": [],
        "diagnoses": [],
        "policy_decisions": [],
        "repair_evidence": [],
        "validation_status": "not_run",
        "repair_attempts": 0,
        "max_repair_attempts": 2,
        "release_ready": False,
        "status": "running",
        "errors": [],
    }


def run_generation() -> dict[str, Any]:
    final_state = cast(GenerationState, build_graph().invoke(initial_state()))
    audit_path = ARTIFACT_DIR / "policy_governed_generation_audit.json"
    audit = cast(dict[str, Any], json.loads(audit_path.read_text(encoding="utf-8")))
    return {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": final_state["objective"],
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "policy_id": POLICY_ID,
        "llm_runtime_mode": "deterministic_local",
        "openai_api_key_required": False,
        "requirement_ids": final_state["requirement_ids"],
        "generated_app_dir": relative(CAPABILITY_DIR),
        "generated_file_count": len(final_state["generated_files"]),
        "diagnosis_count": len(final_state["diagnoses"]),
        "policy_decision_count": len(final_state["policy_decisions"]),
        "repair_attempts": final_state["repair_attempts"],
        "validation_status": final_state["validation_status"],
        "release_ready": final_state["release_ready"],
        "human_approval_required": True,
        "status": final_state["status"],
        "audit_path": relative(audit_path),
        "traceability_path": relative(ARTIFACT_DIR / "requirement_traceability_matrix.json"),
        "passed": audit.get("passed") is True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    result = run_generation()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
