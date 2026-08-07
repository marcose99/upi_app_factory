from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ValidationFailed


@dataclass(frozen=True)
class UpiTransactionRef:
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) < 8:
            raise ValidationFailed("UPI transaction reference is required")


@dataclass(frozen=True)
class DisputeId:
    value: str


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationFailed("Idempotency key is required")
