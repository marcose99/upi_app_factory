from __future__ import annotations

import pathlib
import sys

import pytest

GENERATED_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(GENERATED_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_ROOT))

from phase13l_dispute_case_intake_app.api import create_dispute_case, get_dispute_case
from phase13l_dispute_case_intake_app.service import DisputeCaseIntakeService, DisputeValidationError


def valid_payload() -> dict[str, object]:
    return {
        "transaction_id": "TXN-20260706-0001",
        "payer_vpa": "payer@upi",
        "payee_vpa": "merchant@upi",
        "amount_paise": 125000,
        "rail": "UPI",
        "category": "FAILED_TRANSACTION",
        "evidence_refs": ["txn-log:TXN-20260706-0001", "customer-note:case-1"],
    }


def test_create_dispute_case_accepts_valid_upi_intake() -> None:
    created = create_dispute_case(valid_payload())

    assert created["case_id"].startswith("UPI-DISPUTE-")
    assert created["status"] == "INTAKE_ACCEPTED"
    assert created["rail"] == "UPI"
    assert created["mock_ecosystem_reference"].startswith("MOCK-NPCI-REF-")
    assert "simulated mocks only" in created["boundary_statement"]

    loaded = get_dispute_case(str(created["case_id"]))
    assert loaded == created


def test_service_rejects_missing_evidence() -> None:
    payload = valid_payload()
    payload["evidence_refs"] = []

    with pytest.raises(DisputeValidationError, match="evidence"):
        DisputeCaseIntakeService().create_dispute_case(payload)


def test_service_rejects_invalid_vpa() -> None:
    payload = valid_payload()
    payload["payer_vpa"] = "not-a-vpa"

    with pytest.raises(DisputeValidationError, match="VPAs"):
        DisputeCaseIntakeService().create_dispute_case(payload)
