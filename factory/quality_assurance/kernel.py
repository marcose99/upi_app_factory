"""Deterministic assurance kernel for factory and generated-application evidence."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
import hashlib
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "upi-app-factory.quality-bundle.v1"
ACCEPTANCE_THRESHOLD = Decimal("99.0")
VERIFIED_STATUSES = frozenset(
    {"VERIFIED_BY_EXECUTABLE_EVIDENCE", "VERIFIED_BY_AUTHENTICATED_SOURCE"}
)
ALL_STATUSES = VERIFIED_STATUSES | frozenset(
    {
        "INFERRED_WITH_EXPLICIT_BASIS",
        "UNKNOWN_EXPLICIT",
        "EXTERNAL_REVIEW_PENDING",
        "UNSUPPORTED",
    }
)
HARD_GATES = (
    "artifact_hash_integrity_100_percent",
    "claim_evidence_coverage_100_percent",
    "unsupported_published_claims_zero",
    "phantom_file_or_test_references_zero",
    "requirements_trace_path_integrity_100_percent",
    "frozen_scope_requirements_covered_100_percent",
    "state_transition_coverage_100_percent",
    "policy_branch_coverage_100_percent",
    "api_contract_path_coverage_100_percent",
    "identified_risk_control_test_coverage_100_percent",
    "generated_test_collection_nonzero",
    "hermetic_extracted_package_tests_pass",
    "line_coverage_at_least_99_percent",
    "branch_coverage_at_least_99_percent",
    "critical_domain_mutation_score_at_least_95_percent",
    "deterministic_regeneration_100_percent",
    "architecture_runtime_conformance_100_percent",
    "scenario_semantic_differentiation_pass",
    "security_boundary_and_no_live_authority_pass",
    "html_json_parity_100_percent",
    "html_schema_link_contrast_and_accessibility_pass",
    "critical_findings_open_zero",
    "high_findings_open_zero",
    "internal_independent_review_lanes_8_of_8_pass",
    "external_review_status_truthfully_pending_or_signed",
    "canonical_repository_unchanged",
)
DIMENSION_WEIGHTS = {
    "architecture_and_engineering": 10,
    "business_and_semantic_fidelity": 20,
    "documentation_usability_and_accessibility": 5,
    "evidence_integrity_and_claim_grounding": 15,
    "independent_assurance_readiness": 5,
    "reliability_scalability_operability_observability": 10,
    "security_privacy_and_authority": 10,
    "supply_chain_reproducibility_and_durability": 5,
    "test_architecture_and_execution": 20,
}


class QualityAssuranceError(RuntimeError):
    """Raised when evidence cannot support a published quality decision."""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def digest(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _down(value: Decimal | float | int | str) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN))


def evidence_record(
    evidence_id: str,
    *,
    source: str,
    version: str,
    sha256: str,
    location: str,
    method: str,
    result: str,
) -> dict[str, str]:
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise QualityAssuranceError(f"invalid immutable digest for {evidence_id}")
    return {
        "evidence_id": evidence_id,
        "source": source,
        "version": version,
        "sha256": sha256,
        "location": location,
        "method": method,
        "result": result,
    }


def validate_claim_ledger(
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    *,
    acceptance_claim_ids: Sequence[str] = (),
) -> dict[str, Any]:
    evidence_ids = {str(row.get("evidence_id", "")) for row in evidence}
    if "" in evidence_ids or len(evidence_ids) != len(evidence):
        raise QualityAssuranceError("evidence IDs must be non-empty and unique")
    seen: set[str] = set()
    acceptance = set(acceptance_claim_ids)
    unsupported = 0
    for claim in claims:
        claim_id = str(claim.get("claim_id", ""))
        status = str(claim.get("status", ""))
        text = str(claim.get("text", "")).strip()
        bound = claim.get("evidence_ids", [])
        if not claim_id or claim_id in seen or not text or status not in ALL_STATUSES:
            raise QualityAssuranceError("claims require unique IDs, exact text and valid status")
        seen.add(claim_id)
        if not isinstance(bound, list) or any(item not in evidence_ids for item in bound):
            raise QualityAssuranceError(f"unbound evidence reference in {claim_id}")
        if status in VERIFIED_STATUSES and not bound:
            raise QualityAssuranceError(f"verified claim has no immutable evidence: {claim_id}")
        if status == "UNSUPPORTED":
            unsupported += 1
        if claim_id in acceptance and status not in VERIFIED_STATUSES:
            raise QualityAssuranceError(f"acceptance claim is not verified: {claim_id}")
        lowered = text.lower()
        prohibited_absolute = "absolute " + "no hallucination"
        if prohibited_absolute in lowered or "exhaustive testing" in lowered:
            raise QualityAssuranceError(f"unqualified absolute language in {claim_id}")
    missing_acceptance = acceptance - seen
    if missing_acceptance:
        raise QualityAssuranceError(f"unknown acceptance claims: {sorted(missing_acceptance)}")
    coverage = (
        100.0
        if not claims
        else _down(
            Decimal(sum(bool(row.get("evidence_ids")) for row in claims)) * 100 / len(claims)
        )
    )
    return {
        "claim_count": len(claims),
        "claim_coverage_percent": coverage,
        "unsupported_claim_count": unsupported,
        "phantom_reference_count": 0,
    }


def _ratio(numerator: Any, denominator: Any, label: str) -> float:
    n, d = Decimal(str(numerator)), Decimal(str(denominator))
    if d <= 0 or n < 0 or n > d:
        raise QualityAssuranceError(f"invalid raw measure for {label}")
    return _down(n * 100 / d)


def evaluate_acceptance(
    raw_measures: Mapping[str, Any], *, acceptance_contract: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Derive a decision only from numerator/denominator pairs and sealed test measures."""
    contract = acceptance_contract or {}
    threshold = Decimal(str(contract.get("threshold", ACCEPTANCE_THRESHOLD)))
    dimensions_raw = raw_measures.get("dimensions", {})
    scores: dict[str, float] = {}
    for name in DIMENSION_WEIGHTS:
        row = dimensions_raw.get(name)
        if not isinstance(row, Mapping):
            raise QualityAssuranceError(f"missing raw dimension measure: {name}")
        scores[name] = _ratio(row.get("met"), row.get("total"), name)
    hard_input = raw_measures.get("hard_gates", {})
    hard: dict[str, bool] = {}
    for gate in HARD_GATES:
        row = hard_input.get(gate)
        if not isinstance(row, Mapping) or not row.get("evidence_ids"):
            raise QualityAssuranceError(f"hard gate lacks raw measure or evidence: {gate}")
        hard[gate] = _ratio(row.get("met"), row.get("total"), gate) == 100.0
    weighted = sum(
        Decimal(str(scores[k])) * Decimal(str(w)) for k, w in DIMENSION_WEIGHTS.items()
    ) / Decimal("100")
    index = _down(weighted)
    accepted = (
        all(hard.values())
        and all(Decimal(str(v)) >= threshold for v in scores.values())
        and Decimal(str(index)) >= threshold
    )
    return {
        "schema_version": "upi-app-factory.quality-acceptance.v1",
        "hard_gates": hard,
        "dimension_scores": scores,
        "acceptance_index": index,
        "near_production_candidate": accepted,
        "production_ready": False,
        "decision": "NEAR_PRODUCTION_CANDIDATE" if accepted else "REJECTED",
        "external_human_review_status": raw_measures.get(
            "external_human_review_status", "PENDING_EXTERNAL_HUMAN_REVIEW"
        ),
    }


def validate_acceptance(acceptance: Mapping[str, Any]) -> None:
    if acceptance.get("production_ready") is not False:
        raise QualityAssuranceError("production_ready must remain false")
    hard = acceptance.get("hard_gates", {})
    scores = acceptance.get("dimension_scores", {})
    if acceptance.get("near_production_candidate"):
        if set(hard) != set(HARD_GATES) or not all(v is True for v in hard.values()):
            raise QualityAssuranceError("near-production decision has failed or missing hard gates")
        if set(scores) != set(DIMENSION_WEIGHTS) or min(map(float, scores.values())) < 99.0:
            raise QualityAssuranceError("near-production dimension is below 99.0")
        if float(acceptance.get("acceptance_index", 0)) < 99.0:
            raise QualityAssuranceError("near-production index is below 99.0")
