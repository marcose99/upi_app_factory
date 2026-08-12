from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.services import FailedDebitRuntimeService
from generated_application.app.domain.exceptions import ValidationFailed
from generated_application.app.interfaces.api import main as api_main
from generated_application.app.security.identity import issue_local_test_token


MUTATION_MODELS = (
    "AttachFailedDebitEvidenceRequest",
    "RecordFailedDebitInvestigationRequest",
    "ClassifyFailedDebitCaseRequest",
    "RequestFailedDebitHumanReviewRequest",
    "RecordFailedDebitReviewDecisionRequest",
    "RecordFailedDebitDispositionRequest",
    "CloseFailedDebitCaseRequest",
    "QuarantineFailedDebitCaseRequest",
)


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    database = tmp_path / "fpq-r1-api.sqlite3"
    monkeypatch.setattr(api_main, "DATABASE_PATH", database)
    api_main.app.state.database_path = database
    return api_main.app


async def _async_request(
    api: Any,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
) -> Response:
    transport = ASGITransport(app=api, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://fpq-r1") as client:
        return await client.request(method, path, headers=headers, json=json)


def _request(
    api: Any,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
) -> Response:
    return asyncio.run(_async_request(api, method, path, headers=headers, json=json))


def _authorization(subject: str, roles: list[str], scopes: list[str]) -> str:
    token = issue_local_test_token(subject=subject, roles=roles, scopes=scopes)
    return f"Bearer {token}"


def _create_case(api: Any, *, suffix: str = "001") -> dict[str, Any]:
    response = _request(
        api,
        "POST",
        "/v1/disputes",
        headers={
            "Authorization": _authorization(
                "payer-fpq-r1",
                ["payer"],
                ["dispute:create", "dispute:read"],
            ),
            "Idempotency-Key": f"fpq-r1-create-{suffix}",
            "X-Correlation-Id": f"fpq-r1-create-{suffix}",
        },
        json={
            "transaction_ref": f"TXNFPQR1{suffix}00000",
            "customer_upi": "payer@example",
            "amount": "10.00",
            "reason_code": "FAILED_DEBIT",
        },
    )
    assert response.status_code == 201
    return dict(response.json())


def test_missing_and_stale_expected_version_are_structured_and_do_not_advance(
    api: Any,
) -> None:
    created = _create_case(api)
    dispute_id = str(created["dispute_id"])
    original_version = int(created["version"])
    agent_headers = {
        "Authorization": _authorization(
            "agent-fpq-r1",
            ["customer_support_agent"],
            ["dispute:evidence:write", "dispute:read"],
        ),
        "X-Correlation-Id": "fpq-r1-evidence",
    }
    payload = {
        "evidence_type": "switch_failure",
        "source": "mock_switch",
        "summary": "version guard regression",
        "observed_at_utc": "2026-08-10T00:00:00Z",
    }

    missing = _request(
        api,
        "POST",
        f"/v1/disputes/{dispute_id}/evidence",
        headers={**agent_headers, "Idempotency-Key": "fpq-r1-missing"},
        json=payload,
    )
    assert 400 <= missing.status_code < 500
    assert isinstance(missing.json(), (dict, list))

    valid = _request(
        api,
        "POST",
        f"/v1/disputes/{dispute_id}/evidence",
        headers={**agent_headers, "Idempotency-Key": "fpq-r1-valid"},
        json={**payload, "expected_version": original_version},
    )
    assert valid.status_code == 200
    assert valid.json()["version"] == original_version + 1

    stale = _request(
        api,
        "POST",
        f"/v1/disputes/{dispute_id}/evidence",
        headers={**agent_headers, "Idempotency-Key": "fpq-r1-stale"},
        json={**payload, "expected_version": original_version},
    )
    assert stale.status_code == 409
    assert isinstance(stale.json(), dict)
    current = FailedDebitRuntimeService(
        api_main.SqliteUnitOfWork(api_main.DATABASE_PATH)
    ).get_case(dispute_id)
    assert current is not None
    assert current["version"] == original_version + 1


@pytest.mark.parametrize(
    "amount",
    [
        "not-a-decimal",
        "9" * 4096 + ".00",
        "1e2",
        "NaN",
        "Infinity",
        "-Infinity",
        "1.234",
        "0.00",
        "-1.00",
    ],
)
def test_pathological_amounts_return_structured_4xx(api: Any, amount: str) -> None:
    response = _request(
        api,
        "POST",
        "/v1/disputes",
        headers={
            "Authorization": _authorization(
                "payer-invalid",
                ["payer"],
                ["dispute:create"],
            ),
            "Idempotency-Key": f"fpq-r1-invalid-{len(amount)}-{amount[:3]}",
        },
        json={
            "transaction_ref": "TXNFPQR1INVALID",
            "customer_upi": "payer@example",
            "amount": amount,
            "reason_code": "FAILED_DEBIT",
        },
    )
    assert 400 <= response.status_code < 500
    assert isinstance(response.json(), (dict, list))
    with pytest.raises(ValidationFailed):
        FailedDebitRuntimeService._parse_amount_minor(amount)


def test_openapi_requires_positive_expected_version_on_all_mutations(
    api: Any,
) -> None:
    schemas = _request(api, "GET", "/openapi.json").json()["components"]["schemas"]
    for model_name in MUTATION_MODELS:
        schema = schemas[model_name]
        assert "expected_version" in schema["required"]
        assert schema["properties"]["expected_version"]["minimum"] == 1
