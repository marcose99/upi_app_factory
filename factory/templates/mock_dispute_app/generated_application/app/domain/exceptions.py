from __future__ import annotations


class DomainError(ValueError):
    """Base exception for deterministic generated-application domain failures."""


class InvalidStateTransition(DomainError):
    pass


class ValidationFailed(DomainError):
    pass
