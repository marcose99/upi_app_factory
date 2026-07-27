from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from generated_application.app.application.commands import CreateDisputeCommand
from generated_application.app.application.services import DisputeService
from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from generated_application.app.interfaces.api.schemas import CreateDisputeRequest, DisputeItemResponse
from generated_application.app.security.identity import local_principal
from upi_dispute_app.main import create_app


def valid_payload() -> dict[str, str]:
    return {
        "transaction_ref": "TXN-12345",
        "customer_upi": "customername@upi",
        "reason": "duplicate debit for a local simulated transaction",
    }


def test_compatibility_facade_delegates_to_hardened_api(tmp_path: Path) -> None:
    app = create_app(database_path=tmp_path / "legacy_api.sqlite3")
    schema = app.openapi()

    assert "/health" in schema["paths"]
    assert schema["paths"]["/disputes"]["post"]["security"]
    assert "generated_application.app.interfaces.api.main:app" not in schema["info"]["title"]


def test_create_and_get_dispute_masks_upi_id(tmp_path: Path) -> None:
    service = DisputeService(SqliteUnitOfWork(tmp_path / "legacy_api.sqlite3"))
    payload = valid_payload()
    dispute_id = service.create_dispute(
        CreateDisputeCommand(
            transaction_ref=payload["transaction_ref"],
            customer_upi=payload["customer_upi"],
            reason=payload["reason"],
            idempotency_key="idem-legacy-1",
            correlation_id="corr-legacy",
            owner_subject="client-1",
        )
    )

    dispute = service.get_dispute(dispute_id)
    assert dispute is not None
    body = DisputeItemResponse.from_domain(dispute).model_dump()
    assert body["dispute_id"] == dispute_id
    assert body["masked_customer_upi"] == "cu***@upi"
    assert "customer_upi" not in body


def test_duplicate_client_request_replays_same_dispute_id(tmp_path: Path) -> None:
    service = DisputeService(SqliteUnitOfWork(tmp_path / "legacy_api.sqlite3"))
    payload = valid_payload()

    command = CreateDisputeCommand(
        transaction_ref=payload["transaction_ref"],
        customer_upi=payload["customer_upi"],
        reason=payload["reason"],
        idempotency_key="idem-legacy-1",
        correlation_id="corr-legacy",
        owner_subject="client-1",
    )
    created = service.create_dispute(command)
    replayed = service.create_dispute(command)

    assert replayed == created


def test_invalid_payload_and_missing_principal_are_rejected() -> None:
    payload = valid_payload()
    payload["customer_upi"] = ""
    with pytest.raises(ValidationError):
        CreateDisputeRequest.model_validate(payload)
    with pytest.raises(HTTPException) as exc:
        local_principal(authorization=None, subject=None)
    assert exc.value.status_code == 401
