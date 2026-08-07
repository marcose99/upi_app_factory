from __future__ import annotations


class DomainError(ValueError):
    """Base exception for deterministic generated-application domain failures."""


class InvalidStateTransition(DomainError):
    pass


class OptimisticConcurrencyError(DomainError):
    pass


class IdempotencyConflictError(DomainError):
    pass


class DuplicateBusinessSubmissionError(DomainError):
    pass


class MigrationDriftError(DomainError):
    pass


class ValidationFailed(DomainError):
    pass
