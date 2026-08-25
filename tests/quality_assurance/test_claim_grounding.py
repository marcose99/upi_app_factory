import pytest
from typing import Any

from factory.quality_assurance.kernel import QualityAssuranceError, validate_claim_ledger


def evidence() -> list[dict[str, Any]]:
    return [{"evidence_id": "EV-1", "sha256": "a" * 64}]


def test_verified_claim_is_bound_to_immutable_evidence() -> None:
    result = validate_claim_ledger(
        [
            {
                "claim_id": "CL-1",
                "status": "VERIFIED_BY_EXECUTABLE_EVIDENCE",
                "text": "The measured local test command passed.",
                "evidence_ids": ["EV-1"],
            }
        ],
        evidence(),
    )
    assert result["claim_coverage_percent"] == 100.0
    assert result["unsupported_claim_count"] == 0


def test_unbound_and_absolute_claims_fail_closed() -> None:
    with pytest.raises(QualityAssuranceError):
        validate_claim_ledger(
            [
                {
                    "claim_id": "CL-1",
                    "status": "VERIFIED_BY_AUTHENTICATED_SOURCE",
                    "text": "Absolute no hallucination proof",
                    "evidence_ids": ["missing"],
                }
            ],
            evidence(),
        )
