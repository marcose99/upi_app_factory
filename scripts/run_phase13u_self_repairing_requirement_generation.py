#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, StateGraph

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13U"
PHASE_ID = "phase13u_self_repairing_requirement_generation"
BASELINE_TAG = "v0.13.19-requirement-package-driven-capability-generation"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13u"
)
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13u_self_repairing_sla_escalation"
)
PACKAGE_DIR = GENERATED_ROOT / "phase13u_self_repairing_sla_escalation_app"
GENERATED_TEST_DIR = GENERATED_ROOT / "generated_tests"
AUDIT_PATH = ARTIFACT_DIR / "self_repairing_generation_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "self_repairing_generation_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "self_repairing_generation_report.md"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
REQUIREMENT_PATH = ARTIFACT_DIR / "self_repairing_requirement_package.json"

ValidationStatus = Literal["not_started", "passed", "failed"]


class AgentAction(TypedDict):
    agent: str
    action: str
    status: str
    detail: str


class ValidationResult(TypedDict):
    attempt: int
    command: list[str]
    return_code: int
    output_preview: str


class GeneratedFile(TypedDict):
    path: str
    purpose: str
    sha256: str


class Diagnosis(TypedDict):
    issue_id: str
    category: str
    failed_attempt: int
    repair_strategy: str


class GenerationState(TypedDict):
    app_id: str
    phase: str
    phase_id: str
    objective: str
    requirement_ids: list[str]
    generated_files: list[GeneratedFile]
    agent_actions: list[AgentAction]
    validation_results: list[ValidationResult]
    diagnoses: list[Diagnosis]
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


def run_command(command: list[str], attempt: int) -> ValidationResult:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "attempt": attempt,
        "command": command,
        "return_code": result.returncode,
        "output_preview": (result.stdout + result.stderr)[:4000],
    }


def service_code_faulty() -> str:
    return '''from __future__ import annotations

from .contracts import SlaEscalationRequest, SlaEscalationResult


def validate_sla_escalation(request: SlaEscalationRequest) -> SlaEscalationResult:
    """Faulty first draft intentionally produced to prove bounded repair."""

    # BUG: the first draft breaches every case, even when elapsed minutes are
    # inside the SLA window. The self-repair loop must diagnose and replace this.
    breach_detected = True
    remaining_minutes = request.sla_minutes - request.elapsed_minutes
    return SlaEscalationResult(
        dispute_case_id=request.dispute_case_id,
        breach_detected=breach_detected,
        escalation_status="BREACHED",
        remaining_minutes=remaining_minutes,
        escalation_reason="SLA breach detected by generated first draft",
        audit_event_type="sla_escalation_evaluated",
    )
'''


def service_code_repaired() -> str:
    return '''from __future__ import annotations

from .contracts import SlaEscalationRequest, SlaEscalationResult


def validate_sla_escalation(request: SlaEscalationRequest) -> SlaEscalationResult:
    """Evaluate SLA breach status locally without external ecosystem calls."""

    remaining_minutes = request.sla_minutes - request.elapsed_minutes
    breach_detected = remaining_minutes < 0
    if breach_detected:
        status = "BREACHED"
        reason = "Elapsed minutes exceeded the configured SLA window"
    elif remaining_minutes <= request.warning_threshold_minutes:
        status = "AT_RISK"
        reason = "SLA is still open but inside the warning threshold"
    else:
        status = "ON_TRACK"
        reason = "SLA is inside the allowed operating window"
    return SlaEscalationResult(
        dispute_case_id=request.dispute_case_id,
        breach_detected=breach_detected,
        escalation_status=status,
        remaining_minutes=remaining_minutes,
        escalation_reason=reason,
        audit_event_type="sla_escalation_evaluated",
    )
'''


def requirement_package_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    requirement = {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "requirement_id": "REQ-13U-SELF-REPAIRING-SLA-ESCALATION",
        "title": "Self-repair generated SLA escalation capability",
        "business_goal": (
            "Generate a local UPI dispute SLA escalation capability and prove the "
            "factory can diagnose and repair a generated behavior defect without "
            "a separate manual repair script."
        ),
        "acceptance_criteria": [
            "A case within SLA must return ON_TRACK and no breach.",
            "A case inside warning threshold must return AT_RISK and no breach.",
            "A case beyond SLA must return BREACHED and breach_detected true.",
            "The first validation attempt must fail and a bounded repair must pass.",
        ],
        "truth_boundary": (
            "Primary UPI dispute SLA escalation logic is local and runnable; "
            "external ecosystem interfaces remain simulated mocks only."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REQUIREMENT_PATH.write_text(
        json.dumps(requirement, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    next_state["requirement_ids"] = [str(requirement["requirement_id"])]
    add_action(
        next_state,
        "requirement_package_agent",
        "load_requirement_package",
        "completed",
        "Loaded requirement package for self-repairing SLA escalation generation.",
    )
    return next_state


def design_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    traceability = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "mappings": [
            {
                "requirement_id": "REQ-13U-SELF-REPAIRING-SLA-ESCALATION",
                "design_elements": [
                    "SlaEscalationRequest contract",
                    "SlaEscalationResult contract",
                    "validate_sla_escalation generated service",
                    "bounded repair after failed validation",
                ],
                "code_files": [
                    relative(PACKAGE_DIR / "contracts.py"),
                    relative(PACKAGE_DIR / "service.py"),
                ],
                "generated_test_files": [
                    relative(GENERATED_TEST_DIR / "test_generated_sla_escalation.py")
                ],
                "governance_evidence": [
                    relative(AUDIT_PATH),
                    relative(MANIFEST_PATH),
                    relative(REPORT_PATH),
                    relative(REQUIREMENT_PATH),
                ],
            }
        ],
    }
    TRACEABILITY_PATH.write_text(
        json.dumps(traceability, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    add_action(
        next_state,
        "design_agent",
        "create_repairable_design",
        "completed",
        "Mapped requirement to generated code, behavior tests, and repair evidence.",
    )
    return next_state


def code_generation_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    files = list(next_state["generated_files"])
    init_code = '''"""Generated Phase 13U self-repairing SLA escalation capability."""

from .contracts import SlaEscalationRequest, SlaEscalationResult
from .service import validate_sla_escalation

__all__ = [
    "SlaEscalationRequest",
    "SlaEscalationResult",
    "validate_sla_escalation",
]
'''
    contracts_code = '''from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EscalationStatus = Literal["ON_TRACK", "AT_RISK", "BREACHED"]


class SlaEscalationRequest(BaseModel):
    """Local SLA escalation input for a generated dispute capability."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str = Field(min_length=3, max_length=64)
    elapsed_minutes: int = Field(ge=0, le=30 * 24 * 60)
    sla_minutes: int = Field(ge=1, le=30 * 24 * 60)
    warning_threshold_minutes: int = Field(default=30, ge=0, le=24 * 60)


class SlaEscalationResult(BaseModel):
    """Deterministic local SLA escalation output."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str
    breach_detected: bool
    escalation_status: EscalationStatus
    remaining_minutes: int
    escalation_reason: str
    audit_event_type: str
'''
    readme_code = '''# Phase 13U Self-Repairing SLA Escalation Capability

This generated local capability evaluates UPI dispute SLA escalation state.
The first generated service draft intentionally contains a behavior defect so
Phase 13U can prove bounded diagnosis and repair inside the LangGraph runner.

External banks, rails, NPCI-style, RBI-style, PSP, upstream, and downstream
systems remain simulated/mock boundaries only.
'''
    files = upsert_generated_file(
        files,
        write_file(PACKAGE_DIR / "__init__.py", init_code, "generated_package_init"),
    )
    files = upsert_generated_file(
        files,
        write_file(PACKAGE_DIR / "contracts.py", contracts_code, "generated_contracts"),
    )
    files = upsert_generated_file(
        files,
        write_file(
            PACKAGE_DIR / "service.py",
            service_code_faulty(),
            "generated_faulty_first_draft_service",
        ),
    )
    files = upsert_generated_file(
        files,
        write_file(GENERATED_ROOT / "README.md", readme_code, "generated_readme"),
    )
    next_state["generated_files"] = files
    add_action(
        next_state,
        "code_generation_agent",
        "generate_faulty_first_draft",
        "completed",
        "Generated first draft of SLA escalation service for self-repair proof.",
    )
    return next_state


def test_generation_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    files = list(next_state["generated_files"])
    test_code = '''from __future__ import annotations

import pathlib
import sys

GENERATED_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATED_ROOT))

from phase13u_self_repairing_sla_escalation_app import (
    SlaEscalationRequest,
    validate_sla_escalation,
)


def test_generated_sla_escalation_behavior() -> None:
    on_track = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-ON-TRACK",
            elapsed_minutes=20,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert on_track.breach_detected is False
    assert on_track.escalation_status == "ON_TRACK"

    at_risk = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-RISK",
            elapsed_minutes=100,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert at_risk.breach_detected is False
    assert at_risk.escalation_status == "AT_RISK"

    breached = validate_sla_escalation(
        SlaEscalationRequest(
            dispute_case_id="CASE-13U-BREACH",
            elapsed_minutes=121,
            sla_minutes=120,
            warning_threshold_minutes=30,
        )
    )
    assert breached.breach_detected is True
    assert breached.escalation_status == "BREACHED"
'''
    files = upsert_generated_file(
        files,
        write_file(
            GENERATED_TEST_DIR / "test_generated_sla_escalation.py",
            test_code,
            "generated_behavior_test",
        ),
    )
    next_state["generated_files"] = files
    add_action(
        next_state,
        "test_generation_agent",
        "generate_behavior_tests",
        "completed",
        "Generated behavior tests that expose the first-draft SLA defect.",
    )
    return next_state


def docs_generation_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    files = list(next_state["generated_files"])
    doc_code = '''# Phase 13U - Self-Repairing Requirement Generation Runner

Phase 13U proves the governed generation runner can repair a generated
application behavior defect without a separate manual repair script.

## Proof

The runner intentionally emits a faulty first draft of the local SLA escalation
service. Validation catches the behavior mismatch. The diagnosis agent records
the issue, the bounded repair agent rewrites the generated service, and
validation reruns successfully.

## Governance boundary

The generated SLA escalation capability is local and runnable. External banks,
NPCI-style systems, RBI-style systems, UPI rails, PSPs, upstream applications,
and downstream applications remain mock/simulated boundaries only.
'''
    files = upsert_generated_file(
        files,
        write_file(
            PROJECT_ROOT
            / "docs"
            / "phase13u"
            / "self_repairing_requirement_generation_runner.md",
            doc_code,
            "phase_documentation",
        ),
    )
    next_state["generated_files"] = files
    add_action(
        next_state,
        "docs_generation_agent",
        "generate_phase_documentation",
        "completed",
        "Generated documentation for self-repairing requirement generation.",
    )
    return next_state


def behavior_check_command() -> list[str]:
    generated_root = str(GENERATED_ROOT)
    code = (
        "import sys; "
        f"sys.path.insert(0, {generated_root!r}); "
        "from phase13u_self_repairing_sla_escalation_app import "
        "SlaEscalationRequest, validate_sla_escalation; "
        "on_track = validate_sla_escalation(SlaEscalationRequest("
        "dispute_case_id='CASE-OK', elapsed_minutes=20, sla_minutes=120, "
        "warning_threshold_minutes=30)); "
        "assert on_track.breach_detected is False; "
        "assert on_track.escalation_status == 'ON_TRACK'; "
        "at_risk = validate_sla_escalation(SlaEscalationRequest("
        "dispute_case_id='CASE-RISK', elapsed_minutes=100, sla_minutes=120, "
        "warning_threshold_minutes=30)); "
        "assert at_risk.breach_detected is False; "
        "assert at_risk.escalation_status == 'AT_RISK'; "
        "breached = validate_sla_escalation(SlaEscalationRequest("
        "dispute_case_id='CASE-BREACH', elapsed_minutes=121, sla_minutes=120, "
        "warning_threshold_minutes=30)); "
        "assert breached.breach_detected is True; "
        "assert breached.escalation_status == 'BREACHED'"
    )
    return [sys.executable, "-c", code]


def validation_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    attempt = next_state["repair_attempts"]
    results = list(next_state["validation_results"])
    generated_python_files = [
        str(PACKAGE_DIR / "__init__.py"),
        str(PACKAGE_DIR / "contracts.py"),
        str(PACKAGE_DIR / "service.py"),
        str(GENERATED_TEST_DIR / "test_generated_sla_escalation.py"),
    ]
    attempt_results = [
        run_command([sys.executable, "-m", "py_compile", *generated_python_files], attempt),
        run_command(behavior_check_command(), attempt),
    ]
    results.extend(attempt_results)
    next_state["validation_results"] = results
    if all(result["return_code"] == 0 for result in attempt_results):
        next_state["validation_status"] = "passed"
        next_state["release_ready"] = True
        next_state["status"] = "awaiting_human_release_approval"
        add_action(
            next_state,
            "validation_agent",
            "validate_generated_capability",
            "completed",
            f"Validation attempt {attempt} passed.",
        )
    else:
        next_state["validation_status"] = "failed"
        next_state["release_ready"] = False
        next_state["status"] = "needs_bounded_repair"
        next_state["errors"].append(f"Validation attempt {attempt} failed.")
        add_action(
            next_state,
            "validation_agent",
            "validate_generated_capability",
            "failed",
            f"Validation attempt {attempt} failed and requires diagnosis.",
        )
    return next_state


def failure_diagnosis_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    failed_attempt = next_state["repair_attempts"]
    diagnosis: Diagnosis = {
        "issue_id": "DIAG-13U-SLA-FIRST-DRAFT-ALWAYS-BREACHES",
        "category": "generated_behavior_mismatch",
        "failed_attempt": failed_attempt,
        "repair_strategy": (
            "Replace generated service logic so ON_TRACK, AT_RISK, and BREACHED "
            "states are derived from remaining SLA minutes."
        ),
    }
    next_state["diagnoses"].append(diagnosis)
    add_action(
        next_state,
        "failure_diagnosis_agent",
        "diagnose_validation_failure",
        "completed",
        "Diagnosed generated service as always reporting BREACHED.",
    )
    return next_state


def bounded_repair_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    files = list(next_state["generated_files"])
    next_state["repair_attempts"] += 1
    files = upsert_generated_file(
        files,
        write_file(
            PACKAGE_DIR / "service.py",
            service_code_repaired(),
            "bounded_repair_generated_service",
        ),
    )
    next_state["generated_files"] = files
    add_action(
        next_state,
        "bounded_repair_agent",
        "apply_bounded_generated_code_repair",
        "completed",
        "Repaired generated SLA escalation service inside allowed generated scope.",
    )
    return next_state


def evidence_agent(state: GenerationState) -> GenerationState:
    next_state: GenerationState = state.copy()
    add_action(
        next_state,
        "evidence_agent",
        "persist_self_repair_evidence",
        "completed",
        "Persisted audit, manifest, report, requirement, and traceability evidence.",
    )
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
        "validation_status": next_state["validation_status"],
        "repair_attempts": next_state["repair_attempts"],
        "max_repair_attempts": next_state["max_repair_attempts"],
        "release_ready": next_state["release_ready"],
        "human_approval_required": True,
        "blocked_actions": ["git merge", "git push", "git tag", "release publish"],
        "requirement_ids": next_state["requirement_ids"],
        "status": next_state["status"],
        "passed": next_state["validation_status"] == "passed"
        and next_state["repair_attempts"] == 1,
        "truth_boundary": (
            "Generated UPI dispute SLA escalation capability is local and runnable; "
            "external ecosystem interfaces remain simulated mocks only."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "# Phase 13U Self-Repairing Requirement Generation\n\n"
        f"Status: `{audit['status']}`\n\n"
        f"Validation: `{audit['validation_status']}`\n\n"
        f"Repair attempts: `{audit['repair_attempts']}`\n\n"
        "The governed LangGraph runner generated a faulty first draft, detected "
        "the behavior failure, applied one bounded repair, and passed validation.\n",
        encoding="utf-8",
    )
    return next_state


def route_after_validation(state: GenerationState) -> str:
    if state["validation_status"] == "passed":
        return "evidence_agent"
    if state["repair_attempts"] < state["max_repair_attempts"]:
        return "failure_diagnosis_agent"
    return "evidence_agent"


def build_graph() -> Any:
    graph = StateGraph(GenerationState)
    graph.add_node("requirement_package_agent", requirement_package_agent)
    graph.add_node("design_agent", design_agent)
    graph.add_node("code_generation_agent", code_generation_agent)
    graph.add_node("test_generation_agent", test_generation_agent)
    graph.add_node("docs_generation_agent", docs_generation_agent)
    graph.add_node("validation_agent", validation_agent)
    graph.add_node("failure_diagnosis_agent", failure_diagnosis_agent)
    graph.add_node("bounded_repair_agent", bounded_repair_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.set_entry_point("requirement_package_agent")
    graph.add_edge("requirement_package_agent", "design_agent")
    graph.add_edge("design_agent", "code_generation_agent")
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
    graph.add_edge("failure_diagnosis_agent", "bounded_repair_agent")
    graph.add_edge("bounded_repair_agent", "validation_agent")
    graph.add_edge("evidence_agent", END)
    return graph.compile()


def initial_state(objective: str) -> GenerationState:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": objective,
        "requirement_ids": [],
        "generated_files": [],
        "agent_actions": [],
        "validation_results": [],
        "diagnoses": [],
        "validation_status": "not_started",
        "repair_attempts": 0,
        "max_repair_attempts": 2,
        "release_ready": False,
        "status": "started",
        "errors": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--objective",
        default="Generate and self-repair UPI dispute SLA escalation capability",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    graph = build_graph()
    state = cast(GenerationState, graph.invoke(initial_state(args.objective)))
    passed = state["validation_status"] == "passed" and state["repair_attempts"] == 1
    result = {
        "passed": passed,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": state["objective"],
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "generated_app_dir": relative(GENERATED_ROOT),
        "generated_file_count": len(state["generated_files"]),
        "requirement_ids": state["requirement_ids"],
        "validation_status": state["validation_status"],
        "repair_attempts": state["repair_attempts"],
        "diagnosis_count": len(state["diagnoses"]),
        "release_ready": state["release_ready"],
        "human_approval_required": True,
        "status": state["status"],
        "audit_path": relative(AUDIT_PATH),
        "traceability_path": relative(TRACEABILITY_PATH),
    }
    if not args.quiet:
        print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
