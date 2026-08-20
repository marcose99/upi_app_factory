"""Types and failures for governed blind architecture review."""

from __future__ import annotations

from typing import Any, Protocol


class ArchitectureReviewError(ValueError):
    """Raised when review evidence violates the frozen review contract."""


class ArchitectureReviewIncomplete(ArchitectureReviewError):
    """Raised when every required independent review is not available."""


class ReviewProvider(Protocol):
    """Injected provider boundary; C2 contains no vendor or network integration."""

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]: ...
