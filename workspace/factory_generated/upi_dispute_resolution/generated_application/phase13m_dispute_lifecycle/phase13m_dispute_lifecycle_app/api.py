from __future__ import annotations

from typing import Any

from .service import DisputeLifecycleService

_SERVICE = DisputeLifecycleService()


def create_case(payload: dict[str, Any]) -> dict[str, Any]:
    return _SERVICE.create_case(payload).to_dict()


def progress_case_to_resolution(case_id: str) -> dict[str, Any]:
    return _SERVICE.progress_to_resolution(case_id).to_dict()


def get_case(case_id: str) -> dict[str, Any] | None:
    case = _SERVICE.get_case(case_id)
    return None if case is None else case.to_dict()
