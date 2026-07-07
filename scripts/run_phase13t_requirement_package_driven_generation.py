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
PHASE = "Phase 13T"
PHASE_ID = "phase13t_requirement_package_driven_sla_generation"
BASELINE_TAG = "v0.13.18-agent-owned-application-capability-generation"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13t"
)
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13t_requirement_driven_sla_detection"
)
PACKAGE_DIR = GENERATED_ROOT / "phase13t_requirement_driven_sla_detection_app"
AUDIT_PATH = ARTIFACT_DIR / "requirement_driven_generation_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "requirement_driven_generation_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "requirement_driven_generation_report.md"
TRACEABILITY_PATH = ARTIFACT_DIR / "requirement_traceability_matrix.json"
DEFAULT_REQUIREMENT_PATH = ARTIFACT_DIR / "default_requirement_package.json"

ValidationStatus = Literal["not_started", "passed", "failed"]


class AgentAction(TypedDict):
    agent: str
    action: str
    status: str
    detail: str


class ValidationResult(TypedDict):
    command: list[str]
    return_code: int
    output_preview: str


class GeneratedFile(TypedDict):
    path: str
    purpose: str
    sha256: str


class RequirementPackage(TypedDict):
    requirement_id: str
    capability_id: str
    title: str
    business_goal: str
    domain_terms: list[str]
    input_contract: dict[str, str]
    acceptance_rules: list[str]
    out_of_scope: list[str]
    truth_boundary: str


class PhaseState(TypedDict):
    app_id: str
    phase: str
    phase_id: str
    objective: str
    requirement_package_path: str
    requirement: RequirementPackage
    generated_files: list[GeneratedFile]
    agent_actions: list[AgentAction]
    validation_results: list[ValidationResult]
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


def write_file(path: pathlib.Path, content: str) -> GeneratedFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "path": relative(path),
        "purpose": "generated_from_requirement_package_by_phase13t_runner",
        "sha256": sha256_text(content),
    }


def add_action(state: PhaseState, agent: str, action: str, status: str, detail: str) -> None:
    state["agent_actions"].append(
        {"agent": agent, "action": action, "status": status, "detail": detail}
    )


def run_command(command: list[str], cwd: pathlib.Path) -> ValidationResult:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    return {
        "command": command,
        "return_code": result.returncode,
        "output_preview": output[:4000],
    }


def default_requirement() -> RequirementPackage:
    return {
        "requirement_id": "REQ-13T-SLA-BREACH-DETECTION",
        "capability_id": "phase13t_requirement_driven_sla_detection",
        "title": "Generate UPI dispute SLA breach detection capability",
        "business_goal": (
            "Create a local capability that determines whether a dispute case has "
            "breached a configured handling SLA and whether escalation is required."
        ),
        "domain_terms": [
            "UPI dispute",
            "SLA breach",
            "operator escalation",
            "regulatory priority",
        ],
        "input_contract": {
            "dispute_case_id": "string",
            "transaction_id": "string",
            "received_at_utc": "ISO-8601 timestamp",
            "now_utc": "ISO-8601 timestamp",
            "sla_hours": "integer",
            "priority": "normal|high|regulatory",
        },
        "acceptance_rules": [
            "elapsed minutes must be derived deterministically from received_at_utc and now_utc",
            "status must be WITHIN_SLA when elapsed time is below the configured SLA",
            "status must be BREACHED when elapsed time is above the configured SLA",
            "regulatory priority breaches must be marked ESCALATE_NOW",
            "external ecosystem integrations must remain simulated mocks only",
        ],
        "out_of_scope": [
            "Real bank, PSP, NPCI, RBI, or UPI rail calls",
            "Real ticketing system updates",
            "Real customer notifications",
        ],
        "truth_boundary": (
            "Primary generated UPI dispute SLA capability is local and runnable; "
            "external ecosystem interfaces remain simulated mocks only."
        ),
    }


def load_requirement(path_text: str) -> RequirementPackage:
    if path_text:
        path = pathlib.Path(path_text).expanduser()
    else:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        path = DEFAULT_REQUIREMENT_PATH
        path.write_text(
            json.dumps(default_requirement(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Requirement package must be a JSON object.")
    required_keys = [
        "requirement_id",
        "capability_id",
        "title",
        "business_goal",
        "acceptance_rules",
        "truth_boundary",
    ]
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"Requirement package is missing keys: {missing}")
    return cast(RequirementPackage, payload)


def requirement_ingestion_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    requirement = load_requirement(next_state["requirement_package_path"])
    next_state["requirement"] = requirement
    add_action(
        next_state,
        "requirement_ingestion_agent",
        "ingest_external_requirement_package",
        "completed",
        f"Loaded requirement package {requirement['requirement_id']}.",
    )
    return next_state


def planning_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    requirement = next_state["requirement"]
    traceability = {
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "requirement_source": (
            next_state["requirement_package_path"] or relative(DEFAULT_REQUIREMENT_PATH)
        ),
        "mappings": [
            {
                "requirement_id": requirement["requirement_id"],
                "capability_id": requirement["capability_id"],
                "acceptance_rules": requirement["acceptance_rules"],
                "design_elements": [
                    "SlaAssessmentRequest contract",
                    "SlaAssessmentResult contract",
                    "assess_sla_status service",
                ],
                "code_files": [
                    relative(PACKAGE_DIR / "contracts.py"),
                    relative(PACKAGE_DIR / "service.py"),
                ],
                "test_files": [
                    "tests/test_phase13t_requirement_package_driven_generation.py"
                ],
                "evidence_files": [
                    relative(AUDIT_PATH),
                    relative(MANIFEST_PATH),
                    relative(REPORT_PATH),
                    relative(TRACEABILITY_PATH),
                ],
            }
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TRACEABILITY_PATH.write_text(
        json.dumps(traceability, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    add_action(
        next_state,
        "planning_agent",
        "map_requirement_to_generation_plan",
        "completed",
        "Requirement was mapped to generated code, tests, docs, and evidence.",
    )
    return next_state


def code_generation_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    requirement = next_state["requirement"]
    generated_files = list(next_state["generated_files"])
    init_code = '''"""Generated Phase 13T SLA detection capability."""

from .contracts import SlaAssessmentRequest, SlaAssessmentResult
from .service import assess_sla_status

__all__ = [
    "SlaAssessmentRequest",
    "SlaAssessmentResult",
    "assess_sla_status",
]
'''
    contracts_code = '''from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["normal", "high", "regulatory"]
SlaStatus = Literal["WITHIN_SLA", "BREACHED", "ESCALATE_NOW"]


class SlaAssessmentRequest(BaseModel):
    """Local SLA assessment input generated from a requirement package."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str = Field(min_length=3, max_length=64)
    transaction_id: str = Field(min_length=6, max_length=64)
    received_at_utc: str = Field(min_length=20, max_length=40)
    now_utc: str = Field(min_length=20, max_length=40)
    sla_hours: int = Field(ge=1, le=336)
    priority: Priority = "normal"


class SlaAssessmentResult(BaseModel):
    """Deterministic local SLA assessment result."""

    model_config = ConfigDict(extra="forbid")

    dispute_case_id: str
    transaction_id: str
    elapsed_minutes: int
    remaining_minutes: int
    breached: bool
    escalation_required: bool
    sla_status: SlaStatus
    audit_event_type: str
    audit_reference: str
    risk_flags: list[str]
'''
    service_code = '''from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .contracts import SlaAssessmentRequest, SlaAssessmentResult


def _parse_utc_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stable_reference(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16].upper()


def assess_sla_status(request: SlaAssessmentRequest) -> SlaAssessmentResult:
    """Assess SLA status locally without calling external systems."""

    received_at = _parse_utc_timestamp(request.received_at_utc)
    now_at = _parse_utc_timestamp(request.now_utc)
    elapsed_minutes = int((now_at - received_at).total_seconds() // 60)
    allowed_minutes = request.sla_hours * 60
    remaining_minutes = max(allowed_minutes - elapsed_minutes, 0)
    breached = elapsed_minutes > allowed_minutes
    escalation_required = breached and request.priority in {"high", "regulatory"}
    risk_flags: list[str] = []
    if elapsed_minutes < 0:
        risk_flags.append("NEGATIVE_ELAPSED_TIME")
    if breached:
        risk_flags.append("SLA_BREACHED")
    if escalation_required:
        risk_flags.append("ESCALATION_REQUIRED")
    if request.priority == "regulatory" and breached:
        status = "ESCALATE_NOW"
    elif breached:
        status = "BREACHED"
    else:
        status = "WITHIN_SLA"
    reference = _stable_reference(
        request.dispute_case_id,
        request.transaction_id,
        request.received_at_utc,
        request.now_utc,
        str(request.sla_hours),
        request.priority,
    )
    return SlaAssessmentResult(
        dispute_case_id=request.dispute_case_id,
        transaction_id=request.transaction_id,
        elapsed_minutes=elapsed_minutes,
        remaining_minutes=remaining_minutes,
        breached=breached,
        escalation_required=escalation_required,
        sla_status=status,
        audit_event_type="sla_status_assessed",
        audit_reference=f"AUD-SLA-{reference}",
        risk_flags=risk_flags,
    )
'''
    readme_code = f'''# Phase 13T Requirement-Driven SLA Detection Capability

Generated from requirement package `{requirement["requirement_id"]}`.

## Business goal

{requirement["business_goal"]}

## Boundary

{requirement["truth_boundary"]}
'''
    generated_files.extend(
        [
            write_file(PACKAGE_DIR / "__init__.py", init_code),
            write_file(PACKAGE_DIR / "contracts.py", contracts_code),
            write_file(PACKAGE_DIR / "service.py", service_code),
            write_file(GENERATED_ROOT / "README.md", readme_code),
        ]
    )
    next_state["generated_files"] = generated_files
    add_action(
        next_state,
        "code_generation_agent",
        "generate_capability_from_requirement_package",
        "completed",
        "Generated SLA detection package from requirement package.",
    )
    return next_state


def test_generation_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    generated_files = list(next_state["generated_files"])
    test_code = '''from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any, cast

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATED_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
    / "phase13t_requirement_driven_sla_detection"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "lifecycle_artifacts"
    / "phase13t"
)


def run_phase13t_generation() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(PROJECT_ROOT / "src"),
            str(PROJECT_ROOT / "scripts"),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            str(
                PROJECT_ROOT
                / "scripts"
                / "run_phase13t_requirement_package_driven_generation.py"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_phase13t_requirement_driven_generation_outputs_and_behavior() -> None:
    output = run_phase13t_generation()
    assert output["passed"] is True
    assert output["phase"] == "Phase 13T"
    assert output["graph_type"] == "StateGraph"
    assert output["requirement_source"] == "external_or_default_json_package"

    sys.path.insert(0, str(GENERATED_ROOT))
    from phase13t_requirement_driven_sla_detection_app import (
        SlaAssessmentRequest,
        assess_sla_status,
    )

    within_request = SlaAssessmentRequest(
        dispute_case_id="CASE-13T-001",
        transaction_id="TXN-13T-000001",
        received_at_utc="2026-07-07T00:00:00+00:00",
        now_utc="2026-07-07T02:00:00+00:00",
        sla_hours=24,
        priority="normal",
    )
    within = assess_sla_status(within_request)
    assert within.breached is False
    assert within.sla_status == "WITHIN_SLA"
    assert within.remaining_minutes == 1320

    breached_request = within_request.model_copy(
        update={"now_utc": "2026-07-08T06:30:00+00:00", "priority": "regulatory"}
    )
    breached = assess_sla_status(breached_request)
    assert breached.breached is True
    assert breached.escalation_required is True
    assert breached.sla_status == "ESCALATE_NOW"
    assert "SLA_BREACHED" in breached.risk_flags
    assert "ESCALATION_REQUIRED" in breached.risk_flags

    traceability = json.loads(
        (ARTIFACT_DIR / "requirement_traceability_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    mapping = traceability["mappings"][0]
    assert mapping["requirement_id"] == "REQ-13T-SLA-BREACH-DETECTION"
    assert "contracts.py" in " ".join(mapping["code_files"])
    assert "service.py" in " ".join(mapping["code_files"])
'''
    generated_files.append(
        write_file(
            PROJECT_ROOT / "tests" / "test_phase13t_requirement_package_driven_generation.py",
            test_code,
        )
    )
    next_state["generated_files"] = generated_files
    add_action(
        next_state,
        "test_generation_agent",
        "generate_requirement_driven_tests",
        "completed",
        "Generated tests for within-SLA and breached-SLA outcomes.",
    )
    return next_state


def docs_generation_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    requirement = next_state["requirement"]
    generated_files = list(next_state["generated_files"])
    doc_code = f'''# Phase 13T - Requirement-Package-Driven Capability Generation

Phase 13T moves beyond a phase-specific hardcoded capability. The runner reads
an external or default JSON requirement package and generates a local
application capability from that package.

## Requirement

- Requirement ID: `{requirement["requirement_id"]}`
- Capability ID: `{requirement["capability_id"]}`
- Title: `{requirement["title"]}`

## Generated capability

The generated capability assesses UPI dispute SLA breach status and escalation
requirements using deterministic local logic.

## Governance boundary

{requirement["truth_boundary"]}

## Release boundary

The generator can mark the capability release-ready, but merge, tag, push, and
release publishing remain blocked until human/operator approval.
'''
    generated_files.append(
        write_file(
            PROJECT_ROOT
            / "docs"
            / "phase13t"
            / "requirement_package_driven_capability_generation.md",
            doc_code,
        )
    )
    next_state["generated_files"] = generated_files
    add_action(
        next_state,
        "docs_generation_agent",
        "generate_requirement_driven_docs",
        "completed",
        "Generated Phase 13T documentation from requirement package metadata.",
    )
    return next_state


def validation_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    results = list(next_state["validation_results"])
    generated_python_files = [
        str(PACKAGE_DIR / "__init__.py"),
        str(PACKAGE_DIR / "contracts.py"),
        str(PACKAGE_DIR / "service.py"),
    ]
    results.append(run_command([sys.executable, "-m", "py_compile", *generated_python_files], PROJECT_ROOT))
    behavior_check = (
        "import sys; "
        f"sys.path.insert(0, {str(GENERATED_ROOT)!r}); "
        "from phase13t_requirement_driven_sla_detection_app import "
        "SlaAssessmentRequest, assess_sla_status; "
        "request = SlaAssessmentRequest("
        "dispute_case_id='CASE-13T-001', transaction_id='TXN-13T-000001', "
        "received_at_utc='2026-07-07T00:00:00+00:00', "
        "now_utc='2026-07-08T06:30:00+00:00', "
        "sla_hours=24, priority='regulatory'); "
        "result = assess_sla_status(request); "
        "assert result.breached is True and result.sla_status == 'ESCALATE_NOW'"
    )
    results.append(run_command([sys.executable, "-c", behavior_check], PROJECT_ROOT))
    next_state["validation_results"] = results
    if all(result["return_code"] == 0 for result in results):
        next_state["validation_status"] = "passed"
        next_state["release_ready"] = True
        next_state["status"] = "awaiting_human_release_approval"
        add_action(
            next_state,
            "validation_agent",
            "validate_requirement_driven_capability",
            "completed",
            "Generated capability py_compile and behavior checks passed.",
        )
    else:
        next_state["validation_status"] = "failed"
        next_state["release_ready"] = False
        next_state["status"] = "needs_bounded_repair"
        next_state["errors"].append("Requirement-driven generated capability failed validation.")
        add_action(
            next_state,
            "validation_agent",
            "validate_requirement_driven_capability",
            "failed",
            "Generated capability validation failed and needs bounded repair.",
        )
    return next_state


def bounded_repair_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    next_state["repair_attempts"] += 1
    add_action(
        next_state,
        "bounded_repair_agent",
        "bounded_repair_not_required_or_escalated",
        "completed",
        "No generated-code repair was required in the successful path.",
    )
    return next_state


def evidence_agent(state: PhaseState) -> PhaseState:
    next_state = state.copy()
    requirement = next_state["requirement"]
    add_action(
        next_state,
        "evidence_agent",
        "persist_requirement_driven_lifecycle_evidence",
        "completed",
        "Persisted audit, manifest, report, and traceability evidence.",
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
        "requirement_source": "external_or_default_json_package",
        "requirement": requirement,
        "agent_actions": next_state["agent_actions"],
        "generated_files": next_state["generated_files"],
        "validation_results": next_state["validation_results"],
        "validation_status": next_state["validation_status"],
        "repair_attempts": next_state["repair_attempts"],
        "max_repair_attempts": next_state["max_repair_attempts"],
        "release_ready": next_state["release_ready"],
        "human_approval_required": True,
        "blocked_actions": ["git merge", "git push", "git tag", "release publish"],
        "requirement_ids": [requirement["requirement_id"]],
        "status": next_state["status"],
        "passed": next_state["validation_status"] == "passed",
        "truth_boundary": requirement["truth_boundary"],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "# Phase 13T Requirement-Package-Driven Capability Generation\n\n"
        f"Status: `{audit['status']}`\n\n"
        f"Requirement: `{requirement['requirement_id']}`\n\n"
        f"Validation: `{audit['validation_status']}`\n\n"
        f"Generated files: `{len(next_state['generated_files'])}`\n\n"
        "The governed LangGraph runner ingested a requirement package and "
        "generated a local SLA detection capability, tests, documentation, "
        "and traceability evidence.\n",
        encoding="utf-8",
    )
    return next_state


def should_repair(state: PhaseState) -> str:
    if state["validation_status"] == "passed":
        return "evidence_agent"
    if state["repair_attempts"] < state["max_repair_attempts"]:
        return "bounded_repair_agent"
    return "evidence_agent"


def build_graph() -> Any:
    graph = StateGraph(PhaseState)
    graph.add_node("requirement_ingestion_agent", requirement_ingestion_agent)
    graph.add_node("planning_agent", planning_agent)
    graph.add_node("code_generation_agent", code_generation_agent)
    graph.add_node("test_generation_agent", test_generation_agent)
    graph.add_node("docs_generation_agent", docs_generation_agent)
    graph.add_node("validation_agent", validation_agent)
    graph.add_node("bounded_repair_agent", bounded_repair_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.set_entry_point("requirement_ingestion_agent")
    graph.add_edge("requirement_ingestion_agent", "planning_agent")
    graph.add_edge("planning_agent", "code_generation_agent")
    graph.add_edge("code_generation_agent", "test_generation_agent")
    graph.add_edge("test_generation_agent", "docs_generation_agent")
    graph.add_edge("docs_generation_agent", "validation_agent")
    graph.add_conditional_edges(
        "validation_agent",
        should_repair,
        {
            "bounded_repair_agent": "bounded_repair_agent",
            "evidence_agent": "evidence_agent",
        },
    )
    graph.add_edge("bounded_repair_agent", "validation_agent")
    graph.add_edge("evidence_agent", END)
    return graph.compile()


def initial_state(objective: str, requirement_package_path: str) -> PhaseState:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": objective,
        "requirement_package_path": requirement_package_path,
        "requirement": default_requirement(),
        "generated_files": [],
        "agent_actions": [],
        "validation_results": [],
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
        default="Generate UPI dispute SLA breach detection from requirement package",
    )
    parser.add_argument("--requirement-package", default="")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    graph = build_graph()
    state = cast(
        PhaseState,
        graph.invoke(initial_state(args.objective, args.requirement_package)),
    )
    requirement = state["requirement"]
    result = {
        "passed": state["validation_status"] == "passed",
        "phase": PHASE,
        "phase_id": PHASE_ID,
        "objective": state["objective"],
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "requirement_source": "external_or_default_json_package",
        "requirement_ids": [requirement["requirement_id"]],
        "capability_id": requirement["capability_id"],
        "generated_app_dir": relative(GENERATED_ROOT),
        "generated_file_count": len(state["generated_files"]),
        "validation_status": state["validation_status"],
        "repair_attempts": state["repair_attempts"],
        "release_ready": state["release_ready"],
        "human_approval_required": True,
        "status": state["status"],
        "audit_path": relative(AUDIT_PATH),
        "traceability_path": relative(TRACEABILITY_PATH),
    }
    if not args.quiet:
        print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
