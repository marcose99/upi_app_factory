import pytest
from typing import Any

from factory.quality_assurance import QualityAssuranceError, finalize_internal_review_acceptance


def reviews() -> list[dict[str, Any]]:
    return [
        {"role": f"ROLE_{i}", "status": "PASS", "critical_open": 0, "high_open": 0}
        for i in range(8)
    ]


def test_external_review_remains_pending_without_signed_evidence() -> None:
    result = finalize_internal_review_acceptance(reviews())
    assert result["external_human_review_status"] == "PENDING_EXTERNAL_HUMAN_REVIEW"
    assert result["production_ready"] is False


def test_duplicate_internal_role_fails() -> None:
    rows = reviews()
    rows[-1]["role"] = rows[0]["role"]
    with pytest.raises(QualityAssuranceError):
        finalize_internal_review_acceptance(rows)
