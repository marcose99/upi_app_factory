from __future__ import annotations

from pathlib import Path

import pytest

from factory.operator_portal.runtime_contracts import (
    RUNTIME_APPROVAL_TOKEN,
    RuntimeContractError,
    RuntimeState,
    approval_secret,
    scoped_approval_digest,
    transition_state,
    verify_scoped_approval,
)
from factory.operator_portal.runtime_network_policy import normalize_runtime_url, validate_redirect_location
from factory.operator_portal.runtime_store import default_binding


def test_runtime_state_transitions_fail_closed() -> None:
    assert transition_state(RuntimeState.ABSENT, RuntimeState.STARTING) == RuntimeState.STARTING
    with pytest.raises(RuntimeContractError):
        transition_state(RuntimeState.READY, RuntimeState.STARTING)


def test_approval_scope_and_replay_digest() -> None:
    digest = scoped_approval_digest(
        run_id="phase50_test",
        action="start",
        nonce="nonce-123456",
        token="token",
    )
    assert verify_scoped_approval(
        run_id="phase50_test",
        action="start",
        nonce="nonce-123456",
        presented_token="token",
        expected_sha256=digest,
    )
    assert not verify_scoped_approval(
        run_id="phase50_test",
        action="stop",
        nonce="nonce-123456",
        presented_token="token",
        expected_sha256=digest,
    )


def test_runtime_approval_secret_fails_closed_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPI_APP_FACTORY_RUNTIME_APPROVAL_TOKEN", raising=False)
    with pytest.raises(RuntimeContractError, match="UPI_APP_FACTORY_RUNTIME_APPROVAL_TOKEN"):
        approval_secret()
    monkeypatch.setenv("UPI_APP_FACTORY_RUNTIME_APPROVAL_TOKEN", RUNTIME_APPROVAL_TOKEN)
    assert approval_secret() == RUNTIME_APPROVAL_TOKEN


def test_loopback_policy_rejects_ssrf_and_redirect_escape() -> None:
    allowed = normalize_runtime_url(
        base_url="http://127.0.0.1:18042",
        method="GET",
        endpoint="/health",
        owned_port=18042,
    )
    assert allowed.url == "http://127.0.0.1:18042/health"

    with pytest.raises(RuntimeContractError):
        normalize_runtime_url(
            base_url="http://example.com:18042",
            method="GET",
            endpoint="/health",
            owned_port=18042,
        )
    with pytest.raises(RuntimeContractError):
        normalize_runtime_url(
            base_url="http://127.0.0.1:18042",
            method="GET",
            endpoint="http://127.0.0.1:18042/health",
            owned_port=18042,
        )
    with pytest.raises(RuntimeContractError):
        validate_redirect_location(
            base_url="http://127.0.0.1:18042",
            location="http://169.254.169.254/latest/meta-data",
            owned_port=18042,
        )


def test_default_runtime_binding_uses_hardened_generated_api(tmp_path: Path) -> None:
    binding = default_binding(tmp_path, run_id="phase50_binding", port=18042)
    assert binding.entrypoint == "generated_application.app.interfaces.api.main:app"
