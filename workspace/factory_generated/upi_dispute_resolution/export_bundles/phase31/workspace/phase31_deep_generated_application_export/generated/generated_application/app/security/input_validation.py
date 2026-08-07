from __future__ import annotations

from generated_application.app.domain.exceptions import ValidationFailed


def reject_live_endpoint(value: str) -> None:
    lowered = value.lower()
    forbidden = ["npci.org", "rbi.org", "bank", "production", "live"]
    if any(token in lowered for token in forbidden):
        raise ValidationFailed("Live ecosystem endpoints are outside the generated-app boundary")
