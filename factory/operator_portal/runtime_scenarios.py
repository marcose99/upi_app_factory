from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
import sys
import threading
import time
from typing import Any, Final, cast
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from factory.operator_portal.runtime_contracts import (
    RuntimeContractError,
    RuntimeState,
    sha256_bytes,
    utc_now,
)
from factory.operator_portal.runtime_network_policy import (
    CONCURRENCY_LIMIT,
    MAX_PAYLOAD_BYTES,
    MAX_RESPONSE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    normalize_runtime_url,
    validate_redirect_location,
)
from factory.operator_portal.runtime_store import RuntimeStore, redact
from factory.operator_portal.runtime_supervisor import RuntimeSupervisor


@dataclass(frozen=True)
class RuntimeStep:
    step_id: str
    method: str
    endpoint: str
    payload: dict[str, Any] | None
    expected_status: int
    expected_json: dict[str, Any]
    principal_subject: str = "phase50-scenario-runner"
    principal_scopes: tuple[str, ...] = ()
    principal_roles: tuple[str, ...] = ()
    idempotency_key: str | None = None
    correlation_id: str = "phase50-runtime-scenario"
    capture: dict[str, str] | None = None


@dataclass(frozen=True)
class RuntimeScenario:
    scenario_id: str
    category: str
    method: str
    endpoint: str
    payload: dict[str, Any] | None
    expected_status: int
    expected_json: dict[str, Any]
    steps: tuple[RuntimeStep, ...] = ()


SCENARIO_CATALOG_VERSION: Final[str] = "2.0.0"


def scenario_catalog() -> dict[str, Any]:
    scenarios = [
        RuntimeScenario(
            "positive_create_dispute",
            "positive",
            "POST",
            "/disputes",
            _dispute_payload("PHASE50POSITIVE001", reason="Local mock-safe Phase 50 dispute."),
            201,
            {"certification_boundary": "certification_ready_not_certified"},
        ),
        RuntimeScenario(
            "negative_invalid_request",
            "negative",
            "POST",
            "/disputes",
            {"transaction_ref": "bad"},
            422,
            {"code": "RequestValidationError"},
        ),
        RuntimeScenario(
            "boundary_long_reason",
            "boundary",
            "POST",
            "/disputes",
            _dispute_payload(
                "PHASE50BOUNDARY001",
                reason="Local boundary scenario with a detailed but synthetic reviewer narrative.",
            ),
            201,
            {"certification_boundary": "certification_ready_not_certified"},
        ),
        RuntimeScenario(
            "idempotency_replay",
            "idempotency",
            "POST",
            "/disputes",
            _dispute_payload("PHASE50REPLAY001", reason="Local replay scenario."),
            201,
            {"certification_boundary": "certification_ready_not_certified", "replay_status": 201},
        ),
        RuntimeScenario(
            "resilience_missing_dispute",
            "resilience",
            "GET",
            "/disputes/DSP_MISSING",
            None,
            404,
            {"code": "HTTPException"},
        ),
        RuntimeScenario(
            "security_strict_extra_rejection",
            "security",
            "POST",
            "/disputes",
            {
                **_dispute_payload("PHASE50SECURITY001", reason="Strict input boundary scenario."),
                "unexpected_secret": "synthetic-only",
            },
            422,
            {"code": "RequestValidationError"},
        ),
        RuntimeScenario(
            "authoritative_failed_debit_lifecycle",
            "positive",
            "POST",
            "/v1/disputes",
            {
                "transaction_ref": "TXN-PORTAL-LIFECYCLE-001",
                "customer_upi": "portal.synthetic@upi",
                "amount": "1250.00",
                "reason_code": "beneficiary_not_credited",
            },
            201,
            {"state": "validated"},
            steps=(
                RuntimeStep(
                    "create_case",
                    "POST",
                    "/v1/disputes",
                    {
                        "transaction_ref": "TXN-PORTAL-LIFECYCLE-001",
                        "customer_upi": "portal.synthetic@upi",
                        "amount": "1250.00",
                        "reason_code": "beneficiary_not_credited",
                    },
                    201,
                    {"state": "validated", "version": 1},
                    principal_subject="support-operator",
                    principal_scopes=("dispute:create", "dispute:read"),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-failed-debit-create",
                    correlation_id="phase50-failed-debit-create",
                    capture={"dispute_id": "dispute_id", "case_version": "version"},
                ),
                RuntimeStep(
                    "attach_switch_evidence",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-PHASE50-SWITCH",
                        "evidence_type": "switch_failure",
                        "source": "synthetic_switch_log",
                        "summary": "Deterministic switch timeout without beneficiary credit.",
                        "observed_at_utc": "2026-07-31T04:15:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_evidence", "version": 2},
                    principal_subject="support-operator",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-failed-debit-evidence-1",
                    correlation_id="phase50-failed-debit-evidence-1",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "attach_ledger_evidence",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-PHASE50-LEDGER",
                        "evidence_type": "core_ledger",
                        "source": "synthetic_core_ledger",
                        "summary": "Local ledger confirms debit without credit.",
                        "observed_at_utc": "2026-07-31T04:16:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_evidence", "version": 3},
                    principal_subject="support-operator",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-failed-debit-evidence-2",
                    correlation_id="phase50-failed-debit-evidence-2",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "attach_statement_evidence",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-PHASE50-STATEMENT",
                        "evidence_type": "customer_statement",
                        "source": "synthetic_statement",
                        "summary": "Customer statement still shows missing beneficiary credit.",
                        "observed_at_utc": "2026-07-31T04:17:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "validated", "version": 4},
                    principal_subject="support-operator",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-failed-debit-evidence-3",
                    correlation_id="phase50-failed-debit-evidence-3",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "investigate",
                    "POST",
                    "/v1/disputes/{dispute_id}/investigate",
                    {
                        "analyst_notes": "Local simulated bank adapter confirms beneficiary missing credit.",
                        "simulated_bank_status": "beneficiary_not_credited",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "investigating", "version": 5},
                    principal_subject="analyst-operator",
                    principal_scopes=("dispute:investigation:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-failed-debit-investigate",
                    correlation_id="phase50-failed-debit-investigate",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "classify",
                    "POST",
                    "/v1/disputes/{dispute_id}/classify",
                    {"expected_version": "{case_version}"},
                    200,
                    {
                        "classification.classification": "FAILED",
                        "human_review_required": True,
                        "human_review_status": "PENDING",
                        "proposed_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
                        "version": 6,
                    },
                    principal_subject="analyst-operator",
                    principal_scopes=("dispute:classify:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-failed-debit-classify",
                    correlation_id="phase50-failed-debit-classify",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "request_review",
                    "POST",
                    "/v1/disputes/{dispute_id}/human-review",
                    {
                        "reason_code": "HIGH_IMPACT_CASE",
                        "rationale": "Configured high-value threshold requires governed supervisor review.",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_human_review", "version": 7},
                    principal_subject="analyst-operator",
                    principal_scopes=("dispute:review:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-failed-debit-review-request",
                    correlation_id="phase50-failed-debit-review-request",
                    capture={"case_version": "version", "review_id": "pending_review_id"},
                ),
                RuntimeStep(
                    "record_review_decision",
                    "POST",
                    "/v1/disputes/{dispute_id}/review-decisions",
                    {
                        "decision": "APPROVED",
                        "reason_code": "SUPERVISOR_APPROVED",
                        "rationale": "Supervisor confirms the governed failed-debit disposition.",
                        "review_id": "{review_id}",
                        "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "decision_recorded", "human_review_status": "APPROVED", "version": 8},
                    principal_subject="supervisor-operator",
                    principal_scopes=("dispute:review:write",),
                    principal_roles=("supervisor_approver",),
                    idempotency_key="phase50-failed-debit-review-decision",
                    correlation_id="phase50-failed-debit-review-decision",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "record_disposition",
                    "POST",
                    "/v1/disputes/{dispute_id}/disposition",
                    {
                        "disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
                        "reason_code": "FAILED_DEBIT_CONFIRMED",
                        "rationale": "Governed local conclusion recorded without executing a payment action.",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "resolved", "resolution_status": "resolved", "version": 9},
                    principal_subject="supervisor-operator",
                    principal_scopes=("dispute:disposition:write",),
                    principal_roles=("supervisor_approver",),
                    idempotency_key="phase50-failed-debit-disposition",
                    correlation_id="phase50-failed-debit-disposition",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "verify_audit_integrity",
                    "GET",
                    "/v1/disputes/{dispute_id}/audit-integrity",
                    None,
                    200,
                    {"passed": True, "verification_status": "passed", "state": "resolved", "version": 10},
                    principal_subject="audit-reviewer",
                    principal_scopes=("dispute:audit:read",),
                    principal_roles=("audit_reviewer",),
                    correlation_id="phase50-failed-debit-audit",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "close_case",
                    "POST",
                    "/v1/disputes/{dispute_id}/close",
                    {
                        "reason_code": "CASE_COMPLETE",
                        "rationale": "Supervisor authorizes closure after successful audit verification.",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "closed", "resolution_status": "closed", "version": 11},
                    principal_subject="supervisor-operator",
                    principal_scopes=("dispute:close:write",),
                    principal_roles=("supervisor_approver",),
                    idempotency_key="phase50-failed-debit-close",
                    correlation_id="phase50-failed-debit-close",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "history",
                    "GET",
                    "/v1/disputes/{dispute_id}/history",
                    None,
                    200,
                    {"state": "closed"},
                    principal_subject="audit-reviewer",
                    principal_scopes=("dispute:history:read",),
                    principal_roles=("audit_reviewer",),
                ),
            ),
        ),
        RuntimeScenario(
            "negative_same_actor_review_rejected",
            "negative",
            "POST",
            "/v1/disputes",
            {
                "transaction_ref": "TXN-PORTAL-LIFECYCLE-002",
                "customer_upi": "portal.synthetic@upi",
                "amount": "1250.00",
                "reason_code": "beneficiary_not_credited",
            },
            201,
            {"state": "validated"},
            steps=(
                RuntimeStep(
                    "create_case",
                    "POST",
                    "/v1/disputes",
                    {
                        "transaction_ref": "TXN-PORTAL-LIFECYCLE-002",
                        "customer_upi": "portal.synthetic@upi",
                        "amount": "1250.00",
                        "reason_code": "beneficiary_not_credited",
                    },
                    201,
                    {"state": "validated"},
                    principal_subject="support-negative",
                    principal_scopes=("dispute:create",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-negative-create",
                    capture={"dispute_id": "dispute_id", "case_version": "version"},
                ),
                RuntimeStep(
                    "attach_evidence_1",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-NEG-1",
                        "evidence_type": "switch_failure",
                        "source": "synthetic_switch_log",
                        "summary": "Synthetic evidence 1.",
                        "observed_at_utc": "2026-07-31T04:30:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_evidence"},
                    principal_subject="support-negative",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-negative-evidence-1",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "attach_evidence_2",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-NEG-2",
                        "evidence_type": "core_ledger",
                        "source": "synthetic_core_ledger",
                        "summary": "Synthetic evidence 2.",
                        "observed_at_utc": "2026-07-31T04:31:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_evidence"},
                    principal_subject="support-negative",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-negative-evidence-2",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "attach_evidence_3",
                    "POST",
                    "/v1/disputes/{dispute_id}/evidence",
                    {
                        "evidence_id": "EVD-NEG-3",
                        "evidence_type": "customer_statement",
                        "source": "synthetic_statement",
                        "summary": "Synthetic evidence 3.",
                        "observed_at_utc": "2026-07-31T04:32:00Z",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "validated"},
                    principal_subject="support-negative",
                    principal_scopes=("dispute:evidence:write",),
                    principal_roles=("customer_support_agent",),
                    idempotency_key="phase50-negative-evidence-3",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "investigate",
                    "POST",
                    "/v1/disputes/{dispute_id}/investigate",
                    {
                        "analyst_notes": "Analyst investigates the case.",
                        "simulated_bank_status": "beneficiary_not_credited",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "investigating"},
                    principal_subject="analyst-negative",
                    principal_scopes=("dispute:investigation:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-negative-investigate",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "classify",
                    "POST",
                    "/v1/disputes/{dispute_id}/classify",
                    {"expected_version": "{case_version}"},
                    200,
                    {"human_review_required": True},
                    principal_subject="analyst-negative",
                    principal_scopes=("dispute:classify:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-negative-classify",
                    capture={"case_version": "version"},
                ),
                RuntimeStep(
                    "request_review",
                    "POST",
                    "/v1/disputes/{dispute_id}/human-review",
                    {
                        "reason_code": "HIGH_IMPACT_CASE",
                        "rationale": "Case requires explicit review.",
                        "expected_version": "{case_version}",
                    },
                    200,
                    {"state": "awaiting_human_review"},
                    principal_subject="analyst-negative",
                    principal_scopes=("dispute:review:write",),
                    principal_roles=("dispute_operations_analyst",),
                    idempotency_key="phase50-negative-review-request",
                    capture={"case_version": "version", "review_id": "pending_review_id"},
                ),
                RuntimeStep(
                    "same_actor_approval",
                    "POST",
                    "/v1/disputes/{dispute_id}/review-decisions",
                    {
                        "decision": "APPROVED",
                        "reason_code": "INVALID_SELF_APPROVAL",
                        "rationale": "This must be rejected by segregation-of-duties controls.",
                        "review_id": "{review_id}",
                        "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
                        "expected_version": "{case_version}",
                    },
                    400,
                    {"code": "ValidationFailed"},
                    principal_subject="analyst-negative",
                    principal_scopes=("dispute:review:write",),
                    principal_roles=("supervisor_approver",),
                    idempotency_key="phase50-negative-review-decision",
                ),
            ),
        ),
        RuntimeScenario(
            "timeout_budget_health",
            "timeout",
            "GET",
            "/health",
            None,
            200,
            {"status": "ok"},
        ),
    ]
    return {
        "schema_version": "1.0",
        "version": SCENARIO_CATALOG_VERSION,
        "categories": sorted({scenario.category for scenario in scenarios}),
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "category": scenario.category,
                "method": scenario.method,
                "endpoint": scenario.endpoint,
                "payload": scenario.payload,
                "expected": {
                    "status": scenario.expected_status,
                    "json": scenario.expected_json,
                },
                "steps": [
                    {
                        "id": step.step_id,
                        "method": step.method,
                        "endpoint": step.endpoint,
                        "payload": step.payload,
                        "expected": {
                            "status": step.expected_status,
                            "json": step.expected_json,
                        },
                        "principal_subject": step.principal_subject,
                        "principal_scopes": list(step.principal_scopes),
                        "principal_roles": list(step.principal_roles),
                        "idempotency_key": step.idempotency_key,
                        "correlation_id": step.correlation_id,
                        "capture": step.capture or {},
                    }
                    for step in scenario.steps
                ],
            }
            for scenario in scenarios
        ],
    }


class ScenarioRunner:
    def __init__(self, *, store: RuntimeStore) -> None:
        self.store = store
        self._semaphore = threading.BoundedSemaphore(CONCURRENCY_LIMIT)

    def run_all(self, *, run_id: str, base_url: str, owned_port: int) -> dict[str, Any]:
        supervisor = RuntimeSupervisor(project_root=self.store.project_root, store=self.store)
        status = supervisor.status(run_id=run_id, port=owned_port)
        if status.state not in {RuntimeState.READY, RuntimeState.DEGRADED}:
            raise RuntimeContractError("runtime identity is not verified for scenario attribution")
        runtime_identity = supervisor._runtime_identity_payload(run_id)
        results = [
            self.run_one(run_id=run_id, base_url=base_url, owned_port=owned_port, scenario=item)
            for item in scenario_catalog()["scenarios"]
        ]
        passed = all(result["passed"] for result in results)
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "catalog_version": SCENARIO_CATALOG_VERSION,
            "runtime_identity": runtime_identity,
            "started_at_utc": results[0]["started_at_utc"] if results else utc_now(),
            "completed_at_utc": utc_now(),
            "passed": passed,
            "decision": "GO" if passed else "NO_GO",
            "results": results,
        }
        self.store.atomic_write_json(self.store.scenario_path(run_id), payload)
        self.store.append_event(
            run_id,
            "runtime_scenarios_completed",
            {"passed": passed, "result_count": len(results)},
        )
        return payload

    def run_one(self, *, run_id: str, base_url: str, owned_port: int, scenario: dict[str, Any]) -> dict[str, Any]:
        if not self._semaphore.acquire(blocking=False):
            raise RuntimeContractError("scenario concurrency budget exceeded")
        started = time.monotonic()
        started_at = utc_now()
        try:
            steps = cast(list[dict[str, Any]], scenario.get("steps") or [])
            if steps:
                step_results = self._run_steps(
                    base_url=base_url,
                    owned_port=owned_port,
                    steps=steps,
                )
                passed = all(bool(step["passed"]) for step in step_results)
                material = {
                    "scenario_id": scenario["id"],
                    "steps": step_results,
                }
                result = {
                    "scenario_id": scenario["id"],
                    "category": scenario["category"],
                    "started_at_utc": started_at,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "passed": passed,
                    "request_sha256": sha256_bytes(json.dumps({"steps": [step["request"] for step in step_results]}, sort_keys=True).encode("utf-8")),
                    "response_sha256": sha256_bytes(json.dumps({"steps": [step["response"] for step in step_results]}, sort_keys=True).encode("utf-8")),
                    "result_sha256": sha256_bytes(json.dumps(material, sort_keys=True).encode("utf-8")),
                    "assertions": [{"name": "all_steps_passed", "passed": passed, "expected": True, "actual": passed}],
                    "steps": step_results,
                }
            else:
                method = str(scenario["method"])
                endpoint = str(scenario["endpoint"])
                payload = cast(dict[str, Any] | None, scenario.get("payload"))
                expected = cast(dict[str, Any], scenario["expected"])
                response = self._request(
                    base_url=base_url,
                    owned_port=owned_port,
                    method=method,
                    endpoint=endpoint,
                    payload=payload,
                    subject="phase50-scenario-runner",
                    scopes=("dispute:create", "dispute:read", "dispute:read:any"),
                    roles=(),
                    idempotency_key=_idempotency_key(payload),
                    correlation_id="phase50-generic-scenario",
                )
                replay_response: dict[str, Any] | None = None
                expected_json = cast(dict[str, Any], expected.get("json", {}))
                if "replay_status" in expected_json:
                    replay_response = self._request(
                        base_url=base_url,
                        owned_port=owned_port,
                        method=method,
                        endpoint=endpoint,
                        payload=payload,
                        subject="phase50-scenario-runner",
                        scopes=("dispute:create", "dispute:read", "dispute:read:any"),
                        roles=(),
                        idempotency_key=_idempotency_key(payload),
                        correlation_id="phase50-generic-scenario",
                    )
                assertions = self._assertions(
                    response=response,
                    expected_status=int(expected["status"]),
                    expected_json=expected_json,
                    replay_response=replay_response,
                )
                passed = all(item["passed"] for item in assertions)
                material = {
                    "scenario_id": scenario["id"],
                    "request": {"method": method, "endpoint": endpoint, "payload": redact(payload or {})},
                    "response": redact(response),
                    "assertions": assertions,
                }
                result = {
                    "scenario_id": scenario["id"],
                    "category": scenario["category"],
                    "started_at_utc": started_at,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "passed": passed,
                    "request_sha256": sha256_bytes(json.dumps(material["request"], sort_keys=True).encode("utf-8")),
                    "response_sha256": sha256_bytes(json.dumps(material["response"], sort_keys=True).encode("utf-8")),
                    "result_sha256": sha256_bytes(json.dumps(material, sort_keys=True).encode("utf-8")),
                    "assertions": assertions,
                }
            self.store.append_event(run_id, "runtime_scenario_executed", result)
            return result
        finally:
            self._semaphore.release()

    def _run_steps(
        self,
        *,
        base_url: str,
        owned_port: int,
        steps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        context: dict[str, Any] = {}
        results: list[dict[str, Any]] = []
        for step in steps:
            rendered_endpoint = cast(str, _render(step["endpoint"], context))
            rendered_payload = cast(dict[str, Any] | None, _render(step.get("payload"), context))
            expected = cast(dict[str, Any], step["expected"])
            response = self._request(
                base_url=base_url,
                owned_port=owned_port,
                method=str(step["method"]),
                endpoint=rendered_endpoint,
                payload=rendered_payload,
                subject=str(step["principal_subject"]),
                scopes=tuple(str(item) for item in step.get("principal_scopes", [])),
                roles=tuple(str(item) for item in step.get("principal_roles", [])),
                idempotency_key=None if step.get("idempotency_key") is None else cast(str, _render(step["idempotency_key"], context)),
                correlation_id=cast(str, _render(step.get("correlation_id", "phase50-runtime-scenario"), context)),
            )
            assertions = self._assertions(
                response=response,
                expected_status=int(expected["status"]),
                expected_json=cast(dict[str, Any], expected.get("json", {})),
                replay_response=None,
            )
            step_result = {
                "step_id": step["id"],
                "request": {
                    "method": step["method"],
                    "endpoint": rendered_endpoint,
                    "payload": redact(rendered_payload or {}),
                },
                "response": redact(response),
                "assertions": assertions,
                "passed": all(bool(item["passed"]) for item in assertions),
            }
            results.append(step_result)
            for key, dotted in cast(dict[str, str], step.get("capture", {})).items():
                context[key] = _select(response["json"], dotted)
        return results

    def _request(
        self,
        *,
        base_url: str,
        owned_port: int,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None,
        subject: str,
        scopes: tuple[str, ...],
        roles: tuple[str, ...],
        idempotency_key: str | None,
        correlation_id: str,
    ) -> dict[str, Any]:
        normalized = normalize_runtime_url(
            base_url=base_url,
            method=method,
            endpoint=endpoint,
            owned_port=owned_port,
        )
        body = None
        headers = {"Accept": "application/json"}
        if endpoint.startswith("/disputes") or endpoint.startswith("/v1/disputes"):
            headers["Authorization"] = f"Bearer {self._local_runtime_token(subject=subject, scopes=scopes, roles=roles)}"
            headers["X-Correlation-Id"] = correlation_id
            if method.upper() == "POST":
                headers["Idempotency-Key"] = idempotency_key or "phase50-default-idempotency"
        if payload is not None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            if len(body) > MAX_PAYLOAD_BYTES:
                raise RuntimeContractError("scenario payload exceeded request budget")
            headers["Content-Type"] = "application/json"
        req = urllib_request.Request(normalized.url, data=body, headers=headers, method=normalized.method)
        opener = urllib_request.build_opener(NoRedirectHandler)
        try:
            with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                if 300 <= response.status < 400:
                    validate_redirect_location(
                        base_url=base_url,
                        location=response.headers.get("Location", ""),
                        owned_port=owned_port,
                    )
                    raise RuntimeContractError("redirects are blocked for scenario execution")
                data = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except HTTPError as exc:
            data = exc.read(MAX_RESPONSE_BYTES + 1)
            status = exc.code
        except (URLError, TimeoutError) as exc:
            raise RuntimeContractError(f"scenario request failed: {exc}") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise RuntimeContractError("scenario response exceeded response budget")
        try:
            json_payload: Any = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            json_payload = {"raw": data.decode("utf-8", errors="replace")}
        return {"status": status, "json": json_payload}

    def _local_runtime_token(
        self,
        *,
        subject: str,
        scopes: tuple[str, ...],
        roles: tuple[str, ...],
    ) -> str:
        generated_parent = self.store.project_root / "workspace/factory_generated/upi_dispute_resolution"
        generated_parent_text = generated_parent.as_posix()
        if generated_parent_text not in sys.path:
            sys.path.insert(0, generated_parent_text)
        try:
            identity = importlib.import_module("generated_application.app.security.identity")
            token = identity.issue_local_test_token(
                subject=subject,
                scopes=scopes,
                roles=roles,
            )
        except (AttributeError, ImportError) as exc:
            raise RuntimeContractError("local generated identity helper unavailable") from exc
        return str(token)

    def _assertions(
        self,
        *,
        response: dict[str, Any],
        expected_status: int,
        expected_json: dict[str, Any],
        replay_response: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        assertions = [
            {
                "name": "status",
                "passed": response["status"] == expected_status,
                "expected": expected_status,
                "actual": response["status"],
            }
        ]
        for dotted, expected_value in expected_json.items():
            if dotted == "replay_status":
                actual = replay_response["status"] if replay_response else None
            else:
                actual = _select(response["json"], dotted)
            assertions.append(
                {
                    "name": dotted,
                    "passed": actual == expected_value,
                    "expected": expected_value,
                    "actual": actual,
                }
            )
        return assertions


class NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _select(payload: Any, dotted: str) -> Any:
    current = payload
    for part in dotted.split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}") and value.count("{") == 1 and value.count("}") == 1:
            return context.get(value[1:-1])
        rendered = value
        for key, context_value in context.items():
            rendered = rendered.replace("{" + key + "}", str(context_value))
        return rendered
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def _idempotency_key(payload: dict[str, Any] | None) -> str:
    if isinstance(payload, dict):
        transaction_ref = str(payload.get("transaction_ref", "")).strip()
        if transaction_ref:
            return f"phase50-{transaction_ref.lower()}"
    return "phase50-read-only"


def _dispute_payload(transaction_ref: str, *, reason: str) -> dict[str, Any]:
    return {
        "transaction_ref": transaction_ref,
        "customer_upi": "phase50@upi",
        "reason": reason,
    }
