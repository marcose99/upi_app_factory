from __future__ import annotations

from typing import Any

_NOTIFICATIONS: list[dict[str, Any]] = []


def record_notification_request(
    *,
    case_id: str,
    customer_reference: str,
    message: str,
) -> dict[str, Any]:
    record = {
        "case_id": case_id,
        "customer_reference": customer_reference,
        "message": message,
        "boundary_type": "MOCK_BOUNDARY",
        "data_label": "SYNTHETIC_DATA",
        "sent_to_real_customer": False,
    }
    _NOTIFICATIONS.append(record)
    return record


def list_notification_requests() -> list[dict[str, Any]]:
    return list(_NOTIFICATIONS)
