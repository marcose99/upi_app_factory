#!/usr/bin/env python3
"""Phase 13W: governed multi-capability generated application assembly."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13W"
PHASE_ID = "phase13w_governed_multi_capability_application_assembly"
POLICY_PATH = PROJECT_ROOT / "policies" / "phase13w_multi_capability_assembly_policy.json"
GENERATED_APP_DIR = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "generated_application" / "phase13w_multi_capability_dispute_app"
PACKAGE_DIR = GENERATED_APP_DIR / "phase13w_multi_capability_dispute_app"
GENERATED_TEST_DIR = GENERATED_APP_DIR / "generated_tests"
ARTIFACT_DIR = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13w"


class AssemblyState(TypedDict, total=False):
    requirement_package: dict[str, Any]
    policy: dict[str, Any]
    policy_decisions: list[dict[str, Any]]
    generated_files: list[str]
    generated_app_dir: str
    validation_errors: list[str]
    validation_status: str
    assembled_capabilities: list[str]
    traceability: dict[str, Any]
    audit_events: list[dict[str, Any]]
    release_ready: bool
    human_approval_required: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_requirement_package() -> dict[str, Any]:
    return {
        "package_id": "RP-13W-GOVERNED-MULTI-CAPABILITY-DISPUTE-APP",
        "app_id": APP_ID,
        "phase": PHASE,
        "objective": "Assemble a governed local UPI dispute application from multiple generated capabilities.",
        "requirements": [
            {
                "id": "REQ-13W-EVIDENCE-VALIDATION",
                "capability": "evidence_validation",
                "statement": "Validate uploaded dispute evidence before case triage.",
                "acceptance": [
                    "Reject missing case id.",
                    "Reject unsupported evidence file types.",
                    "Reject empty or oversized evidence payloads.",
                ],
            },
            {
                "id": "REQ-13W-SLA-TRIAGE",
                "capability": "sla_triage",
                "statement": "Classify dispute cases for standard handling, evidence review, or SLA escalation.",
                "acceptance": [
                    "Escalate when age exceeds SLA hours.",
                    "Route cases with evidence issues to evidence review.",
                    "Keep valid in-SLA cases on the standard queue.",
                ],
            },
        ],
        "external_ecosystem_boundary": "mock_only",
    }


def load_policy() -> dict[str, Any]:
    if not POLICY_PATH.exists():
        raise FileNotFoundError(f"Missing Phase 13W policy: {POLICY_PATH}")
    return cast(dict[str, Any], json.loads(POLICY_PATH.read_text(encoding="utf-8")))


def audit(state: AssemblyState, event: str, details: dict[str, Any]) -> None:
    events = state.setdefault("audit_events", [])
    events.append({"at_utc": utc_now(), "event": event, "details": details})


def requirement_intake_agent(state: AssemblyState) -> AssemblyState:
    state["requirement_package"] = default_requirement_package()
    state["human_approval_required"] = True
    audit(state, "requirement_intake_agent", {"requirement_count": 2})
    return state


def policy_gate_agent(state: AssemblyState) -> AssemblyState:
    package = state["requirement_package"]
    policy = load_policy()
    capabilities = [str(item["capability"]) for item in package["requirements"]]
    required = [str(item) for item in policy["required_capabilities"]]
    errors: list[str] = []
    if len(capabilities) < int(policy["allowed_capability_count_min"]):
        errors.append("Too few capabilities for multi-capability assembly.")
    if len(capabilities) > int(policy["allowed_capability_count_max"]):
        errors.append("Too many capabilities for this local-first phase.")
    missing = sorted(set(required) - set(capabilities))
    if missing:
        errors.append(f"Missing required capabilities: {missing}")
    decision = {
        "policy_id": policy["policy_id"],
        "decision": "allow" if not errors else "deny",
        "capabilities": capabilities,
        "errors": errors,
    }
    state["policy"] = policy
    state["policy_decisions"] = [decision]
    state["assembled_capabilities"] = capabilities
    audit(state, "policy_gate_agent", decision)
    if errors:
        state["validation_errors"] = errors
    return state


def application_assembly_agent(state: AssemblyState) -> AssemblyState:
    if state.get("validation_errors"):
        return state
    generated_files: list[str] = []

    write_text(PACKAGE_DIR / "contracts.py", '''
        """Contracts for Phase 13W generated multi-capability dispute app."""
        from __future__ import annotations

        from dataclasses import dataclass


        @dataclass(frozen=True)
        class EvidenceUpload:
            case_id: str
            filename: str
            content_hash: str
            size_bytes: int


        @dataclass(frozen=True)
        class DisputeCase:
            case_id: str
            age_hours: int
            sla_hours: int
            amount_paise: int
            channel: str


        @dataclass(frozen=True)
        class EvidenceValidationResult:
            case_id: str
            accepted: bool
            issues: tuple[str, ...]


        @dataclass(frozen=True)
        class TriageDecision:
            case_id: str
            queue: str
            needs_escalation: bool
            reasons: tuple[str, ...]


        @dataclass(frozen=True)
        class MultiCapabilityResult:
            case_id: str
            evidence: EvidenceValidationResult
            triage: TriageDecision
            external_ecosystem_mode: str
    ''')
    generated_files.append(rel(PACKAGE_DIR / "contracts.py"))

    write_text(PACKAGE_DIR / "evidence_validation.py", '''
        """Generated evidence-validation capability."""
        from __future__ import annotations

        from .contracts import EvidenceUpload, EvidenceValidationResult

        SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")
        MAX_EVIDENCE_SIZE_BYTES = 5_000_000


        def validate_evidence(upload: EvidenceUpload) -> EvidenceValidationResult:
            issues: list[str] = []
            if not upload.case_id.strip():
                issues.append("missing_case_id")
            if not upload.filename.lower().endswith(SUPPORTED_EXTENSIONS):
                issues.append("unsupported_file_type")
            if not upload.content_hash.strip() or len(upload.content_hash.strip()) < 16:
                issues.append("weak_or_missing_content_hash")
            if upload.size_bytes <= 0:
                issues.append("empty_evidence_payload")
            if upload.size_bytes > MAX_EVIDENCE_SIZE_BYTES:
                issues.append("evidence_payload_too_large")
            return EvidenceValidationResult(
                case_id=upload.case_id,
                accepted=not issues,
                issues=tuple(issues),
            )
    ''')
    generated_files.append(rel(PACKAGE_DIR / "evidence_validation.py"))

    write_text(PACKAGE_DIR / "sla_triage.py", '''
        """Generated SLA triage capability."""
        from __future__ import annotations

        from .contracts import DisputeCase, EvidenceValidationResult, TriageDecision


        def decide_triage(case: DisputeCase, evidence: EvidenceValidationResult) -> TriageDecision:
            reasons: list[str] = []
            if not evidence.accepted:
                reasons.append("evidence_validation_failed")
            if case.age_hours >= case.sla_hours:
                reasons.append("sla_breach_or_due")
            if case.amount_paise >= 100_000:
                reasons.append("high_value_dispute")

            if "evidence_validation_failed" in reasons:
                queue = "evidence_review"
            elif "sla_breach_or_due" in reasons:
                queue = "sla_escalation"
            else:
                queue = "standard_dispute_ops"

            return TriageDecision(
                case_id=case.case_id,
                queue=queue,
                needs_escalation=queue in {"evidence_review", "sla_escalation"},
                reasons=tuple(reasons),
            )
    ''')
    generated_files.append(rel(PACKAGE_DIR / "sla_triage.py"))

    write_text(PACKAGE_DIR / "assembly.py", '''
        """Generated multi-capability assembly service."""
        from __future__ import annotations

        from .contracts import DisputeCase, EvidenceUpload, MultiCapabilityResult
        from .evidence_validation import validate_evidence
        from .sla_triage import decide_triage


        def process_dispute_case(upload: EvidenceUpload, case: DisputeCase) -> MultiCapabilityResult:
            evidence_result = validate_evidence(upload)
            triage_decision = decide_triage(case, evidence_result)
            return MultiCapabilityResult(
                case_id=case.case_id,
                evidence=evidence_result,
                triage=triage_decision,
                external_ecosystem_mode="mock_only",
            )
    ''')
    generated_files.append(rel(PACKAGE_DIR / "assembly.py"))

    write_text(PACKAGE_DIR / "__init__.py", '''
        """Phase 13W generated multi-capability dispute application."""
        from .assembly import process_dispute_case
        from .contracts import DisputeCase, EvidenceUpload, MultiCapabilityResult, TriageDecision
        from .evidence_validation import validate_evidence
        from .sla_triage import decide_triage

        __all__ = [
            "DisputeCase",
            "EvidenceUpload",
            "MultiCapabilityResult",
            "TriageDecision",
            "decide_triage",
            "process_dispute_case",
            "validate_evidence",
        ]
    ''')
    generated_files.append(rel(PACKAGE_DIR / "__init__.py"))

    write_text(PACKAGE_DIR / "py.typed", "")
    generated_files.append(rel(PACKAGE_DIR / "py.typed"))

    write_text(GENERATED_TEST_DIR / "test_generated_multi_capability_app.py", '''
        from __future__ import annotations

        import importlib
        import sys
        from pathlib import Path

        GENERATED_APP_ROOT = Path(__file__).resolve().parents[1]
        if str(GENERATED_APP_ROOT) not in sys.path:
            sys.path.insert(0, str(GENERATED_APP_ROOT))

        generated_app = importlib.import_module("phase13w_multi_capability_dispute_app")
        DisputeCase = generated_app.DisputeCase
        EvidenceUpload = generated_app.EvidenceUpload
        process_dispute_case = generated_app.process_dispute_case


        def test_valid_case_stays_standard_and_mock_bounded() -> None:
            result = process_dispute_case(
                EvidenceUpload("CASE-1", "receipt.pdf", "abc1234567890def", 2048),
                DisputeCase("CASE-1", age_hours=4, sla_hours=24, amount_paise=25000, channel="UPI"),
            )

            assert result.evidence.accepted is True
            assert result.triage.queue == "standard_dispute_ops"
            assert result.external_ecosystem_mode == "mock_only"


        def test_invalid_evidence_routes_to_evidence_review() -> None:
            result = process_dispute_case(
                EvidenceUpload("CASE-2", "notes.exe", "bad", 10),
                DisputeCase("CASE-2", age_hours=2, sla_hours=24, amount_paise=25000, channel="UPI"),
            )

            assert result.evidence.accepted is False
            assert result.triage.queue == "evidence_review"
            assert result.triage.needs_escalation is True


        def test_sla_breach_routes_to_sla_escalation() -> None:
            result = process_dispute_case(
                EvidenceUpload("CASE-3", "proof.png", "abc1234567890def", 1024),
                DisputeCase("CASE-3", age_hours=25, sla_hours=24, amount_paise=25000, channel="UPI"),
            )

            assert result.evidence.accepted is True
            assert result.triage.queue == "sla_escalation"
            assert "sla_breach_or_due" in result.triage.reasons
    ''')
    generated_files.append(rel(GENERATED_TEST_DIR / "test_generated_multi_capability_app.py"))

    write_text(GENERATED_APP_DIR / "README.md", '''
        # Phase 13W generated multi-capability dispute app

        This local generated application assembles two governed capabilities:

        1. Evidence upload validation.
        2. SLA triage and escalation routing.

        External payment rails, banks, NPCI/RBI-style integrations, and upstream/downstream systems remain mock/simulated only.
    ''')
    generated_files.append(rel(GENERATED_APP_DIR / "README.md"))

    state["generated_files"] = generated_files
    state["generated_app_dir"] = rel(GENERATED_APP_DIR)
    audit(state, "application_assembly_agent", {"generated_file_count": len(generated_files)})
    return state


def verification_agent(state: AssemblyState) -> AssemblyState:
    if state.get("validation_errors"):
        return state
    sys.path.insert(0, str(GENERATED_APP_DIR))
    try:
        from phase13w_multi_capability_dispute_app import DisputeCase, EvidenceUpload, process_dispute_case

        standard = process_dispute_case(
            EvidenceUpload("CASE-OK", "receipt.pdf", "abc1234567890def", 2048),
            DisputeCase("CASE-OK", age_hours=2, sla_hours=24, amount_paise=12000, channel="UPI"),
        )
        evidence_review = process_dispute_case(
            EvidenceUpload("CASE-BAD", "payload.exe", "bad", 2048),
            DisputeCase("CASE-BAD", age_hours=2, sla_hours=24, amount_paise=12000, channel="UPI"),
        )
        sla = process_dispute_case(
            EvidenceUpload("CASE-SLA", "receipt.jpg", "abc1234567890def", 2048),
            DisputeCase("CASE-SLA", age_hours=25, sla_hours=24, amount_paise=12000, channel="UPI"),
        )
    finally:
        if str(GENERATED_APP_DIR) in sys.path:
            sys.path.remove(str(GENERATED_APP_DIR))

    errors: list[str] = []
    if standard.triage.queue != "standard_dispute_ops":
        errors.append("Expected valid in-SLA case to remain on standard queue.")
    if evidence_review.triage.queue != "evidence_review":
        errors.append("Expected invalid evidence case to route to evidence review.")
    if sla.triage.queue != "sla_escalation":
        errors.append("Expected SLA breach case to route to SLA escalation.")
    if standard.external_ecosystem_mode != "mock_only":
        errors.append("External ecosystem boundary must remain mock_only.")

    state["validation_errors"] = errors
    state["validation_status"] = "failed" if errors else "passed"
    state["release_ready"] = not errors
    audit(state, "verification_agent", {"validation_status": state["validation_status"], "errors": errors})
    return state


def evidence_agent(state: AssemblyState) -> AssemblyState:
    package = state["requirement_package"]
    requirements = cast(list[dict[str, Any]], package["requirements"])
    traceability = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "requirement_links": [
            {
                "requirement_id": str(req["id"]),
                "capability": str(req["capability"]),
                "generated_app_dir": rel(GENERATED_APP_DIR),
                "tests": [rel(GENERATED_TEST_DIR / "test_generated_multi_capability_app.py")],
                "policy_id": state["policy"]["policy_id"],
            }
            for req in requirements
        ],
    }
    state["traceability"] = traceability
    audit(state, "evidence_agent", {"traceability_links": len(traceability["requirement_links"])})

    manifest = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "generated_at_utc": utc_now(),
        "generated_app_dir": rel(GENERATED_APP_DIR),
        "generated_files": state.get("generated_files", []),
        "assembled_capabilities": state.get("assembled_capabilities", []),
        "policy_id": state["policy"]["policy_id"],
        "policy_decisions": state.get("policy_decisions", []),
        "validation_status": state.get("validation_status"),
        "human_approval_required": True,
        "external_ecosystem_boundary": "mock_only",
    }
    audit_payload = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "events": state.get("audit_events", []),
        "policy_decisions": state.get("policy_decisions", []),
        "validation_errors": state.get("validation_errors", []),
    }
    report = f"""
        # Phase 13W governed multi-capability application assembly

        Status: {state.get('validation_status')}

        Capabilities assembled:
        - evidence_validation
        - sla_triage

        Governance:
        - Source-controlled policy: {state['policy']['policy_id']}
        - Human release approval required: true
        - External ecosystem boundary: mock_only
        - OpenAI API key required for this phase: false
    """
    write_json(ARTIFACT_DIR / "multi_capability_requirement_package.json", package)
    write_json(ARTIFACT_DIR / "effective_multi_capability_policy.json", state["policy"])
    write_json(ARTIFACT_DIR / "requirement_traceability_matrix.json", traceability)
    write_json(ARTIFACT_DIR / "multi_capability_assembly_manifest.json", manifest)
    write_json(ARTIFACT_DIR / "multi_capability_assembly_audit.json", audit_payload)
    write_text(ARTIFACT_DIR / "multi_capability_assembly_report.md", report)
    return state


def build_graph() -> Any:
    graph = StateGraph(AssemblyState)
    graph.add_node("requirement_intake_agent", requirement_intake_agent)
    graph.add_node("policy_gate_agent", policy_gate_agent)
    graph.add_node("application_assembly_agent", application_assembly_agent)
    graph.add_node("verification_agent", verification_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.set_entry_point("requirement_intake_agent")
    graph.add_edge("requirement_intake_agent", "policy_gate_agent")
    graph.add_edge("policy_gate_agent", "application_assembly_agent")
    graph.add_edge("application_assembly_agent", "verification_agent")
    graph.add_edge("verification_agent", "evidence_agent")
    graph.add_edge("evidence_agent", END)
    return graph.compile()


def run_generation(output: Path | None = None) -> dict[str, Any]:
    app = build_graph()
    final_state = cast(AssemblyState, app.invoke({}))
    passed = final_state.get("validation_status") == "passed" and final_state.get("release_ready") is True
    result = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "passed": passed,
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "objective": final_state["requirement_package"]["objective"],
        "requirement_ids": [req["id"] for req in final_state["requirement_package"]["requirements"]],
        "assembled_capabilities": final_state.get("assembled_capabilities", []),
        "capability_count": len(final_state.get("assembled_capabilities", [])),
        "policy_id": final_state["policy"]["policy_id"],
        "policy_decision_count": len(final_state.get("policy_decisions", [])),
        "generated_app_dir": final_state.get("generated_app_dir", ""),
        "generated_file_count": len(final_state.get("generated_files", [])),
        "traceability_path": rel(ARTIFACT_DIR / "requirement_traceability_matrix.json"),
        "audit_path": rel(ARTIFACT_DIR / "multi_capability_assembly_audit.json"),
        "validation_status": final_state.get("validation_status"),
        "release_ready": final_state.get("release_ready", False),
        "human_approval_required": final_state.get("human_approval_required", True),
        "external_ecosystem_boundary": "mock_only",
        "llm_runtime_mode": "deterministic_local",
        "openai_api_key_required": False,
        "status": "awaiting_human_release_approval" if passed else "failed_validation",
    }
    if output is not None:
        write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = run_generation(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
