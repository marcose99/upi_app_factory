from pathlib import Path

from fastapi.testclient import TestClient

from upi_dispute_app.audit import AuditLogger
from upi_dispute_app.main import create_app
from upi_dispute_app.repository import DisputeRepository


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        repository=DisputeRepository(),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
    )
    return TestClient(app)


def valid_payload() -> dict[str, object]:
    return {
        "client_request_id": "client-req-001",
        "dispute_type": "duplicate_debit",
        "transaction_reference": "TXN-12345",
        "customer_upi_id": "customername@upi",
        "amount_paise": 50000,
        "description": (
            "Customer reports duplicate debit for a local simulated transaction."
        ),
        "evidence": {
            "customer_statement": "Duplicate debit visible in app screenshot."
        },
    }


def test_health(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_dispute_masks_upi_id(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/disputes", json=valid_payload())
    assert response.status_code == 201, response.json()
    body = response.json()
    dispute_id = body["dispute"]["dispute_id"]
    assert body["dispute"]["masked_customer_upi_id"] == "cu***e@upi"
    assert "mock/simulated" in body["boundary_notice"]

    fetched = client.get(f"/disputes/{dispute_id}")
    assert fetched.status_code == 200
    assert fetched.json()["dispute"]["dispute_id"] == dispute_id


def test_duplicate_client_request_is_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    created = client.post("/disputes", json=valid_payload())
    assert created.status_code == 201, created.text

    replayed = client.post("/disputes", json=valid_payload())
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["dispute"]["dispute_id"] == created.json()["dispute"]["dispute_id"]

    conflicting_payload = valid_payload()
    if "description" in conflicting_payload:
        conflicting_payload["description"] = (
            str(conflicting_payload["description"]) + " changed duplicate payload"
        )
    elif "amount" in conflicting_payload:
        conflicting_payload["amount"] = 999999
    elif "complaint_category" in conflicting_payload:
        conflicting_payload["complaint_category"] = "PENDING_TRANSACTION"
    else:
        conflicting_payload["customer_reference"] = "changed-duplicate-payload"

    conflict = client.post("/disputes", json=conflicting_payload)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "payload_conflict"



def test_mock_ecosystem_check_updates_status(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    created = client.post("/disputes", json=valid_payload())
    assert created.status_code == 201, created.json()
    dispute_id = created.json()["dispute"]["dispute_id"]

    checked = client.post(f"/disputes/{dispute_id}/actions/mock-ecosystem-check")
    assert checked.status_code == 200
    body = checked.json()
    assert body["decision"] == "refund_eligible"
    assert body["new_status"] == "refund_initiated"
    assert "mock_psp_adapter" in body["mock_sources_checked"]


def test_obvious_long_numeric_sensitive_description_is_rejected(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path)
    payload = valid_payload()
    payload["client_request_id"] = "client-req-002"
    payload["description"] = (
        "This includes a long number 123456789012 and is rejected."
    )
    response = client.post("/disputes", json=payload)
    assert response.status_code == 422
