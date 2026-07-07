from __future__ import annotations

from typing import Any

from .service import DisputeCaseIntakeService

_SERVICE = DisputeCaseIntakeService()


def create_dispute_case(payload: dict[str, Any]) -> dict[str, Any]:
    """Application API facade for dispute intake."""
    return _SERVICE.create_dispute_case(payload).to_dict()


def get_dispute_case(case_id: str) -> dict[str, Any] | None:
    case = _SERVICE.get_dispute_case(case_id)
    return None if case is None else case.to_dict()
