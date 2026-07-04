from fastapi.testclient import TestClient

from app.main import app


def test_mock_failed_transaction_to_dispute_case_flow() -> None:
    client = TestClient(app)

    transactions_response = client.get("/disputes/mock-failed-transactions")
    assert transactions_response.status_code == 200
    transactions = transactions_response.json()
    assert len(transactions) >= 1
    assert "SYNTHETIC_DATA" in transactions[0]["evidence_labels"]

    transaction_id = transactions[0]["transaction_id"]
    create_response = client.post(
        "/disputes/cases/from-failed-transaction",
        json={
            "transaction_id": transaction_id,
            "created_by": "TECHNICAL_REVIEWER",
        },
    )
    assert create_response.status_code == 201
    created_case = create_response.json()
    assert created_case["transaction_id"] == transaction_id
    assert created_case["status"] == "EVIDENCE_PENDING"
    assert "MOCK_BOUNDARY" in created_case["evidence_labels"]
    assert created_case["audit_event_ids"]

    case_id = created_case["case_id"]
    action_response = client.post(
        f"/disputes/cases/{case_id}/actions",
        json={
            "action": "ASSIGN_REVIEWER",
            "reviewer": "GOVERNANCE_REVIEWER",
            "notes": "Synthetic case accepted for mock review.",
        },
    )
    assert action_response.status_code == 200
    updated_case = action_response.json()
    assert updated_case["status"] == "IN_REVIEW"
    assert len(updated_case["audit_event_ids"]) >= 2

    get_response = client.get(f"/disputes/cases/{case_id}")
    assert get_response.status_code == 200
    assert get_response.json()["case_id"] == case_id


def test_unknown_mock_failed_transaction_is_404() -> None:
    client = TestClient(app)
    response = client.post(
        "/disputes/cases/from-failed-transaction",
        json={
            "transaction_id": "SYN-UPI-TXN-DOES-NOT-EXIST",
            "created_by": "TECHNICAL_REVIEWER",
        },
    )
    assert response.status_code == 404
