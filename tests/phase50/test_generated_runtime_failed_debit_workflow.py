from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any, cast

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_PACKAGE_ROOT = PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution"
if str(GENERATED_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_PACKAGE_ROOT))

from generated_application.app.interfaces.api import main  # noqa: E402
from generated_application.app.runtime import RuntimeLifecycle  # noqa: E402
from generated_application.app.security.identity import issue_local_test_token  # noqa: E402


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://generated-runtime") as client:
        return await client.request(method, path, json=payload, headers=headers)


def request(
    app: Any,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, payload=payload, headers=headers))


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path]:
    database = tmp_path / "failed_debit.sqlite3"
    monkeypatch.setattr(main, "DATABASE_PATH", database)
    monkeypatch.setattr(main, "RUNTIME", RuntimeLifecycle(database))
    return main.app, database


def token(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> str:
    return cast(
        str,
        issue_local_test_token(subject=subject, scopes=scopes, roles=roles),
    )


def auth(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> dict[str, str]:
    return {"Authorization": "Bearer " + token(subject, scopes, roles)}


def create_case(app: Any, headers: dict[str, str]) -> httpx.Response:
    return request(
        app,
        "POST",
        "/v1/disputes",
        payload={
            "transaction_ref": "TXN-R9-LIFECYCLE-001",
            "customer_upi": "payer.synthetic@upi",
            "amount": "1250.00",
            "reason_code": "beneficiary_not_credited",
        },
        headers={
            **headers,
            "Idempotency-Key": "idem-create-r9",
            "X-Correlation-Id": "corr-r9-create",
        },
    )


def attach_all_required_evidence(app: Any, dispute_id: str, version: int, headers: dict[str, str]) -> int:
    evidence = [
        ("switch_failure", "EVD-R9-SWITCH", "2026-07-31T04:15:00Z"),
        ("core_ledger", "EVD-R9-LEDGER", "2026-07-31T04:16:00Z"),
        ("customer_statement", "EVD-R9-STATEMENT", "2026-07-31T04:17:00Z"),
    ]
    current = version
    for index, (evidence_type, evidence_id, observed_at_utc) in enumerate(evidence, start=1):
        response = request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/evidence",
            payload={
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "source": f"synthetic_{evidence_type}",
                "summary": f"Synthetic {evidence_type} evidence for R9 lifecycle coverage.",
                "observed_at_utc": observed_at_utc,
                "expected_version": current,
            },
            headers={
                **headers,
                "Idempotency-Key": f"idem-evidence-r9-{index}",
                "X-Correlation-Id": f"corr-r9-evidence-{index}",
            },
        )
        assert response.status_code == 200, response.text
        current = int(response.json()["version"])
    return current


def test_authoritative_generated_runtime_supports_full_r9_dispute_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _database = make_client(tmp_path, monkeypatch)
    support_headers = auth(
        "support-1",
        ("dispute:create", "dispute:evidence:write", "dispute:read", "dispute:read:any"),
        ("customer_support_agent",),
    )
    analyst_headers = auth(
        "analyst-1",
        (
            "dispute:investigation:write",
            "dispute:classify:write",
            "dispute:review:write",
            "dispute:read",
            "dispute:read:any",
        ),
        ("dispute_operations_analyst",),
    )
    supervisor_headers = auth(
        "supervisor-1",
        ("dispute:review:write", "dispute:disposition:write", "dispute:close:write", "dispute:read"),
        ("supervisor_approver",),
    )
    audit_headers = auth(
        "audit-1",
        ("dispute:history:read", "dispute:audit:read"),
        ("audit_reviewer",),
    )

    created = create_case(app, support_headers)
    assert created.status_code == 201, created.text
    dispute_id = created.json()["dispute_id"]
    version = int(created.json()["version"])
    assert created.json()["state"] == "validated"
    assert created.json()["human_review_status"] == "NOT_REQUIRED"

    version = attach_all_required_evidence(app, dispute_id, version, support_headers)

    investigation = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/investigate",
        payload={
            "analyst_notes": "Deterministic investigation confirms beneficiary missing credit.",
            "simulated_bank_status": "beneficiary_not_credited",
            "expected_version": version,
        },
        headers={
            **analyst_headers,
            "Idempotency-Key": "idem-r9-investigate",
            "X-Correlation-Id": "corr-r9-investigate",
        },
    )
    assert investigation.status_code == 200, investigation.text
    version = int(investigation.json()["version"])
    assert investigation.json()["state"] == "investigating"
    assert investigation.json()["latest_investigation"]["provider_snapshot"]["provider_call_performed"] is False

    classification = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/classify",
        payload={"expected_version": version},
        headers={
            **analyst_headers,
            "Idempotency-Key": "idem-r9-classify",
            "X-Correlation-Id": "corr-r9-classify",
        },
    )
    assert classification.status_code == 200, classification.text
    version = int(classification.json()["version"])
    assert classification.json()["classification"]["classification"] == "FAILED"
    assert classification.json()["classification"]["reason_code"] == "BENEFICIARY_CREDIT_FAILED"
    assert classification.json()["classification"]["impact"] in {"HIGH", "CRITICAL"}
    assert classification.json()["human_review_required"] is True
    assert classification.json()["human_review_status"] == "PENDING"
    assert classification.json()["proposed_disposition"] == "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP"

    review_requested = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/human-review",
        payload={
            "reason_code": "HIGH_IMPACT_CASE",
            "rationale": "Configured threshold requires explicit supervisor review.",
            "expected_version": version,
        },
        headers={
            **analyst_headers,
            "Idempotency-Key": "idem-r9-review-request",
            "X-Correlation-Id": "corr-r9-review-request",
        },
    )
    assert review_requested.status_code == 200, review_requested.text
    version = int(review_requested.json()["version"])
    review_id = review_requested.json()["pending_review_id"]
    assert review_requested.json()["state"] == "awaiting_human_review"
    assert review_requested.json()["human_review_status"] == "PENDING"

    review_decision = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/review-decisions",
        payload={
            "decision": "APPROVED",
            "reason_code": "SUPERVISOR_APPROVED",
            "rationale": "Supervisor approves governed local-only disposition.",
            "review_id": review_id,
            "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "expected_version": version,
        },
        headers={
            **supervisor_headers,
            "Idempotency-Key": "idem-r9-review-decision",
            "X-Correlation-Id": "corr-r9-review-decision",
        },
    )
    assert review_decision.status_code == 200, review_decision.text
    version = int(review_decision.json()["version"])
    assert review_decision.json()["state"] == "decision_recorded"
    assert review_decision.json()["human_review_status"] == "APPROVED"
    assert review_decision.json()["approved_disposition"] == "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP"

    disposition = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/disposition",
        payload={
            "disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "reason_code": "FAILED_DEBIT_CONFIRMED",
            "rationale": "Recorded operational conclusion without payment execution.",
            "expected_version": version,
        },
        headers={
            **supervisor_headers,
            "Idempotency-Key": "idem-r9-disposition",
            "X-Correlation-Id": "corr-r9-disposition",
        },
    )
    assert disposition.status_code == 200, disposition.text
    version = int(disposition.json()["version"])
    assert disposition.json()["state"] == "resolved"
    assert disposition.json()["latest_disposition"]["disposition"] == "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP"

    audit = request(
        app,
        "GET",
        f"/v1/disputes/{dispute_id}/audit-integrity",
        headers={**audit_headers, "X-Correlation-Id": "corr-r9-audit"},
    )
    assert audit.status_code == 200, audit.text
    assert audit.json()["passed"] is True
    assert audit.json()["verification_status"] == "passed"
    version = int(audit.json()["version"])

    closed = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/close",
        payload={
            "reason_code": "CASE_COMPLETE",
            "rationale": "Supervisor authorizes closure after governed checks pass.",
            "expected_version": version,
        },
        headers={
            **supervisor_headers,
            "Idempotency-Key": "idem-r9-close",
            "X-Correlation-Id": "corr-r9-close",
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["state"] == "closed"
    assert closed.json()["resolution_status"] == "closed"
    assert closed.json()["closed_by"] == "supervisor-1"

    history = request(app, "GET", f"/v1/disputes/{dispute_id}/history", headers=audit_headers)
    assert history.status_code == 200, history.text
    event_types = [item["event_type"] for item in history.json()["timeline"]]
    assert "FailedDebitCaseClassified" in event_types
    assert "FailedDebitHumanReviewRequested" in event_types
    assert "FailedDebitReviewDecisionRecorded" in event_types
    assert "FailedDebitDispositionRecorded" in event_types
    assert "FailedDebitAuditIntegrityVerified" in event_types
    assert "FailedDebitCaseClosed" in event_types
    assert [item["decision_status"] for item in history.json()["review_history"]] == ["REQUESTED", "APPROVED"]

    search = request(
        app,
        "GET",
        "/v1/disputes?transaction_reference=TXN-R9-LIFECYCLE-001&human_review_status=APPROVED&classification=FAILED&state=closed",
        headers=auth("search-1", ("dispute:read:any",), ("customer_support_agent",)),
    )
    assert search.status_code == 200, search.text
    assert search.json()["items"][0]["dispute_id"] == dispute_id


def test_fail_closed_enforcement_blocks_same_actor_review_and_close_before_disposition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _database = make_client(tmp_path, monkeypatch)
    support_headers = auth("support-2", ("dispute:create", "dispute:evidence:write"), ("customer_support_agent",))
    analyst_headers = auth(
        "analyst-2",
        ("dispute:investigation:write", "dispute:classify:write", "dispute:review:write"),
        ("dispute_operations_analyst",),
    )
    supervisor_headers = auth(
        "supervisor-2",
        ("dispute:review:write", "dispute:close:write"),
        ("supervisor_approver",),
    )

    created = create_case(app, support_headers)
    dispute_id = created.json()["dispute_id"]
    version = attach_all_required_evidence(app, dispute_id, int(created.json()["version"]), support_headers)

    version = int(
        request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/investigate",
            payload={
                "analyst_notes": "Investigate before classification.",
                "simulated_bank_status": "beneficiary_not_credited",
                "expected_version": version,
            },
            headers={
                **analyst_headers,
                "Idempotency-Key": "idem-neg-investigate",
                "X-Correlation-Id": "corr-neg-investigate",
            },
        ).json()["version"]
    )
    classified = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/classify",
        payload={"expected_version": version},
        headers={
            **analyst_headers,
            "Idempotency-Key": "idem-neg-classify",
            "X-Correlation-Id": "corr-neg-classify",
        },
    )
    version = int(classified.json()["version"])

    close_before_disposition = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/close",
        payload={
            "reason_code": "TOO_EARLY",
            "rationale": "Close must fail before disposition and audit verification.",
            "expected_version": version,
        },
        headers={
            **supervisor_headers,
            "Idempotency-Key": "idem-neg-close-early",
            "X-Correlation-Id": "corr-neg-close-early",
        },
    )
    assert close_before_disposition.status_code == 400
    assert "resolved cases" in close_before_disposition.text

    review_requested = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/human-review",
        payload={
            "reason_code": "HIGH_IMPACT_CASE",
            "rationale": "Review is mandatory before any consequential decision.",
            "expected_version": version,
        },
        headers={
            **analyst_headers,
            "Idempotency-Key": "idem-neg-review-request",
            "X-Correlation-Id": "corr-neg-review-request",
        },
    )
    version = int(review_requested.json()["version"])
    review_id = review_requested.json()["pending_review_id"]

    same_actor = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/review-decisions",
        payload={
            "decision": "APPROVED",
            "reason_code": "SELF_APPROVAL",
            "rationale": "This should be rejected by segregation of duties.",
            "review_id": review_id,
            "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "expected_version": version,
        },
        headers={
            "Authorization": auth(
                "analyst-2",
                ("dispute:review:write",),
                ("supervisor_approver",),
            )["Authorization"],
            "Idempotency-Key": "idem-neg-review-decision",
            "X-Correlation-Id": "corr-neg-review-decision",
        },
    )
    assert same_actor.status_code == 400
    assert "segregation of duties" in same_actor.text


def test_audit_integrity_failure_quarantines_case_and_blocks_normal_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database = make_client(tmp_path, monkeypatch)
    support_headers = auth("support-3", ("dispute:create", "dispute:evidence:write"), ("customer_support_agent",))
    analyst_headers = auth(
        "analyst-3",
        ("dispute:investigation:write", "dispute:classify:write"),
        ("dispute_operations_analyst",),
    )
    audit_headers = auth("audit-3", ("dispute:audit:read",), ("audit_reviewer",))
    supervisor_headers = auth(
        "supervisor-3",
        ("dispute:close:write",),
        ("supervisor_approver",),
    )

    created = create_case(app, support_headers)
    dispute_id = created.json()["dispute_id"]
    version = attach_all_required_evidence(app, dispute_id, int(created.json()["version"]), support_headers)
    version = int(
        request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/investigate",
            payload={
                "analyst_notes": "Investigate before tamper verification.",
                "simulated_bank_status": "beneficiary_not_credited",
                "expected_version": version,
            },
            headers={
                **analyst_headers,
                "Idempotency-Key": "idem-audit-investigate",
                "X-Correlation-Id": "corr-audit-investigate",
            },
        ).json()["version"]
    )
    version = int(
        request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/classify",
            payload={"expected_version": version},
            headers={
                **analyst_headers,
                "Idempotency-Key": "idem-audit-classify",
                "X-Correlation-Id": "corr-audit-classify",
            },
        ).json()["version"]
    )

    with sqlite3.connect(database) as connection:
        connection.execute(
            "update audit_records set payload_json = ? where sequence = 1",
            ('{"tampered":true}',),
        )
        connection.commit()

    audit = request(
        app,
        "GET",
        f"/v1/disputes/{dispute_id}/audit-integrity",
        headers={**audit_headers, "X-Correlation-Id": "corr-audit-verify"},
    )
    assert audit.status_code == 200, audit.text
    assert audit.json()["passed"] is False
    assert audit.json()["quarantine_applied"] is True
    assert audit.json()["state"] == "quarantined"
    version = int(audit.json()["version"])

    closed = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/close",
        payload={
            "reason_code": "SHOULD_FAIL",
            "rationale": "Quarantined case must not close normally.",
            "expected_version": version,
        },
        headers={
            **supervisor_headers,
            "Idempotency-Key": "idem-audit-close",
            "X-Correlation-Id": "corr-audit-close",
        },
    )
    assert closed.status_code == 400
    assert "resolved cases" in closed.text
