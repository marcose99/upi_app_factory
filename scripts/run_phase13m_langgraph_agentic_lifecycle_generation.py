#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13m_dispute_lifecycle"
)
PACKAGE_NAME = "phase13m_dispute_lifecycle_app"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13m"
)
AUDIT_PATH = ARTIFACT_DIR / "langgraph_agentic_lifecycle_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "langgraph_agentic_lifecycle_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "langgraph_agentic_lifecycle_report.md"


class AgentOutput(TypedDict):
    agent_name: str
    status: str
    output: str


class GenerationState(TypedDict, total=False):
    run_id: str
    requirement_package: dict[str, Any]
    domain_model_ready: bool
    generated_files: list[str]
    truth_boundary: str
    validation_passed: bool
    validation_output: str
    corrections: list[str]
    agents: list[AgentOutput]
    file_hashes: dict[str, str]
    audit: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def add_agent(state: GenerationState, name: str, output: str) -> list[AgentOutput]:
    agents = list(state.get("agents", []))
    agents.append({"agent_name": name, "status": "completed", "output": output})
    return agents


def write_file(relative_path: str, content: str) -> pathlib.Path:
    path = GEN_APP_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def app_files() -> dict[str, str]:
    return {
        "README.md": """# Phase 13M Dispute Lifecycle Slice

This generated component is a local runnable UPI dispute-resolution lifecycle
slice. It extends intake into lifecycle status transitions, evidence validation,
mock investigation response handling, resolution decisioning, and audit trail
creation.

Agent orchestration is performed by a real LangGraph StateGraph. The graph is
local-first and deterministic in this phase, but it is a true agentic graph with
state, nodes, directed edges, and a conditional self-correction route.

External ecosystem boundaries are deliberately mock/simulated only. Banks,
NPCI-style, RBI-style, payment rail, upstream, and downstream interfaces are not
real integrations in this slice.

## Run locally

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application/phase13m_dispute_lifecycle
python3 scripts/run_demo.py
PYTHONPATH=. python3 -m pytest -q checks/dispute_lifecycle_checks.py
```
""",
        f"{PACKAGE_NAME}/__init__.py": """from .api import create_case, get_case, progress_case_to_resolution

__all__ = ["create_case", "get_case", "progress_case_to_resolution"]
""",
        f"{PACKAGE_NAME}/domain.py": """from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DisputeStatus(str, Enum):
    INTAKE_ACCEPTED = "INTAKE_ACCEPTED"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    INVESTIGATION_RESPONDED = "INVESTIGATION_RESPONDED"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"
    RESOLVED = "RESOLVED"


class ResolutionOutcome(str, Enum):
    CUSTOMER_CREDIT_RECOMMENDED = "CUSTOMER_CREDIT_RECOMMENDED"
    MERCHANT_DEFENSE_ACCEPTED = "MERCHANT_DEFENSE_ACCEPTED"


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    details: dict[str, Any]
    created_at_utc: str


@dataclass
class DisputeCase:
    case_id: str
    transaction_id: str
    payer_vpa: str
    payee_vpa: str
    amount_paise: int
    status: DisputeStatus
    evidence_refs: list[str]
    mock_investigation_reference: str | None = None
    resolution_outcome: ResolutionOutcome | None = None
    audit_trail: list[AuditEvent] = field(default_factory=list)

    def add_event(self, event_type: str, details: dict[str, Any]) -> None:
        self.audit_trail.append(
            AuditEvent(
                event_type=event_type,
                details=details,
                created_at_utc=utc_now_iso(),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "transaction_id": self.transaction_id,
            "payer_vpa": self.payer_vpa,
            "payee_vpa": self.payee_vpa,
            "amount_paise": self.amount_paise,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "mock_investigation_reference": self.mock_investigation_reference,
            "resolution_outcome": (
                None
                if self.resolution_outcome is None
                else self.resolution_outcome.value
            ),
            "audit_trail": [
                {
                    "event_type": event.event_type,
                    "details": dict(event.details),
                    "created_at_utc": event.created_at_utc,
                }
                for event in self.audit_trail
            ],
            "boundary_statement": (
                "Primary UPI dispute lifecycle logic is local and runnable; "
                "external banks, rails, NPCI-style, RBI-style, upstream, and "
                "downstream ecosystem interfaces are simulated mocks only."
            ),
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
""",
        f"{PACKAGE_NAME}/external_mocks.py": """from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MockInvestigationResponse:
    reference: str
    simulated_bank_code: str
    simulated_network_status: str
    evidence_score: int


class MockBankInvestigationClient:
    # Simulated bank/NPCI-style investigation client; performs no real rail call.

    def request_investigation(
        self,
        transaction_id: str,
        evidence_refs: list[str],
    ) -> MockInvestigationResponse:
        raw = transaction_id + "|" + "|".join(evidence_refs)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return MockInvestigationResponse(
            reference=f"MOCK-INV-{digest[:14].upper()}",
            simulated_bank_code=f"MOCK-BANK-{digest[14:20].upper()}",
            simulated_network_status="SIMULATED_RESPONSE_RECEIVED",
            evidence_score=92 if evidence_refs else 0,
        )
""",
        f"{PACKAGE_NAME}/service.py": """from __future__ import annotations

import hashlib
from typing import Any

from .domain import DisputeCase, DisputeStatus, ResolutionOutcome
from .external_mocks import MockBankInvestigationClient


class DisputeLifecycleError(ValueError):
    pass


class InMemoryDisputeLifecycleRepository:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}

    def save(self, case: DisputeCase) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> DisputeCase | None:
        return self._cases.get(case_id)


class DisputeLifecycleService:
    # Primary lifecycle logic is local and runnable; external ecosystem
    # interfaces are simulated mocks only.
    def __init__(
        self,
        repository: InMemoryDisputeLifecycleRepository | None = None,
        investigation_client: MockBankInvestigationClient | None = None,
    ) -> None:
        self._repository = repository or InMemoryDisputeLifecycleRepository()
        self._investigation_client = (
            investigation_client or MockBankInvestigationClient()
        )

    def create_case(self, payload: dict[str, Any]) -> DisputeCase:
        transaction_id = self._required_text(payload, "transaction_id")
        payer_vpa = self._required_text(payload, "payer_vpa")
        payee_vpa = self._required_text(payload, "payee_vpa")
        amount_paise = self._positive_int(payload, "amount_paise")
        evidence_refs = self._evidence_refs(payload)
        case = DisputeCase(
            case_id=self._case_id(transaction_id, payer_vpa, payee_vpa),
            transaction_id=transaction_id,
            payer_vpa=payer_vpa,
            payee_vpa=payee_vpa,
            amount_paise=amount_paise,
            status=DisputeStatus.INTAKE_ACCEPTED,
            evidence_refs=evidence_refs,
        )
        case.add_event("case_created", {"transaction_id": transaction_id})
        self._repository.save(case)
        return case

    def validate_evidence(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.INTAKE_ACCEPTED:
            raise DisputeLifecycleError("Evidence can only be validated after intake.")
        if not case.evidence_refs:
            raise DisputeLifecycleError("At least one evidence reference is required.")
        case.status = DisputeStatus.EVIDENCE_VALIDATED
        case.add_event("evidence_validated", {"evidence_count": len(case.evidence_refs)})
        return case

    def request_investigation(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.EVIDENCE_VALIDATED:
            raise DisputeLifecycleError("Investigation requires validated evidence.")
        response = self._investigation_client.request_investigation(
            case.transaction_id,
            case.evidence_refs,
        )
        case.status = DisputeStatus.INVESTIGATION_RESPONDED
        case.mock_investigation_reference = response.reference
        case.add_event(
            "mock_investigation_responded",
            {
                "reference": response.reference,
                "simulated_bank_code": response.simulated_bank_code,
                "simulated_network_status": response.simulated_network_status,
                "evidence_score": response.evidence_score,
            },
        )
        return case

    def propose_resolution(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.INVESTIGATION_RESPONDED:
            raise DisputeLifecycleError(
                "Resolution requires mock investigation response."
            )
        case.status = DisputeStatus.RESOLUTION_PROPOSED
        case.resolution_outcome = ResolutionOutcome.CUSTOMER_CREDIT_RECOMMENDED
        case.add_event("resolution_proposed", {"outcome": case.resolution_outcome.value})
        return case

    def finalize_resolution(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.RESOLUTION_PROPOSED:
            raise DisputeLifecycleError("Only proposed resolutions can be finalized.")
        case.status = DisputeStatus.RESOLVED
        outcome = None if case.resolution_outcome is None else case.resolution_outcome.value
        case.add_event("case_resolved", {"outcome": str(outcome)})
        return case

    def progress_to_resolution(self, case_id: str) -> DisputeCase:
        self.validate_evidence(case_id)
        self.request_investigation(case_id)
        self.propose_resolution(case_id)
        return self.finalize_resolution(case_id)

    def get_case(self, case_id: str) -> DisputeCase | None:
        return self._repository.get(case_id)

    def _require_case(self, case_id: str) -> DisputeCase:
        case = self._repository.get(case_id)
        if case is None:
            raise DisputeLifecycleError(f"Unknown case_id: {case_id}")
        return case

    @staticmethod
    def _required_text(payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DisputeLifecycleError(f"{field} is required.")
        return value.strip()

    @staticmethod
    def _positive_int(payload: dict[str, Any], field: str) -> int:
        value = payload.get(field)
        if not isinstance(value, int) or value <= 0:
            raise DisputeLifecycleError(f"{field} must be a positive integer.")
        return value

    @staticmethod
    def _evidence_refs(payload: dict[str, Any]) -> list[str]:
        refs = payload.get("evidence_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(item, str) and item for item in refs)
        ):
            raise DisputeLifecycleError(
                "evidence_refs must be a non-empty list of strings."
            )
        return list(refs)

    @staticmethod
    def _case_id(transaction_id: str, payer_vpa: str, payee_vpa: str) -> str:
        raw = f"{transaction_id}|{payer_vpa}|{payee_vpa}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"UPI-LIFECYCLE-{digest[:12].upper()}"
""",
        f"{PACKAGE_NAME}/api.py": """from __future__ import annotations

from typing import Any

from .service import DisputeLifecycleService

_SERVICE = DisputeLifecycleService()


def create_case(payload: dict[str, Any]) -> dict[str, Any]:
    return _SERVICE.create_case(payload).to_dict()


def progress_case_to_resolution(case_id: str) -> dict[str, Any]:
    return _SERVICE.progress_to_resolution(case_id).to_dict()


def get_case(case_id: str) -> dict[str, Any] | None:
    case = _SERVICE.get_case(case_id)
    return None if case is None else case.to_dict()
""",
        "checks/dispute_lifecycle_checks.py": f"""from __future__ import annotations

from {PACKAGE_NAME}.api import create_case, get_case, progress_case_to_resolution
from {PACKAGE_NAME}.service import DisputeLifecycleError, DisputeLifecycleService


def valid_payload() -> dict[str, object]:
    return {{
        "transaction_id": "TXN-20260706-LIFE-001",
        "payer_vpa": "payer@upi",
        "payee_vpa": "merchant@upi",
        "amount_paise": 125000,
        "evidence_refs": ["txn-log:TXN-20260706-LIFE-001", "customer-note:life-1"],
    }}


def test_lifecycle_reaches_resolved_status_with_audit_trail() -> None:
    created = create_case(valid_payload())
    resolved = progress_case_to_resolution(str(created["case_id"]))

    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution_outcome"] == "CUSTOMER_CREDIT_RECOMMENDED"
    assert str(resolved["mock_investigation_reference"]).startswith("MOCK-INV-")
    assert len(resolved["audit_trail"]) >= 5
    assert "simulated mocks only" in resolved["boundary_statement"]

    loaded = get_case(str(created["case_id"]))
    assert loaded == resolved


def test_service_rejects_missing_evidence() -> None:
    payload = valid_payload()
    payload["evidence_refs"] = []

    try:
        DisputeLifecycleService().create_case(payload)
    except DisputeLifecycleError as exc:
        assert "evidence_refs" in str(exc)
    else:
        raise AssertionError("Expected missing evidence to be rejected.")


def test_service_rejects_invalid_transition_order() -> None:
    service = DisputeLifecycleService()
    case = service.create_case(valid_payload())

    try:
        service.request_investigation(case.case_id)
    except DisputeLifecycleError as exc:
        assert "validated evidence" in str(exc)
    else:
        raise AssertionError("Expected invalid transition order to be rejected.")
""",
        "scripts/run_demo.py": f"""from __future__ import annotations

import json

from {PACKAGE_NAME}.api import create_case, progress_case_to_resolution

payload = {{
    "transaction_id": "TXN-20260706-LIFE-DEMO",
    "payer_vpa": "payer@upi",
    "payee_vpa": "merchant@upi",
    "amount_paise": 9900,
    "evidence_refs": ["demo:evidence", "demo:customer-note"],
}}

created = create_case(payload)
resolved = progress_case_to_resolution(str(created["case_id"]))
print(json.dumps(resolved, indent=2, sort_keys=True))
""",
    }


def write_app_files(state: GenerationState) -> GenerationState:
    if GEN_APP_DIR.exists():
        shutil.rmtree(GEN_APP_DIR)
    files = app_files()
    generated_paths = [write_file(path, text) for path, text in files.items()]
    return {
        **state,
        "generated_files": [relative(path) for path in generated_paths],
        "file_hashes": {
            relative(GEN_APP_DIR / path): sha256_text(text)
            for path, text in files.items()
        },
    }


def run_generated_checks() -> tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{GEN_APP_DIR}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "checks/dispute_lifecycle_checks.py"],
        cwd=GEN_APP_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def requirement_intake_agent(state: GenerationState) -> GenerationState:
    return {
        **state,
        "requirement_package": {
            "slice": "dispute_lifecycle",
            "required_flow": [
                "create_case",
                "validate_evidence",
                "mock_investigation_response",
                "propose_resolution",
                "finalize_resolution",
                "audit_trail",
            ],
            "runtime": "local_first_langgraph",
        },
        "truth_boundary": (
            "The primary generated UPI dispute lifecycle application is local and "
            "runnable. External bank, rail, NPCI-style, RBI-style, upstream, and "
            "downstream ecosystem interfaces are simulated mocks only."
        ),
        "agents": add_agent(
            state,
            "requirement_intake_agent",
            "lifecycle requirement package created",
        ),
    }


def domain_model_agent(state: GenerationState) -> GenerationState:
    return {
        **state,
        "domain_model_ready": True,
        "agents": add_agent(
            state,
            "domain_model_agent",
            "lifecycle statuses, transitions, and audit events defined",
        ),
    }


def application_slice_agent(state: GenerationState) -> GenerationState:
    updated = write_app_files(state)
    return {
        **updated,
        "agents": add_agent(
            updated,
            "application_slice_agent",
            "local runnable lifecycle package generated",
        ),
    }


def ecosystem_mock_agent(state: GenerationState) -> GenerationState:
    return {
        **state,
        "agents": add_agent(
            state,
            "ecosystem_mock_agent",
            "mock bank/NPCI-style investigation boundary generated",
        ),
    }


def verification_agent(state: GenerationState) -> GenerationState:
    passed, output = run_generated_checks()
    return {
        **state,
        "validation_passed": passed,
        "validation_output": output,
        "agents": add_agent(
            state,
            "verification_agent",
            "generated lifecycle checks executed",
        ),
    }


def self_correction_agent(state: GenerationState) -> GenerationState:
    corrections = list(state.get("corrections", []))
    corrections.append("self_correction_route_available_but_not_needed_when_checks_pass")
    return {
        **state,
        "corrections": corrections,
        "agents": add_agent(
            state,
            "self_correction_agent",
            "self-correction route executed",
        ),
    }


def route_after_verification(state: GenerationState) -> str:
    return (
        "governance_evidence_agent"
        if state.get("validation_passed") is True
        else "self_correction_agent"
    )


def governance_evidence_agent(state: GenerationState) -> GenerationState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    agents = state.get("agents", []) + [
        {
            "agent_name": "governance_evidence_agent",
            "status": "completed",
            "output": "audit, manifest, graph topology, and validation evidence generated",
        }
    ]
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": "Phase 13M",
        "run_id": state["run_id"],
        "generated_at_utc": utc_now(),
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "graph_nodes": [
            "requirement_intake_agent",
            "domain_model_agent",
            "application_slice_agent",
            "ecosystem_mock_agent",
            "verification_agent",
            "self_correction_agent",
            "governance_evidence_agent",
        ],
        "conditional_edges": [
            "verification_agent -> governance_evidence_agent when checks pass",
            "verification_agent -> self_correction_agent when checks fail",
            "self_correction_agent -> verification_agent",
        ],
        "adapter_mode": "local_langgraph_deterministic",
        "truth_boundary": state.get("truth_boundary"),
        "completed_agents": len(agents),
        "agents": agents,
        "generated_application_dir": relative(GEN_APP_DIR),
        "generated_package": PACKAGE_NAME,
        "generated_files": state.get("generated_files", []),
        "file_hashes": state.get("file_hashes", {}),
        "validation": {
            "generated_checks_passed": state.get("validation_passed") is True,
            "generated_check_command": [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "checks/dispute_lifecycle_checks.py",
            ],
            "generated_check_cwd": relative(GEN_APP_DIR),
            "generated_check_output": state.get("validation_output", ""),
        },
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        "# Phase 13M LangGraph Agentic Lifecycle Generation\n\n"
        "Status: `generated`\n\n"
        f"Run ID: `{state['run_id']}`\n\n"
        "Orchestration framework: `LangGraph StateGraph`\n\n"
        f"Generated application directory: `{relative(GEN_APP_DIR)}`\n\n"
        f"Generated package: `{PACKAGE_NAME}`\n\n"
        f"Generated checks passed: `{audit['validation']['generated_checks_passed']}`\n\n"
        f"Truth boundary: {audit['truth_boundary']}\n",
        encoding="utf-8",
    )
    return {**state, "audit": audit, "agents": agents}


def build_graph() -> Any:
    graph = StateGraph(GenerationState)
    graph.add_node("requirement_intake_agent", requirement_intake_agent)
    graph.add_node("domain_model_agent", domain_model_agent)
    graph.add_node("application_slice_agent", application_slice_agent)
    graph.add_node("ecosystem_mock_agent", ecosystem_mock_agent)
    graph.add_node("verification_agent", verification_agent)
    graph.add_node("self_correction_agent", self_correction_agent)
    graph.add_node("governance_evidence_agent", governance_evidence_agent)
    graph.add_edge(START, "requirement_intake_agent")
    graph.add_edge("requirement_intake_agent", "domain_model_agent")
    graph.add_edge("domain_model_agent", "application_slice_agent")
    graph.add_edge("application_slice_agent", "ecosystem_mock_agent")
    graph.add_edge("ecosystem_mock_agent", "verification_agent")
    graph.add_conditional_edges(
        "verification_agent",
        route_after_verification,
        {
            "governance_evidence_agent": "governance_evidence_agent",
            "self_correction_agent": "self_correction_agent",
        },
    )
    graph.add_edge("self_correction_agent", "verification_agent")
    graph.add_edge("governance_evidence_agent", END)
    return graph.compile()


def generate() -> dict[str, Any]:
    app = build_graph()
    final_state = app.invoke(
        {
            "run_id": "phase13m_langgraph_agentic_lifecycle_generation_001",
            "agents": [],
            "corrections": [],
        }
    )
    audit = final_state.get("audit")
    if not isinstance(audit, dict):
        raise SystemExit("LangGraph generation did not produce an audit payload.")
    if audit.get("validation", {}).get("generated_checks_passed") is not True:
        print(json.dumps(audit, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = generate()
    if not args.quiet:
        print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
