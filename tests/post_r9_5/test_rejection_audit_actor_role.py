from __future__ import annotations

import asyncio
import hashlib
import json
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
    database = tmp_path / "rejection_audit.sqlite3"
    monkeypatch.setattr(main, "DATABASE_PATH", database)
    monkeypatch.setattr(main, "RUNTIME", RuntimeLifecycle(database))
    main.app.state.database_path = database
    return main.app, database


def token(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> str:
    return cast(str, issue_local_test_token(subject=subject, scopes=scopes, roles=roles))


def auth(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> dict[str, str]:
    return {"Authorization": "Bearer " + token(subject, scopes, roles)}


def create_case(app: Any, headers: dict[str, str]) -> httpx.Response:
    return request(
        app,
        "POST",
        "/v1/disputes",
        payload={
            "transaction_ref": "TXN-R9-AUDIT-001",
            "customer_upi": "payer.synthetic@upi",
            "amount": "1250.00",
            "reason_code": "beneficiary_not_credited",
        },
        headers={
            **headers,
            "Idempotency-Key": "idem-r9-audit-create",
            "X-Correlation-Id": "corr-r9-audit-create",
        },
    )


def attach_all_required_evidence(app: Any, dispute_id: str, version: int, headers: dict[str, str]) -> int:
    evidence = [
        ("switch_failure", "EVD-AUDIT-SWITCH", "2026-07-31T04:15:00Z"),
        ("core_ledger", "EVD-AUDIT-LEDGER", "2026-07-31T04:16:00Z"),
        ("customer_statement", "EVD-AUDIT-STATEMENT", "2026-07-31T04:17:00Z"),
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
                "summary": f"Synthetic {evidence_type} evidence for audit rejection coverage.",
                "observed_at_utc": observed_at_utc,
                "expected_version": current,
            },
            headers={
                **headers,
                "Idempotency-Key": f"idem-r9-audit-evidence-{index}",
                "X-Correlation-Id": f"corr-r9-audit-evidence-{index}",
            },
        )
        assert response.status_code == 200, response.text
        current = int(response.json()["version"])
    return current


def _audit_rows(database: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            select occurred_at_utc, actor_id, actor_role, action, target, payload_json, previous_hash, record_hash
            from audit_records
            order by sequence
            """
        ).fetchall()


def test_rejection_audit_chain_records_actor_role_and_redacted_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database = make_client(tmp_path, monkeypatch)
    support_headers = auth(
        "support-1",
        ("dispute:create", "dispute:evidence:write", "dispute:read"),
        ("customer_support_agent",),
    )
    analyst_headers = auth(
        "analyst-1",
        ("dispute:investigation:write", "dispute:classify:write", "dispute:review:write"),
        ("dispute_operations_analyst",),
    )

    created = create_case(app, support_headers)
    assert created.status_code == 201, created.text
    dispute_id = created.json()["dispute_id"]
    version = attach_all_required_evidence(app, dispute_id, int(created.json()["version"]), support_headers)

    version = int(
        request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/investigate",
            payload={
                "analyst_notes": "Investigate before review rejection.",
                "simulated_bank_status": "beneficiary_not_credited",
                "expected_version": version,
            },
            headers={
                **analyst_headers,
                "Idempotency-Key": "idem-r9-audit-investigate",
                "X-Correlation-Id": "corr-r9-audit-investigate",
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
                "Idempotency-Key": "idem-r9-audit-classify",
                "X-Correlation-Id": "corr-r9-audit-classify",
            },
        ).json()["version"]
    )
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
            "Idempotency-Key": "idem-r9-audit-review-request",
            "X-Correlation-Id": "corr-r9-audit-review-request",
        },
    )
    assert review_requested.status_code == 200, review_requested.text
    version = int(review_requested.json()["version"])
    review_id = review_requested.json()["pending_review_id"]

    idempotency_conflict = request(
        app,
        "POST",
        "/v1/disputes",
        payload={
            "transaction_ref": "TXN-R9-AUDIT-001",
            "customer_upi": "payer.synthetic@upi",
            "amount": "1300.00",
            "reason_code": "beneficiary_not_credited",
        },
        headers={
            **support_headers,
            "Idempotency-Key": "idem-r9-audit-create",
            "X-Correlation-Id": "corr-r9-audit-idempotency-conflict",
        },
    )
    assert idempotency_conflict.status_code == 409

    prohibited = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/review-decisions",
        payload={
            "decision": "APPROVED",
            "reason_code": "ROLE_REJECTED",
            "rationale": "Support staff cannot approve review decisions.",
            "review_id": review_id,
            "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "expected_version": version,
        },
        headers={
            **support_headers,
            "Idempotency-Key": "idem-r9-audit-prohibited",
            "X-Correlation-Id": "corr-r9-audit-prohibited",
        },
    )
    assert prohibited.status_code == 403

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
                "analyst-1",
                ("dispute:review:write",),
                ("supervisor_approver",),
            )["Authorization"],
            "Idempotency-Key": "idem-r9-audit-sod",
            "X-Correlation-Id": "corr-r9-audit-sod",
        },
    )
    assert same_actor.status_code == 400

    rows = _audit_rows(database)
    assert rows
    categories = {
        json.loads(str(row["payload_json"]))["category"]
        for row in rows
        if str(row["action"]).startswith("rejection.")
    }
    assert {"idempotency_conflict", "prohibited_action", "segregation_of_duties_failure"}.issubset(
        categories
    )

    latest = rows[-1]
    expected_hash = hashlib.sha256(
        "|".join(
            [
                str(latest["occurred_at_utc"]),
                str(latest["actor_id"]),
                str(latest["actor_role"]),
                str(latest["action"]),
                str(latest["target"]),
                str(latest["payload_json"]),
                str(latest["previous_hash"]),
            ]
        ).encode("utf-8")
    ).hexdigest()
    assert str(latest["record_hash"]) == expected_hash

    rejection_rows = [row for row in rows if str(row["action"]).startswith("rejection.")]
    assert {str(row["actor_role"]) for row in rejection_rows} >= {
        "customer_support_agent",
        "supervisor_approver",
    }
    for row in rejection_rows:
        payload = json.loads(str(row["payload_json"]))
        assert payload["detail_redacted"] is True
        assert payload["reason_sha256"]
        assert "idem-r9-audit" not in str(row["payload_json"])
