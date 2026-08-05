from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Header, HTTPException

LOCAL_ISSUER = "upi-app-factory-local-issuer"
LOCAL_AUDIENCE = "upi-dispute-local"
LOCAL_SIGNING_KEY = b"upi-app-factory-deterministic-local-test-key"


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]
    scopes: frozenset[str]

    @property
    def primary_role(self) -> str:
        if not self.roles:
            return "unknown"
        return sorted(self.roles)[0]


@dataclass(frozen=True)
class OidcProductionAdapterContract:
    issuer: str = "https://idp.example.invalid/"
    audience: str = "upi-dispute-local"
    jwks_uri: str = "https://idp.example.invalid/.well-known/jwks.json"
    live_provider_calls_allowed: bool = False
    oauth2_security_benchmark: str = "RFC 9700 aligned benchmark; no certification claim"


def issue_local_test_token(
    *,
    subject: str,
    scopes: Iterable[str],
    roles: Iterable[str] = (),
    expires_in_seconds: int = 300,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": LOCAL_ISSUER,
        "aud": LOCAL_AUDIENCE,
        "sub": subject,
        "roles": sorted(set(roles)),
        "scopes": sorted(set(scopes)),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "live_provider_calls_allowed": False,
    }
    body = _b64url(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _b64url(hmac.new(LOCAL_SIGNING_KEY, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_local_test_token(token: str) -> Principal:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid local token") from exc
    expected = _b64url(hmac.new(LOCAL_SIGNING_KEY, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid local token signature")
    try:
        claims = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="invalid local token claims") from exc
    now = int(datetime.now(timezone.utc).timestamp())
    if claims.get("iss") != LOCAL_ISSUER or claims.get("aud") != LOCAL_AUDIENCE:
        raise HTTPException(status_code=401, detail="invalid local token issuer")
    if int(claims.get("exp", 0)) < now:
        raise HTTPException(status_code=401, detail="expired local token")
    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise HTTPException(status_code=401, detail="invalid local token subject")
    return Principal(
        subject=subject,
        roles=frozenset(str(item) for item in claims.get("roles", []) if str(item).strip()),
        scopes=frozenset(str(item) for item in claims.get("scopes", []) if str(item).strip()),
    )


class LocalAuthorizationPolicy:
    def require(self, principal: Principal, *, scopes: Iterable[str]) -> None:
        missing = [scope for scope in scopes if scope not in principal.scopes]
        if missing and "ops_admin" not in principal.roles:
            raise HTTPException(status_code=403, detail="authorization denied")

    def require_role(self, principal: Principal, *, roles: Iterable[str]) -> None:
        allowed = set(roles)
        if "ops_admin" in principal.roles or principal.roles.intersection(allowed):
            return
        raise HTTPException(status_code=403, detail="role authorization denied")

    def require_object_access(
        self,
        principal: Principal,
        *,
        owner_subject: str,
        scope: str,
    ) -> None:
        if "ops_admin" in principal.roles or "dispute:read:any" in principal.scopes:
            return
        if principal.roles.intersection(
            {
                "customer_support_agent",
                "dispute_operations_analyst",
                "supervisor_approver",
                "audit_reviewer",
            }
        ):
            return
        if principal.subject == owner_subject and scope in principal.scopes:
            return
        raise HTTPException(status_code=403, detail="object authorization denied")


def local_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    subject: str | None = Header(default=None, alias="X-Local-Subject"),
    roles: str = Header(default="", alias="X-Local-Roles"),
    scopes: str = Header(default="", alias="X-Local-Scopes"),
) -> Principal:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="bearer local token required")
        return verify_local_test_token(token)
    if os.environ.get("UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL") != "1":
        raise HTTPException(status_code=401, detail="signed local bearer token required")
    if not subject:
        raise HTTPException(status_code=401, detail="authentication required")
    return Principal(
        subject=subject,
        roles=frozenset(_split(roles)),
        scopes=frozenset(_split(scopes)),
    )


def openapi_security_schemes() -> dict[str, object]:
    return {
        "LocalTestPrincipal": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "deterministic-local-hmac-test-token",
            "description": "Signed local issuer fixture; no live identity-provider calls.",
        },
        "OAuth2AuthorizationCodePkce": {
            "type": "oauth2",
            "description": (
                "RFC 9700 aligned OAuth 2.0 profile benchmark for a future "
                "OIDC adapter contract. No live identity-provider calls."
            ),
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://idp.example.invalid/authorize",
                    "tokenUrl": "https://idp.example.invalid/token",
                    "scopes": {
                        "dispute:create": "Create local simulated disputes.",
                        "dispute:read:any": "List local simulated disputes.",
                        "dispute:read": "Read local simulated disputes owned by the principal.",
                        "dispute:evidence:write": "Attach local failed-debit evidence to an owned dispute.",
                        "dispute:investigation:write": "Record deterministic failed-debit investigation outcomes.",
                        "dispute:classify:write": "Classify a deterministic failed-debit case.",
                        "dispute:review:write": "Request or record deterministic failed-debit human review decisions.",
                        "dispute:disposition:write": "Record deterministic failed-debit dispositions.",
                        "dispute:close:write": "Authorize deterministic failed-debit closure.",
                        "dispute:quarantine:write": "Quarantine deterministic failed-debit cases.",
                        "dispute:history:read": "Read failed-debit event, review and evidence lineage.",
                        "dispute:audit:read": "Verify failed-debit audit integrity results.",
                        "runtime:drain": "Begin local runtime drain as an operator.",
                        "runtime:diagnostics": "Read bounded local runtime diagnostics.",
                    },
                }
            },
        },
}


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(",", " ").split() if item.strip()]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))
