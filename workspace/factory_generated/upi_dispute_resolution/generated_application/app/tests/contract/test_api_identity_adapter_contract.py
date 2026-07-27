from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import httpx as local_http_client
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class ASGISyncClient:
    def __init__(self, app: Any) -> None:
        self.app = app

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        async def _request() -> Any:
            transport = local_http_client.ASGITransport(app=self.app)
            async with local_http_client.AsyncClient(transport=transport, base_url="http://local") as client:
                return await client.request(method, path, **kwargs)

        import asyncio

        return asyncio.run(_request())

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)


def _token(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...] = ()) -> str:
    from generated_application.app.security.identity import issue_local_test_token

    return cast(str, issue_local_test_token(subject=subject, scopes=scopes, roles=roles))


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ASGISyncClient:
    from generated_application.app.interfaces.api import main
    from generated_application.app.runtime import RuntimeLifecycle

    database = tmp_path / "api.sqlite3"
    monkeypatch.setattr(main, "DATABASE_PATH", database)
    monkeypatch.setattr(main, "RUNTIME", RuntimeLifecycle(database))
    return ASGISyncClient(main.app)


def test_api_template_declares_problem_json_and_openapi_31() -> None:
    api_root = Path(__file__).resolve().parents[2] / "interfaces/api"
    main_text = (api_root / "main.py").read_text(encoding="utf-8")
    error_text = (api_root / "error_handlers.py").read_text(encoding="utf-8")

    assert 'openapi_version="3.1.0"' in main_text
    assert "operationId" in main_text
    assert "LocalTestPrincipal" in main_text
    assert "OAuth2AuthorizationCodePkce" in main_text
    assert "RFC 9457 compatible" in main_text
    assert "x-content-type-options" in main_text
    assert "cache-control" in main_text
    assert "get_dispute" in main_text
    assert "require_object_access" in main_text
    assert "service.list_disputes" in main_text
    assert "application/problem+json" in error_text
    assert '"type"' in error_text
    assert '"correlation_id"' in error_text
    assert "RequestValidationError" in error_text
    assert "invalid_params = []" in error_text
    assert "masked_customer_upi" in (api_root / "schemas.py").read_text(encoding="utf-8")
    assert "runtime:drain" in main_text
    assert "runtime:diagnostics" in main_text


def test_openapi_schema_marks_every_protected_operation_secured() -> None:
    from generated_application.app.interfaces.api.main import app

    schema = app.openapi()
    paths = schema["paths"]
    protected = {
        ("/disputes", "post"): "dispute:create",
        ("/disputes", "get"): "dispute:read:any",
        ("/disputes/{dispute_id}", "get"): "dispute:read",
        ("/drain", "post"): "runtime:drain",
        ("/runtime/diagnostics", "get"): "runtime:diagnostics",
    }

    for (path, method), scope in protected.items():
        operation = paths[path][method]
        assert {"LocalTestPrincipal": []} in operation["security"]
        assert {"OAuth2AuthorizationCodePkce": [scope]} in operation["security"]
        assert operation["operationId"]
        assert operation["x-local-boundary"]["live_provider_calls_allowed"] is False
        assert operation["x-deterministic-examples"]["required_scopes"] == [scope]


def test_create_dispute_api_schema_rejects_unknown_json_fields() -> None:
    from generated_application.app.interfaces.api.main import app
    from generated_application.app.interfaces.api.schemas import CreateDisputeRequest

    schema = app.openapi()
    request_schema = schema["components"]["schemas"]["CreateDisputeRequest"]
    assert request_schema["additionalProperties"] is False

    with pytest.raises(ValidationError) as exc:
        CreateDisputeRequest.model_validate(
            {
                "transaction_ref": "UPI12345",
                "customer_upi": "client@upi",
                "reason": "failed debit",
                "unexpected": "must be rejected",
            }
        )

    assert exc.value.errors()[0]["type"] == "extra_forbidden"


def test_adapter_contracts_are_bounded_and_mock_only() -> None:
    from generated_application.app.infrastructure.external_adapters import (
        AdapterBackpressureError,
        AdapterCircuitOpenError,
        AdapterPayloadTooLargeError,
        AdapterRateLimitError,
        AdapterResilienceContract,
        DeterministicResilientAdapter,
        MOCK_ADAPTER_CONTRACTS,
    )

    rendered = [contract.as_dict() for contract in MOCK_ADAPTER_CONTRACTS]
    assert len(rendered) == 4
    assert all(contract["timeout_ms"] <= 5_000 for contract in rendered)
    assert all(contract["retry_budget"] <= 3 for contract in rendered)
    assert all(contract["jitter_ms"] >= 0 for contract in rendered)
    assert all(contract["live_provider_calls_allowed"] is False for contract in rendered)
    json.dumps(rendered, sort_keys=True)

    now = 0

    def clock() -> int:
        return now

    adapter = DeterministicResilientAdapter(
        AdapterResilienceContract(
            adapter_name="mock_test",
            timeout_ms=10,
            retry_budget=1,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_reset_ms=50,
        ),
        clock_ms=clock,
    )

    def fail() -> str:
        raise RuntimeError("deterministic failure")

    degraded = adapter.call(fail)
    assert isinstance(degraded, dict)
    assert degraded["mode"] == "return_local_manual_review_decision"
    try:
        adapter.call(lambda: "blocked")
    except AdapterCircuitOpenError:
        pass
    else:
        raise AssertionError("open circuit did not reject call")

    now = 51
    assert adapter.call(lambda: "ok") == "ok"

    payload_bound = DeterministicResilientAdapter(
        AdapterResilienceContract(adapter_name="mock_payload", max_payload_bytes=4),
        clock_ms=clock,
    )
    try:
        payload_bound.call(lambda: "oversize", payload={"value": "too large"})
    except AdapterPayloadTooLargeError:
        pass
    else:
        raise AssertionError("payload byte budget did not reject oversize payload")

    rate_bound = DeterministicResilientAdapter(
        AdapterResilienceContract(adapter_name="mock_rate", rate_limit_per_minute=1),
        clock_ms=clock,
    )
    assert rate_bound.call(lambda: "first", payload=b"ok") == "first"
    try:
        rate_bound.call(lambda: "second")
    except AdapterRateLimitError:
        pass
    else:
        raise AssertionError("deterministic rate budget did not reject second call")

    busy = DeterministicResilientAdapter(
        AdapterResilienceContract(adapter_name="mock_busy"),
        clock_ms=clock,
        in_flight=4,
    )
    try:
        busy.call(lambda: "overloaded")
    except AdapterBackpressureError:
        pass
    else:
        raise AssertionError("backpressure budget did not reject call")


def test_primary_fastapi_create_replay_validation_and_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "transaction_ref": "UPI12345",
        "customer_upi": "client@upi",
        "reason": "failed debit",
    }
    headers = {
        "Authorization": f"Bearer {_token('client-1', ('dispute:create', 'dispute:read'))}",
        "Idempotency-Key": "idem-api-primary",
        "X-Correlation-Id": "corr-api-primary",
    }

    client = _client(tmp_path, monkeypatch)
    first = client.post("/disputes", json=payload, headers=headers)
    replay = client.post("/disputes", json=payload, headers=headers)
    conflict = client.post(
        "/disputes",
        json={**payload, "reason": "different reason"},
        headers=headers,
    )
    validation = client.post(
        "/disputes",
        json={**payload, "unexpected": "field"},
        headers={**headers, "Idempotency-Key": "idem-validation"},
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert first.json()["dispute_id"] == replay.json()["dispute_id"]
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert validation.status_code == 422
    assert validation.json()["code"] == "RequestValidationError"
    assert first.headers["x-correlation-id"] == "corr-api-primary"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["cache-control"] == "no-store"


def test_primary_fastapi_auth_object_access_and_pagination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers = {
        "Authorization": f"Bearer {_token('client-1', ('dispute:create', 'dispute:read'))}",
        "Idempotency-Key": "idem-owner",
    }
    other_headers = {
        "Authorization": f"Bearer {_token('client-2', ('dispute:read',))}",
    }
    ops_headers = {
        "Authorization": f"Bearer {_token('ops', ('dispute:read:any',), ('ops_admin',))}",
    }

    client = _client(tmp_path, monkeypatch)
    missing_auth = client.post(
        "/disputes",
        json={"transaction_ref": "UPI10000", "customer_upi": "client@upi", "reason": "failed debit"},
        headers={"Idempotency-Key": "idem-missing-auth"},
    )
    invalid_auth = client.get("/disputes/DSP-MISSING", headers={"Authorization": "Bearer invalid"})
    created = client.post(
        "/disputes",
        json={"transaction_ref": "UPI10001", "customer_upi": "client@upi", "reason": "failed debit"},
        headers=owner_headers,
    )
    dispute_id = str(created.json()["dispute_id"])
    denied = client.get(f"/disputes/{dispute_id}", headers=other_headers)
    listed = client.get("/disputes?limit=1&cursor=0", headers=ops_headers)
    too_large = client.get("/disputes?limit=101&cursor=0", headers=ops_headers)

    assert missing_auth.status_code == 401
    assert invalid_auth.status_code == 401
    assert created.status_code == 201
    assert denied.status_code == 403
    assert denied.headers["content-type"].startswith("application/problem+json")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["dispute_id"] == dispute_id
    assert listed.json()["next_cursor"] == 1
    assert too_large.status_code == 429
