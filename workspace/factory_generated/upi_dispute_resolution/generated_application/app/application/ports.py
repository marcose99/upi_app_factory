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


class FailedDebitRepository(Protocol):
    def add_case(self, payload: dict[str, Any]) -> None: ...
    def get_case(self, dispute_id: str) -> dict[str, Any] | None: ...
    def get_case_detail(self, dispute_id: str) -> dict[str, Any] | None: ...
    def has_open_transaction_ref(self, transaction_ref: str) -> bool: ...
    def add_evidence(self, payload: dict[str, Any]) -> None: ...
    def list_evidence(self, dispute_id: str) -> list[dict[str, Any]]: ...
    def missing_evidence_types(self, dispute_id: str) -> set[str]: ...
    def update_case(
        self,
        dispute_id: str,
        *,
        expected_version: int,
        updates: dict[str, Any],
    ) -> int: ...
    def add_event(self, payload: dict[str, Any]) -> None: ...
    def list_events(self, dispute_id: str) -> list[dict[str, Any]]: ...
    def list_cases(
        self,
        *,
        limit: int,
        cursor: int,
        transaction_reference: str | None = None,
        state: str | None = None,
        age_bucket: str | None = None,
        analyst: str | None = None,
        resolution_status: str | None = None,
        classification: str | None = None,
        human_review_status: str | None = None,
    ) -> dict[str, Any]: ...
    def add_review_decision(self, payload: dict[str, Any]) -> None: ...
    def list_review_decisions(self, dispute_id: str) -> list[dict[str, Any]]: ...
    def add_audit_check(self, payload: dict[str, Any]) -> None: ...
    def list_audit_checks(self, dispute_id: str) -> list[dict[str, Any]]: ...


class IdempotencyStore(Protocol):
    def get(self, key: str) -> tuple[str, str] | None: ...
    def reserve(self, key: str, request_fingerprint: str) -> tuple[str, str] | None: ...
    def finalize(self, key: str, request_fingerprint: str, value: str) -> None: ...
    def put(self, key: str, request_fingerprint: str, value: str) -> None: ...


class Outbox(Protocol):
    def enqueue(self, event: DomainEvent, *, trace_id: str = "local-trace") -> str: ...


class AuditLog(Protocol):
    def append(
        self,
        actor_id: str,
        actor_role: str,
        action: str | None = None,
        target: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str: ...


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
