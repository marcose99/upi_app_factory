from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.security.identity import (
    LocalAuthorizationPolicy,
    Principal,
    issue_local_test_token,
    local_principal,
    verify_local_test_token,
)


def test_function_authorization_requires_scope() -> None:
    policy = LocalAuthorizationPolicy()
    principal = Principal("local-user", frozenset(), frozenset({"dispute:read"}))

    with pytest.raises(HTTPException) as exc:
        policy.require(principal, scopes=("dispute:create",))

    assert exc.value.status_code == 403


def test_object_authorization_allows_owner_and_denies_other_subject() -> None:
    policy = LocalAuthorizationPolicy()
    owner = Principal("client-1", frozenset(), frozenset({"dispute:read"}))
    other = Principal("client-2", frozenset(), frozenset({"dispute:read"}))

    policy.require_object_access(owner, owner_subject="client-1", scope="dispute:read")
    with pytest.raises(HTTPException) as exc:
        policy.require_object_access(other, owner_subject="client-1", scope="dispute:read")

    assert exc.value.status_code == 403


def test_signed_local_token_round_trip_and_tamper_rejection() -> None:
    token = issue_local_test_token(
        subject="client-1",
        scopes=("dispute:create", "dispute:read"),
        roles=("customer",),
    )
    principal = verify_local_test_token(token)

    assert principal.subject == "client-1"
    assert "dispute:create" in principal.scopes
    assert "customer" in principal.roles

    with pytest.raises(HTTPException) as exc:
        verify_local_test_token(token + "tampered")

    assert exc.value.status_code == 401


def test_header_principal_fallback_is_not_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL", raising=False)

    with pytest.raises(HTTPException) as exc:
        local_principal(authorization=None, subject="header-user", scopes="dispute:read")

    assert exc.value.status_code == 401


def test_header_principal_fallback_requires_explicit_test_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL", "1")

    principal = local_principal(
        authorization=None,
        subject="header-user",
        roles="ops_admin",
        scopes="runtime:diagnostics",
    )

    assert principal.subject == "header-user"
    assert "ops_admin" in principal.roles
    assert "runtime:diagnostics" in principal.scopes
