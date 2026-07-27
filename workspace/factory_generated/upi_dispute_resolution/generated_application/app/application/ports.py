from __future__ import annotations

from typing import Any, Callable, Iterable, Protocol

from generated_application.app.domain.domain_events import DomainEvent
from generated_application.app.domain.entities import Dispute


class DisputeRepository(Protocol):
    def add(
        self,
        dispute: Dispute,
        *,
        audit_link_hash: str | None = None,
        business_fingerprint: str | None = None,
    ) -> None: ...
    def exists_for_business_fingerprint(self, business_fingerprint: str) -> bool: ...
    def get(self, dispute_id: str) -> Dispute | None: ...
    def list_page(self, *, limit: int, cursor: int) -> list[Dispute]: ...
    def save(self, dispute: Dispute, *, expected_version: int) -> int: ...


class IdempotencyStore(Protocol):
    def get(self, key: str) -> tuple[str, str] | None: ...
    def reserve(self, key: str, request_fingerprint: str) -> tuple[str, str] | None: ...
    def finalize(self, key: str, request_fingerprint: str, value: str) -> None: ...
    def put(self, key: str, request_fingerprint: str, value: str) -> None: ...


class Outbox(Protocol):
    def enqueue(self, event: DomainEvent, *, trace_id: str = "local-trace") -> str: ...


class AuditLog(Protocol):
    def append(self, actor_id: str, action: str, target: str, payload: dict[str, Any]) -> str: ...


class Inbox(Protocol):
    def process_once(self, message_id: str, handler: Callable[[], None]) -> bool: ...


class IdentityProvider(Protocol):
    def verify_local_principal(
        self,
        *,
        subject: str | None,
        roles: str,
        scopes: str,
    ) -> object: ...


class AuthorizationPolicy(Protocol):
    def require(self, principal: object, *, scopes: Iterable[str]) -> None: ...

    def require_object_access(
        self,
        principal: object,
        *,
        owner_subject: str,
        scope: str,
    ) -> None: ...
