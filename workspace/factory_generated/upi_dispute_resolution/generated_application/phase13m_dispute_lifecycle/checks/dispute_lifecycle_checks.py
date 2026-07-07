from __future__ import annotations

from phase13m_dispute_lifecycle_app.api import create_case, get_case, progress_case_to_resolution
from phase13m_dispute_lifecycle_app.service import DisputeLifecycleError, DisputeLifecycleService


def valid_payload() -> dict[str, object]:
    return {
        "transaction_id": "TXN-20260706-LIFE-001",
        "payer_vpa": "payer@upi",
        "payee_vpa": "merchant@upi",
        "amount_paise": 125000,
        "evidence_refs": ["txn-log:TXN-20260706-LIFE-001", "customer-note:life-1"],
    }


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
