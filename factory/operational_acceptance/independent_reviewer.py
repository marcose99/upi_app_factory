"""Deterministic skeptical review over registered claims and canonical evidence.

The reviewer is a projection over the M2.4 fact/evidence graph and the M2.6
value-closure claim model.  It does not infer authority from prose and it does
not call an LLM.  A positive verdict requires a current status fact, current
supporting facts, exact provenance linkage, and evidence satisfying an explicit
claim contract.  Adverse and indeterminate findings remain in the canonical
review record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, TypeAlias, cast

from factory.documentation import (
    EvidenceGraph,
    FactNode,
    FactStatus,
    Freshness,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.documentation.facts import FactModelError

from .failure_recovery import ProofVerdict
from .value_closure import (
    CAPABILITY_STATUS_NODE_TYPES,
    MACHINE_EVIDENCE_NODE_TYPES,
    MACHINE_EVIDENCE_RELATION,
    MACHINE_EVIDENCE_SOURCE_TYPES,
    CapabilityClaim,
    ValueClosureStatus,
    _normalize_current_sources,
    _public_identifier,
    _public_text,
)


class IndependentReviewError(FactModelError):
    """Raised when a review input or serialized review is ambiguous."""


# Reuse the existing evidence-verdict primitive.  Independent reviews enforce
# the five-value subset below and never emit ProofVerdict.NOT_MEASURED.
ReviewerVerdict: TypeAlias = ProofVerdict
REVIEWER_VERDICTS = frozenset(
    {
        ProofVerdict.PROVEN,
        ProofVerdict.DISPROVEN,
        ProofVerdict.PARTIAL,
        ProofVerdict.UNKNOWN,
        ProofVerdict.NOT_APPLICABLE,
    }
)


class ClaimDomain(str, Enum):
    """Explicit claim scope; no domain is inferred from claim prose."""

    FACTORY_CAPABILITY = "FACTORY_CAPABILITY"
    PRODUCTION_READINESS = "PRODUCTION_READINESS"
    REGULATORY_COMPLIANCE = "REGULATORY_COMPLIANCE"
    SECURITY_ASSURANCE = "SECURITY_ASSURANCE"


class FindingSeverity(str, Enum):
    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ChallengeKind(str, Enum):
    """Fixed skeptical attempts applied to every registered claim."""

    STATUS_FACT_INTEGRITY = "STATUS_FACT_INTEGRITY"
    SUPPORTING_FACT_INTEGRITY = "SUPPORTING_FACT_INTEGRITY"
    EVIDENCE_PRESENCE_AND_FRESHNESS = "EVIDENCE_PRESENCE_AND_FRESHNESS"
    PROVENANCE_LINKAGE_INTEGRITY = "PROVENANCE_LINKAGE_INTEGRITY"
    AI_AUTHORITY_BOUNDARY = "AI_AUTHORITY_BOUNDARY"
    CLAIM_CONTRACT_SATISFACTION = "CLAIM_CONTRACT_SATISFACTION"


CHALLENGE_ORDER = tuple(ChallengeKind)

_AI_SOURCE_TYPES = frozenset(
    {
        "AI_PROPOSAL",
        "AI_STATEMENT",
        "LLM_JUDGEMENT",
        "LLM_JUDGMENT",
        "MODEL_GENERATED_NARRATIVE",
    }
)
_AI_NODE_TYPES = frozenset(
    {
        "AI_PROPOSAL",
        "AI_STATEMENT",
        "LLM_JUDGEMENT",
        "LLM_JUDGMENT",
        "MODEL_GENERATED_NARRATIVE",
    }
)
_PROTECTED_DOMAINS = frozenset(
    {
        ClaimDomain.PRODUCTION_READINESS,
        ClaimDomain.REGULATORY_COMPLIANCE,
        ClaimDomain.SECURITY_ASSURANCE,
    }
)


def _records(
    values: Iterable[Any], field_name: str, expected_type: type[Any], *, required: bool
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise IndependentReviewError(f"{field_name} must be a collection")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise IndependentReviewError(f"{field_name} must be a collection") from exc
    if required and not result:
        raise IndependentReviewError(f"{field_name} must not be empty")
    if any(not isinstance(item, expected_type) for item in result):
        raise IndependentReviewError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    return result


def _identifiers(
    values: Iterable[str], field_name: str, *, required: bool
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise IndependentReviewError(f"{field_name} must be a collection")
    try:
        result = tuple(_public_identifier(item, field_name) for item in values)
    except (TypeError, FactModelError) as exc:
        raise IndependentReviewError(str(exc)) from exc
    if required and not result:
        raise IndependentReviewError(f"{field_name} must not be empty")
    if len(result) != len(set(result)):
        raise IndependentReviewError(f"{field_name} must contain unique identities")
    return tuple(sorted(result))


def _is_ai_authority(value: str) -> bool:
    upper = value.upper()
    if upper in _AI_SOURCE_TYPES or upper in _AI_NODE_TYPES:
        return True
    tokens = set(upper.replace("-", "_").split("_"))
    return bool(tokens.intersection({"AI", "LLM"}))


@dataclass(frozen=True)
class EvidenceRequirement:
    """One explicit evidence class required by a claim contract."""

    requirement_id: str
    node_types: tuple[str, ...]
    source_types: tuple[str, ...]
    accepted_results: tuple[str, ...]
    relation: str = MACHINE_EVIDENCE_RELATION
    minimum_count: int = 1

    def __post_init__(self) -> None:
        try:
            _public_identifier(self.requirement_id, "requirement_id")
            _public_identifier(self.relation, "relation")
            nodes = _identifiers(self.node_types, "node_types", required=True)
            sources = _identifiers(self.source_types, "source_types", required=True)
            results = _identifiers(
                self.accepted_results, "accepted_results", required=True
            )
        except FactModelError as exc:
            raise IndependentReviewError(str(exc)) from exc
        if any(_is_ai_authority(item) for item in (*nodes, *sources)):
            raise IndependentReviewError(
                "AI or LLM material cannot be an accepted evidence authority"
            )
        allowed_nodes = MACHINE_EVIDENCE_NODE_TYPES.union(
            {
                "PRODUCTION_OPERATIONAL_ACCEPTANCE_EVIDENCE",
                "REGULATORY_COMPLIANCE_EVIDENCE",
                "SECURITY_VERIFICATION_EVIDENCE",
            }
        )
        allowed_sources = MACHINE_EVIDENCE_SOURCE_TYPES.union(
            {
                "AUTHORIZED_PRODUCTION_ACCEPTANCE_RECORD",
                "EXTERNAL_REGULATORY_AUTHORITY_RECORD",
                "AUTHENTICATED_SECURITY_ASSESSMENT_RECORD",
            }
        )
        if not set(nodes).issubset(allowed_nodes):
            raise IndependentReviewError(
                "node_types must use the closed authenticated evidence vocabulary"
            )
        if not set(sources).issubset(allowed_sources):
            raise IndependentReviewError(
                "source_types must use the closed authenticated evidence vocabulary"
            )
        if not set(results).issubset({"PASS", "PROVEN"}):
            raise IndependentReviewError(
                "accepted_results can only recognize PASS or PROVEN observations"
            )
        if self.relation != MACHINE_EVIDENCE_RELATION:
            raise IndependentReviewError(
                f"evidence requirements must use {MACHINE_EVIDENCE_RELATION}"
            )
        if not isinstance(self.minimum_count, int) or self.minimum_count < 1:
            raise IndependentReviewError("minimum_count must be a positive integer")
        object.__setattr__(self, "node_types", nodes)
        object.__setattr__(self, "source_types", sources)
        object.__setattr__(self, "accepted_results", results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted_results": list(self.accepted_results),
            "minimum_count": self.minimum_count,
            "node_types": list(self.node_types),
            "relation": self.relation,
            "requirement_id": self.requirement_id,
            "source_types": list(self.source_types),
        }


_DOMAIN_REQUIREMENTS: dict[ClaimDomain, tuple[EvidenceRequirement, ...]] = {
    ClaimDomain.FACTORY_CAPABILITY: (
        EvidenceRequirement(
            "REQ-CURRENT-AUTHENTICATED-MACHINE-EVIDENCE",
            tuple(MACHINE_EVIDENCE_NODE_TYPES),
            tuple(MACHINE_EVIDENCE_SOURCE_TYPES),
            ("PASS", "PROVEN"),
        ),
    ),
    ClaimDomain.PRODUCTION_READINESS: (
        EvidenceRequirement(
            "REQ-AUTHORIZED-PRODUCTION-ACCEPTANCE",
            ("PRODUCTION_OPERATIONAL_ACCEPTANCE_EVIDENCE",),
            ("AUTHORIZED_PRODUCTION_ACCEPTANCE_RECORD",),
            ("PROVEN",),
        ),
    ),
    ClaimDomain.REGULATORY_COMPLIANCE: (
        EvidenceRequirement(
            "REQ-EXTERNAL-REGULATORY-AUTHORITY",
            ("REGULATORY_COMPLIANCE_EVIDENCE",),
            ("EXTERNAL_REGULATORY_AUTHORITY_RECORD",),
            ("PROVEN",),
        ),
    ),
    ClaimDomain.SECURITY_ASSURANCE: (
        EvidenceRequirement(
            "REQ-AUTHENTICATED-SECURITY-ASSESSMENT",
            ("SECURITY_VERIFICATION_EVIDENCE",),
            ("AUTHENTICATED_SECURITY_ASSESSMENT_RECORD",),
            ("PASS", "PROVEN"),
        ),
    ),
}


@dataclass(frozen=True)
class ClaimContract:
    """Registered evidence contract, including adoption-blocker semantics."""

    contract_id: str
    domain: ClaimDomain
    evidence_requirements: tuple[EvidenceRequirement, ...]
    adverse_severity: FindingSeverity = FindingSeverity.BLOCKER
    blocks_adoption: bool = True

    def __post_init__(self) -> None:
        try:
            _public_identifier(self.contract_id, "contract_id")
        except FactModelError as exc:
            raise IndependentReviewError(str(exc)) from exc
        if not isinstance(self.domain, ClaimDomain):
            raise IndependentReviewError("domain must use ClaimDomain")
        requirements = _records(
            self.evidence_requirements,
            "evidence_requirements",
            EvidenceRequirement,
            required=True,
        )
        requirement_ids = [item.requirement_id for item in requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise IndependentReviewError("evidence requirement IDs must be unique")
        if not isinstance(self.adverse_severity, FindingSeverity):
            raise IndependentReviewError("adverse_severity must use FindingSeverity")
        if not isinstance(self.blocks_adoption, bool):
            raise IndependentReviewError("blocks_adoption must be an explicit boolean")
        if self.blocks_adoption and self.adverse_severity is FindingSeverity.INFO:
            raise IndependentReviewError("an adoption blocker cannot have INFO severity")
        ordered = tuple(sorted(requirements, key=lambda item: item.requirement_id))
        if self.domain in _PROTECTED_DOMAINS:
            expected_contract_id = f"CLAIM-CONTRACT-{self.domain.value}-V1"
            protected_contract_weakened = (
                self.contract_id != expected_contract_id
                or ordered
                != tuple(
                    sorted(
                        _DOMAIN_REQUIREMENTS[self.domain],
                        key=lambda item: item.requirement_id,
                    )
                )
                or not self.blocks_adoption
                or self.adverse_severity is not FindingSeverity.BLOCKER
            )
            if protected_contract_weakened:
                raise IndependentReviewError(
                    "protected claim domains require the closed governed evidence contract"
                )
        object.__setattr__(self, "evidence_requirements", ordered)

    @classmethod
    def for_domain(
        cls,
        domain: ClaimDomain,
        *,
        adverse_severity: FindingSeverity = FindingSeverity.BLOCKER,
        blocks_adoption: bool = True,
    ) -> "ClaimContract":
        if not isinstance(domain, ClaimDomain):
            raise IndependentReviewError("domain must use ClaimDomain")
        return cls(
            contract_id=f"CLAIM-CONTRACT-{domain.value}-V1",
            domain=domain,
            evidence_requirements=_DOMAIN_REQUIREMENTS[domain],
            adverse_severity=adverse_severity,
            blocks_adoption=blocks_adoption,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "adverse_severity": self.adverse_severity.value,
            "blocks_adoption": self.blocks_adoption,
            "contract_id": self.contract_id,
            "domain": self.domain.value,
            "evidence_requirements": [
                item.to_dict() for item in self.evidence_requirements
            ],
        }


@dataclass(frozen=True)
class RegisteredClaim:
    """A value-closure claim explicitly paired with its review contract."""

    claim: CapabilityClaim
    contract: ClaimContract

    def __post_init__(self) -> None:
        if not isinstance(self.claim, CapabilityClaim):
            raise IndependentReviewError("claim must use CapabilityClaim")
        if not isinstance(self.contract, ClaimContract):
            raise IndependentReviewError("contract must use ClaimContract")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "claim": {
                "capability_id": self.claim.capability_id,
                "claim_id": self.claim.claim_id,
                "claim_text": self.claim.claim_text,
                "limitations": [item.to_dict() for item in self.claim.limitations],
                "machine_evidence_fact_ids": list(
                    self.claim.machine_evidence_fact_ids
                ),
                "status": self.claim.status.value,
                "status_fact_id": self.claim.status_fact_id,
                "supporting_fact_ids": list(self.claim.supporting_fact_ids),
            },
            "contract": self.contract.to_dict(),
        }

    @property
    def registration_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def registration_id(self) -> str:
        return f"CLAIM-REGISTRATION-{self.registration_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "registration_id": self.registration_id,
            "registration_sha256": self.registration_sha256,
        }


@dataclass(frozen=True)
class ChallengeFinding:
    """One preserved skeptical attempt and its evidence-derived outcome."""

    claim_id: str
    challenge: ChallengeKind
    verdict: ProofVerdict
    severity: FindingSeverity
    blocker: bool
    evidence_fact_ids: tuple[str, ...]
    evidence_source_ids: tuple[str, ...]
    evidence_relationship_ids: tuple[str, ...]
    limitation_ids: tuple[str, ...]
    expected: Any
    observed: Any
    explanation: str

    def __post_init__(self) -> None:
        try:
            _public_identifier(self.claim_id, "claim_id")
            facts = _identifiers(
                self.evidence_fact_ids, "evidence_fact_ids", required=False
            )
            sources = _identifiers(
                self.evidence_source_ids, "evidence_source_ids", required=False
            )
            relationships = _identifiers(
                self.evidence_relationship_ids,
                "evidence_relationship_ids",
                required=False,
            )
            limitations = _identifiers(
                self.limitation_ids, "limitation_ids", required=True
            )
            _public_text(self.explanation, "explanation")
        except FactModelError as exc:
            raise IndependentReviewError(str(exc)) from exc
        if not isinstance(self.challenge, ChallengeKind):
            raise IndependentReviewError("challenge must use ChallengeKind")
        if self.verdict not in REVIEWER_VERDICTS:
            raise IndependentReviewError("verdict is outside the reviewer vocabulary")
        if not isinstance(self.severity, FindingSeverity):
            raise IndependentReviewError("severity must use FindingSeverity")
        if not isinstance(self.blocker, bool):
            raise IndependentReviewError("blocker must be an explicit boolean")
        if self.verdict in {ProofVerdict.PROVEN, ProofVerdict.NOT_APPLICABLE}:
            if self.blocker or self.severity is not FindingSeverity.INFO:
                raise IndependentReviewError(
                    "PROVEN and NOT_APPLICABLE findings must be non-blocking INFO"
                )
        if self.blocker and self.severity is FindingSeverity.INFO:
            raise IndependentReviewError("blocker findings cannot have INFO severity")
        if not self.blocker and self.severity is FindingSeverity.BLOCKER:
            raise IndependentReviewError("BLOCKER severity requires an open blocker")
        try:
            expected = json.loads(canonical_json(self.expected))
            observed = json.loads(canonical_json(self.observed))
        except FactModelError as exc:
            raise IndependentReviewError(str(exc)) from exc
        object.__setattr__(self, "evidence_fact_ids", facts)
        object.__setattr__(self, "evidence_source_ids", sources)
        object.__setattr__(self, "evidence_relationship_ids", relationships)
        object.__setattr__(self, "limitation_ids", limitations)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "observed", observed)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "blocker": self.blocker,
            "challenge": self.challenge.value,
            "claim_id": self.claim_id,
            "evidence_fact_ids": list(self.evidence_fact_ids),
            "evidence_relationship_ids": list(self.evidence_relationship_ids),
            "evidence_source_ids": list(self.evidence_source_ids),
            "expected": self.expected,
            "explanation": self.explanation,
            "limitation_ids": list(self.limitation_ids),
            "observed": self.observed,
            "severity": self.severity.value,
            "verdict": self.verdict.value,
        }

    @property
    def finding_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def finding_id(self) -> str:
        return f"REVIEW-FINDING-{self.finding_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "finding_id": self.finding_id,
            "finding_sha256": self.finding_sha256,
        }


def _aggregate_verdicts(values: Iterable[ProofVerdict]) -> ProofVerdict:
    verdicts = tuple(values)
    if not verdicts:
        return ProofVerdict.UNKNOWN
    if any(item is ProofVerdict.DISPROVEN for item in verdicts):
        return ProofVerdict.DISPROVEN
    if any(item is ProofVerdict.UNKNOWN for item in verdicts):
        return ProofVerdict.UNKNOWN
    if any(item is ProofVerdict.PARTIAL for item in verdicts):
        return ProofVerdict.PARTIAL
    if any(item is ProofVerdict.PROVEN for item in verdicts):
        return ProofVerdict.PROVEN
    return ProofVerdict.NOT_APPLICABLE


def _aggregate_claim_findings(
    findings: Iterable[ChallengeFinding],
) -> ProofVerdict:
    ordered = tuple(findings)
    if (
        ordered
        and ordered[0].challenge is ChallengeKind.STATUS_FACT_INTEGRITY
        and ordered[0].verdict is ProofVerdict.NOT_APPLICABLE
    ):
        return ProofVerdict.NOT_APPLICABLE
    return _aggregate_verdicts(item.verdict for item in ordered)


@dataclass(frozen=True)
class ClaimReview:
    """Canonical review result for one registered claim."""

    registration: RegisteredClaim
    verdict: ProofVerdict
    findings: tuple[ChallengeFinding, ...]
    evidence_assessments: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.registration, RegisteredClaim):
            raise IndependentReviewError("registration must use RegisteredClaim")
        if self.verdict not in REVIEWER_VERDICTS:
            raise IndependentReviewError("claim verdict is outside reviewer vocabulary")
        findings = _records(
            self.findings, "findings", ChallengeFinding, required=True
        )
        expected_order = list(CHALLENGE_ORDER)
        if [item.challenge for item in findings] != expected_order:
            raise IndependentReviewError(
                "findings must attempt every skeptical challenge in canonical order"
            )
        if any(item.claim_id != self.registration.claim.claim_id for item in findings):
            raise IndependentReviewError("findings must bind the registered claim")
        if self.verdict is not _aggregate_claim_findings(findings):
            raise IndependentReviewError("claim verdict is not derived from findings")
        try:
            assessments = tuple(
                cast(Mapping[str, Any], json.loads(canonical_json(dict(item))))
                for item in self.evidence_assessments
            )
        except (TypeError, ValueError, FactModelError) as exc:
            raise IndependentReviewError(
                "evidence_assessments must be canonical JSON objects"
            ) from exc
        assessment_ids = [str(item.get("evidence_fact_id", "")) for item in assessments]
        if assessment_ids != sorted(assessment_ids) or len(assessment_ids) != len(
            set(assessment_ids)
        ):
            raise IndependentReviewError(
                "evidence assessments must be uniquely and canonically ordered"
            )
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "evidence_assessments", assessments)

    @property
    def open_blocker_finding_ids(self) -> tuple[str, ...]:
        return tuple(item.finding_id for item in self.findings if item.blocker)

    def identity_payload(self) -> dict[str, Any]:
        claim = self.registration.claim
        return {
            "capability_id": claim.capability_id,
            "claim_id": claim.claim_id,
            "claim_text": claim.claim_text,
            "contract": self.registration.contract.to_dict(),
            "declared_status": claim.status.value,
            "evidence_assessments": [dict(item) for item in self.evidence_assessments],
            "findings": [item.to_dict() for item in self.findings],
            "limitations": [item.to_dict() for item in claim.limitations],
            "open_blocker_finding_ids": list(self.open_blocker_finding_ids),
            "registration_id": self.registration.registration_id,
            "verdict": self.verdict.value,
        }

    @property
    def review_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def review_id(self) -> str:
        return f"CLAIM-REVIEW-{self.review_sha256}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "review_id": self.review_id,
            "review_sha256": self.review_sha256,
        }


def _fact_verdict(status: FactStatus) -> ProofVerdict:
    if status is FactStatus.PROVEN:
        return ProofVerdict.PROVEN
    if status is FactStatus.PARTIAL:
        return ProofVerdict.PARTIAL
    if status is FactStatus.NOT_APPLICABLE:
        return ProofVerdict.NOT_APPLICABLE
    if status in {
        FactStatus.NOT_IMPLEMENTED,
        FactStatus.NOT_RELEASED,
        FactStatus.NOT_DEPLOYED,
    }:
        return ProofVerdict.DISPROVEN
    return ProofVerdict.UNKNOWN


def _finding(
    registration: RegisteredClaim,
    challenge: ChallengeKind,
    verdict: ProofVerdict,
    *,
    evidence_fact_ids: Iterable[str],
    evidence_source_ids: Iterable[str] = (),
    evidence_relationship_ids: Iterable[str] = (),
    expected: Any,
    observed: Any,
    explanation: str,
) -> ChallengeFinding:
    adverse = verdict not in {ProofVerdict.PROVEN, ProofVerdict.NOT_APPLICABLE}
    return ChallengeFinding(
        claim_id=registration.claim.claim_id,
        challenge=challenge,
        verdict=verdict,
        severity=(
            registration.contract.adverse_severity
            if adverse
            else FindingSeverity.INFO
        ),
        blocker=registration.contract.blocks_adoption and adverse,
        evidence_fact_ids=tuple(evidence_fact_ids),
        evidence_source_ids=tuple(evidence_source_ids),
        evidence_relationship_ids=tuple(evidence_relationship_ids),
        limitation_ids=tuple(
            item.limitation_id for item in registration.claim.limitations
        ),
        expected=expected,
        observed=observed,
        explanation=explanation,
    )


def _node_sources(graph: EvidenceGraph, fact_ids: Iterable[str]) -> tuple[str, ...]:
    result: set[str] = set()
    for fact_id in fact_ids:
        try:
            result.update(item.source_id for item in graph.node(fact_id).provenance)
        except FactModelError:
            continue
    return tuple(sorted(result))


def _review_claim(
    graph: EvidenceGraph,
    current_sources: Mapping[str, tuple[str, str]],
    registration: RegisteredClaim,
) -> ClaimReview:
    claim = registration.claim
    edges = tuple(graph.to_dict()["edges"])
    evidence_ids = claim.machine_evidence_fact_ids
    evidence_sources = _node_sources(graph, evidence_ids)

    # 1. Challenge the declared status against the canonical status fact.
    try:
        status_node = graph.node(claim.status_fact_id)
    except FactModelError:
        status_verdict = ProofVerdict.UNKNOWN
        status_observed: Any = {"availability": "MISSING"}
    else:
        status_observed = {
            "availability": "PRESENT",
            "freshness": status_node.freshness(current_sources).value,
            "node_type": status_node.node_type,
            "status": status_node.status.value,
        }
        if status_node.node_type not in CAPABILITY_STATUS_NODE_TYPES:
            status_verdict = ProofVerdict.DISPROVEN
        elif status_node.status.value != claim.status.value:
            status_verdict = ProofVerdict.DISPROVEN
        else:
            status_verdict = _fact_verdict(status_node.status)
            if (
                status_verdict is ProofVerdict.PROVEN
                and status_node.freshness(current_sources) is not Freshness.CURRENT
            ):
                status_verdict = ProofVerdict.UNKNOWN
    findings: list[ChallengeFinding] = [
        _finding(
            registration,
            ChallengeKind.STATUS_FACT_INTEGRITY,
            status_verdict,
            evidence_fact_ids=(claim.status_fact_id,),
            evidence_source_ids=_node_sources(graph, (claim.status_fact_id,)),
            expected={
                "node_types": sorted(CAPABILITY_STATUS_NODE_TYPES),
                "status": claim.status.value,
                "when_proven_freshness": Freshness.CURRENT.value,
            },
            observed=status_observed,
            explanation=(
                "Attempted to disprove the declared status against its canonical "
                "fact and current provenance."
            ),
        )
    ]

    # 2. Challenge supporting facts not already assessed as status or machine evidence.
    additional_ids = tuple(
        item
        for item in claim.supporting_fact_ids
        if item != claim.status_fact_id and item not in set(evidence_ids)
    )
    supporting_observed: list[dict[str, str]] = []
    supporting_verdicts: list[ProofVerdict] = []
    for fact_id in additional_ids:
        try:
            node = graph.node(fact_id)
        except FactModelError:
            supporting_observed.append(
                {"availability": "MISSING", "fact_id": fact_id}
            )
            supporting_verdicts.append(ProofVerdict.UNKNOWN)
            continue
        freshness = node.freshness(current_sources)
        verdict = _fact_verdict(node.status)
        if verdict is ProofVerdict.PROVEN and freshness is not Freshness.CURRENT:
            verdict = ProofVerdict.UNKNOWN
        supporting_observed.append(
            {
                "availability": "PRESENT",
                "fact_id": fact_id,
                "freshness": freshness.value,
                "status": node.status.value,
            }
        )
        supporting_verdicts.append(verdict)
    supporting_verdict = (
        _aggregate_verdicts(supporting_verdicts)
        if additional_ids
        else ProofVerdict.NOT_APPLICABLE
    )
    findings.append(
        _finding(
            registration,
            ChallengeKind.SUPPORTING_FACT_INTEGRITY,
            supporting_verdict,
            evidence_fact_ids=additional_ids,
            evidence_source_ids=_node_sources(graph, additional_ids),
            expected={"all_declared_support": "CURRENT_AND_PROVEN"},
            observed=supporting_observed,
            explanation=(
                "Attempted to disprove the claim using every additional declared "
                "supporting fact."
            ),
        )
    )

    # 3. Challenge evidence existence, fact status, and live source identity.
    presence_observed: list[dict[str, str]] = []
    presence_verdicts: list[ProofVerdict] = []
    for evidence_id in evidence_ids:
        try:
            node = graph.node(evidence_id)
        except FactModelError:
            presence_observed.append(
                {"availability": "MISSING", "evidence_fact_id": evidence_id}
            )
            presence_verdicts.append(ProofVerdict.UNKNOWN)
            continue
        freshness = node.freshness(current_sources)
        verdict = _fact_verdict(node.status)
        if verdict is ProofVerdict.PROVEN and freshness is not Freshness.CURRENT:
            verdict = ProofVerdict.UNKNOWN
        presence_observed.append(
            {
                "availability": "PRESENT",
                "evidence_fact_id": evidence_id,
                "freshness": freshness.value,
                "status": node.status.value,
            }
        )
        presence_verdicts.append(verdict)
    positive_claim = claim.status in {
        ValueClosureStatus.PROVEN,
        ValueClosureStatus.PARTIAL,
    }
    if evidence_ids:
        presence_verdict = _aggregate_verdicts(presence_verdicts)
    elif positive_claim:
        presence_verdict = ProofVerdict.UNKNOWN
    else:
        presence_verdict = ProofVerdict.NOT_APPLICABLE
    findings.append(
        _finding(
            registration,
            ChallengeKind.EVIDENCE_PRESENCE_AND_FRESHNESS,
            presence_verdict,
            evidence_fact_ids=evidence_ids,
            evidence_source_ids=evidence_sources,
            expected={
                "minimum_evidence_count": 1 if positive_claim else 0,
                "status": FactStatus.PROVEN.value,
                "freshness": Freshness.CURRENT.value,
            },
            observed=presence_observed,
            explanation=(
                "Attempted to disprove evidence availability, proven state, and "
                "current source identity."
            ),
        )
    )

    # 4. Challenge exact status-fact -> evidence provenance relationships.
    linkage_observed: list[dict[str, Any]] = []
    linkage_verdicts: list[ProofVerdict] = []
    relationship_ids: list[str] = []
    for evidence_id in evidence_ids:
        try:
            node = graph.node(evidence_id)
        except FactModelError:
            linkage_observed.append(
                {"availability": "EVIDENCE_MISSING", "evidence_fact_id": evidence_id}
            )
            linkage_verdicts.append(ProofVerdict.UNKNOWN)
            continue
        matching = [
            edge
            for edge in edges
            if edge["source_id"] == claim.status_fact_id
            and edge["target_id"] == evidence_id
            and edge["relation"] == MACHINE_EVIDENCE_RELATION
        ]
        relationship_ids.extend(str(edge["edge_id"]) for edge in matching)
        expected_sources = sorted(item.source_id for item in node.provenance)
        exact = (
            len(matching) == 1
            and sorted(matching[0]["provenance_ids"]) == expected_sources
        )
        linkage_observed.append(
            {
                "evidence_fact_id": evidence_id,
                "exact_provenance_binding": exact,
                "relationship_count": len(matching),
                "relationship_ids": sorted(str(edge["edge_id"]) for edge in matching),
            }
        )
        linkage_verdicts.append(
            ProofVerdict.PROVEN if exact else ProofVerdict.DISPROVEN
        )
    if evidence_ids:
        linkage_verdict = _aggregate_verdicts(linkage_verdicts)
    else:
        linkage_verdict = (
            ProofVerdict.UNKNOWN if positive_claim else ProofVerdict.NOT_APPLICABLE
        )
    findings.append(
        _finding(
            registration,
            ChallengeKind.PROVENANCE_LINKAGE_INTEGRITY,
            linkage_verdict,
            evidence_fact_ids=evidence_ids,
            evidence_source_ids=evidence_sources,
            evidence_relationship_ids=relationship_ids,
            expected={
                "relation": MACHINE_EVIDENCE_RELATION,
                "relationship_count_per_evidence": 1,
                "provenance_binding": "EXACT",
            },
            observed=linkage_observed,
            explanation=(
                "Attempted to disprove each evidence identity by checking its exact "
                "graph relationship and provenance binding."
            ),
        )
    )

    # 5. Reject AI/model statements globally, even if a custom contract names them.
    authority_fact_ids = claim.supporting_fact_ids
    authority_observed: list[dict[str, Any]] = []
    authority_verdicts: list[ProofVerdict] = []
    for evidence_id in authority_fact_ids:
        try:
            node = graph.node(evidence_id)
        except FactModelError:
            authority_observed.append(
                {"availability": "MISSING", "evidence_fact_id": evidence_id}
            )
            authority_verdicts.append(ProofVerdict.UNKNOWN)
            continue
        source_types = sorted(item.source_type for item in node.provenance)
        prohibited = _is_ai_authority(node.node_type) or any(
            _is_ai_authority(item) for item in source_types
        )
        authority_observed.append(
            {
                "evidence_fact_id": evidence_id,
                "node_type": node.node_type,
                "prohibited_ai_authority": prohibited,
                "source_types": source_types,
            }
        )
        authority_verdicts.append(
            ProofVerdict.DISPROVEN if prohibited else ProofVerdict.PROVEN
        )
    authority_verdict = (
        _aggregate_verdicts(authority_verdicts)
        if authority_fact_ids
        else ProofVerdict.NOT_APPLICABLE
    )
    findings.append(
        _finding(
            registration,
            ChallengeKind.AI_AUTHORITY_BOUNDARY,
            authority_verdict,
            evidence_fact_ids=authority_fact_ids,
            evidence_source_ids=_node_sources(graph, authority_fact_ids),
            expected={"ai_or_llm_evidence_authority": "PROHIBITED"},
            observed=authority_observed,
            explanation=(
                "Attempted to disprove the non-AI authority boundary for every "
                "declared supporting fact and evidence source."
            ),
        )
    )

    # 6. Challenge every candidate against every explicit contract requirement.
    contract_observed: list[dict[str, Any]] = []
    satisfied_by_evidence: dict[str, list[str]] = {item: [] for item in evidence_ids}
    contract_verdicts: list[ProofVerdict] = []
    for requirement in registration.contract.evidence_requirements:
        matching_evidence_ids: list[str] = []
        requirement_assessments: list[dict[str, Any]] = []
        assessment_verdicts: list[ProofVerdict] = []
        for evidence_id in evidence_ids:
            try:
                node = graph.node(evidence_id)
            except FactModelError:
                requirement_assessments.append(
                    {"availability": "MISSING", "evidence_fact_id": evidence_id}
                )
                assessment_verdicts.append(ProofVerdict.UNKNOWN)
                continue
            result = node.value.get("result") if isinstance(node.value, Mapping) else None
            source_types = sorted(item.source_type for item in node.provenance)
            checks = {
                "accepted_result": result in requirement.accepted_results,
                "accepted_source_types": bool(source_types)
                and all(item in requirement.source_types for item in source_types),
                "current": node.freshness(current_sources) is Freshness.CURRENT,
                "node_type": node.node_type in requirement.node_types,
                "proven": node.status is FactStatus.PROVEN,
            }
            satisfies = all(checks.values())
            if satisfies:
                matching_evidence_ids.append(evidence_id)
                satisfied_by_evidence[evidence_id].append(requirement.requirement_id)
                assessment_verdict = ProofVerdict.PROVEN
            elif result in {"FAIL", "DISPROVEN"} or any(
                not checks[key]
                for key in ("accepted_source_types", "node_type", "proven")
            ):
                assessment_verdict = ProofVerdict.DISPROVEN
            else:
                assessment_verdict = ProofVerdict.UNKNOWN
            assessment_verdicts.append(assessment_verdict)
            requirement_assessments.append(
                {
                    "checks": checks,
                    "evidence_fact_id": evidence_id,
                    "observed_result": result,
                    "source_types": source_types,
                    "verdict": assessment_verdict.value,
                }
            )
        count_satisfied = len(matching_evidence_ids) >= requirement.minimum_count
        if count_satisfied:
            requirement_verdict = ProofVerdict.PROVEN
        elif any(item is ProofVerdict.DISPROVEN for item in assessment_verdicts):
            requirement_verdict = ProofVerdict.DISPROVEN
        else:
            requirement_verdict = ProofVerdict.UNKNOWN
        contract_verdicts.append(requirement_verdict)
        contract_observed.append(
            {
                "assessments": requirement_assessments,
                "matching_evidence_fact_ids": sorted(matching_evidence_ids),
                "minimum_count": requirement.minimum_count,
                "requirement_id": requirement.requirement_id,
                "verdict": requirement_verdict.value,
            }
        )
    uncovered: list[str] = []
    for evidence_id, requirement_ids in satisfied_by_evidence.items():
        if requirement_ids:
            continue
        try:
            uncovered_node = graph.node(evidence_id)
        except FactModelError:
            continue
        if (
            uncovered_node.status is FactStatus.PROVEN
            and uncovered_node.freshness(current_sources) is Freshness.CURRENT
        ):
            uncovered.append(evidence_id)
    uncovered.sort()
    if uncovered:
        contract_verdicts.append(ProofVerdict.DISPROVEN)
    if not evidence_ids and not positive_claim:
        contract_verdict = ProofVerdict.NOT_APPLICABLE
    else:
        contract_verdict = _aggregate_verdicts(contract_verdicts)
    findings.append(
        _finding(
            registration,
            ChallengeKind.CLAIM_CONTRACT_SATISFACTION,
            contract_verdict,
            evidence_fact_ids=evidence_ids,
            evidence_source_ids=evidence_sources,
            expected={
                "contract_id": registration.contract.contract_id,
                "domain": registration.contract.domain.value,
                "requirements": [
                    item.to_dict()
                    for item in registration.contract.evidence_requirements
                ],
                "uncovered_evidence_fact_ids": [],
            },
            observed={
                "requirements": contract_observed,
                "uncovered_evidence_fact_ids": uncovered,
            },
            explanation=(
                "Attempted to disprove the claim by applying every registered "
                "evidence requirement without narrative inference."
            ),
        )
    )

    evidence_assessments: list[dict[str, Any]] = []
    for evidence_id in evidence_ids:
        try:
            node = graph.node(evidence_id)
        except FactModelError:
            evidence_assessments.append(
                {
                    "availability": "MISSING",
                    "evidence_fact_id": evidence_id,
                    "freshness": "UNKNOWN",
                    "node_type": None,
                    "provenance": [],
                    "relationship_ids": [],
                    "status": None,
                }
            )
            continue
        matching_ids = sorted(
            str(edge["edge_id"])
            for edge in edges
            if edge["source_id"] == claim.status_fact_id
            and edge["target_id"] == evidence_id
            and edge["relation"] == MACHINE_EVIDENCE_RELATION
        )
        evidence_assessments.append(
            {
                "availability": "PRESENT",
                "evidence_fact_id": evidence_id,
                "freshness": node.freshness(current_sources).value,
                "node_type": node.node_type,
                "provenance": [
                    item.to_dict()
                    for item in sorted(node.provenance, key=lambda value: value.source_id)
                ],
                "relationship_ids": matching_ids,
                "status": node.status.value,
            }
        )
    verdict = _aggregate_claim_findings(findings)
    return ClaimReview(
        registration=registration,
        verdict=verdict,
        findings=tuple(findings),
        evidence_assessments=tuple(evidence_assessments),
    )


@dataclass(frozen=True)
class IndependentReviewReport:
    """Canonical evidence envelope for a deterministic independent review."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.independent-review-report.v1"

    fact_graph_digest: str
    source_snapshot_sha256: str
    reviews: tuple[ClaimReview, ...]

    def __post_init__(self) -> None:
        for field_name in ("fact_graph_digest", "source_snapshot_sha256"):
            value = getattr(self, field_name)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(item not in "0123456789abcdef" for item in value)
            ):
                raise IndependentReviewError(f"{field_name} must be a SHA-256 digest")
        reviews = _records(self.reviews, "reviews", ClaimReview, required=True)
        ordered = tuple(
            sorted(
                reviews,
                key=lambda item: (
                    item.registration.claim.claim_id,
                    item.registration.registration_id,
                ),
            )
        )
        claim_ids = [item.registration.claim.claim_id for item in ordered]
        if len(claim_ids) != len(set(claim_ids)):
            raise IndependentReviewError("registered claim IDs must be unique")
        object.__setattr__(self, "reviews", ordered)

    @property
    def overall_verdict(self) -> ProofVerdict:
        return _aggregate_verdicts(item.verdict for item in self.reviews)

    @property
    def open_blocker_finding_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                finding.finding_id
                for review in self.reviews
                for finding in review.findings
                if finding.blocker
            )
        )

    def identity_payload(self) -> dict[str, Any]:
        counts = {item.value: 0 for item in REVIEWER_VERDICTS}
        for review in self.reviews:
            counts[review.verdict.value] += 1
        return {
            "authority_boundary": {
                "adoption_authority": "SUPERVISOR_AND_HUMAN_GATES",
                "ai_authority": "NONE",
                "record_role": "DETERMINISTIC_EVIDENCE_REVIEW",
                "self_awarded_readiness": False,
            },
            "fact_graph_digest": self.fact_graph_digest,
            "open_blocker_finding_ids": list(self.open_blocker_finding_ids),
            "overall_verdict": self.overall_verdict.value,
            "reviews": [item.to_dict() for item in self.reviews],
            "schema_version": self.SCHEMA_VERSION,
            "source_snapshot_sha256": self.source_snapshot_sha256,
            "summary": {
                "claim_count": len(self.reviews),
                "finding_count": sum(len(item.findings) for item in self.reviews),
                "open_blocker_count": len(self.open_blocker_finding_ids),
                "verdict_counts": dict(sorted(counts.items())),
            },
        }

    @property
    def review_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def review_id(self) -> str:
        return f"INDEPENDENT-REVIEW-{self.review_sha256}"

    @property
    def provenance_binding(self) -> ProvenanceBinding:
        return ProvenanceBinding(
            source_id=f"SOURCE-INDEPENDENT-REVIEW-{self.review_sha256}",
            revision=f"FACT-GRAPH-{self.fact_graph_digest}",
            content_sha256=self.review_sha256,
            source_type="CANONICAL_MACHINE_EVIDENCE",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "provenance": self.provenance_binding.to_dict(),
            "review_id": self.review_id,
            "review_sha256": self.review_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def machine_evidence_fact(self) -> FactNode:
        """Authenticate the review observation without granting adoption authority."""
        return FactNode(
            node_id=f"FACT-INDEPENDENT-REVIEW-{self.review_sha256}",
            node_type="AUTHENTICATED_MACHINE_EVIDENCE",
            status=FactStatus.PROVEN,
            value={
                "open_blocker_count": len(self.open_blocker_finding_ids),
                "result": self.overall_verdict.value,
                "review_id": self.review_id,
            },
            provenance=(self.provenance_binding,),
            metadata={
                "authority": "MACHINE_OBSERVATION_ONLY",
                "limitation_ids": sorted(
                    {
                        limitation.limitation_id
                        for review in self.reviews
                        for limitation in review.registration.claim.limitations
                    }
                ),
            },
        )

    def evidence_graph(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=(self.machine_evidence_fact(),))


def run_independent_review(
    graph: EvidenceGraph,
    current_sources: Mapping[str, tuple[str, str]],
    registered_claims: Iterable[RegisteredClaim],
) -> IndependentReviewReport:
    """Apply every fixed skeptical challenge to every registered claim."""
    if not isinstance(graph, EvidenceGraph):
        raise IndependentReviewError("graph must use the canonical EvidenceGraph")
    try:
        sources = _normalize_current_sources(current_sources)
    except FactModelError as exc:
        raise IndependentReviewError(str(exc)) from exc
    registrations = _records(
        registered_claims, "registered_claims", RegisteredClaim, required=True
    )
    claim_ids = [item.claim.claim_id for item in registrations]
    if len(claim_ids) != len(set(claim_ids)):
        raise IndependentReviewError("registered claim IDs must be unique")
    reviews = tuple(
        _review_claim(graph, sources, item)
        for item in sorted(registrations, key=lambda value: value.claim.claim_id)
    )
    source_snapshot = {
        source_id: {"content_sha256": identity[1], "revision": identity[0]}
        for source_id, identity in sources.items()
    }
    return IndependentReviewReport(
        fact_graph_digest=str(graph.to_dict()["graph_digest"]),
        source_snapshot_sha256=canonical_sha256(source_snapshot),
        reviews=reviews,
    )


# A descriptive alias for callers that name the actor rather than the process.
run_independent_reviewer = run_independent_review


def _validate_identity(
    value: Mapping[str, Any], *, id_field: str, digest_field: str, prefix: str
) -> None:
    digest = value.get(digest_field)
    if not isinstance(digest, str) or len(digest) != 64:
        raise IndependentReviewError(f"{digest_field} must be a SHA-256 digest")
    if value.get(id_field) != f"{prefix}{digest}":
        raise IndependentReviewError(f"{id_field} does not match {digest_field}")
    core = {
        key: item
        for key, item in value.items()
        if key not in {id_field, digest_field}
    }
    if canonical_sha256(core) != digest:
        raise IndependentReviewError(f"{digest_field} is invalid")


def validate_independent_review_document(document: Mapping[str, Any]) -> bool:
    """Validate canonical identity, typed verdicts, ordering, and blockers."""
    expected_fields = {
        "authority_boundary",
        "fact_graph_digest",
        "open_blocker_finding_ids",
        "overall_verdict",
        "provenance",
        "review_id",
        "review_sha256",
        "reviews",
        "schema_version",
        "source_snapshot_sha256",
        "summary",
    }
    if not isinstance(document, Mapping) or set(document) != expected_fields:
        raise IndependentReviewError("independent-review fields do not match the contract")
    if document.get("schema_version") != IndependentReviewReport.SCHEMA_VERSION:
        raise IndependentReviewError("unsupported independent-review schema_version")
    if document.get("authority_boundary") != {
        "adoption_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "DETERMINISTIC_EVIDENCE_REVIEW",
        "self_awarded_readiness": False,
    }:
        raise IndependentReviewError("independent-review authority boundary is invalid")
    core = {
        key: item
        for key, item in document.items()
        if key not in {"provenance", "review_id", "review_sha256"}
    }
    digest = document.get("review_sha256")
    if not isinstance(digest, str) or canonical_sha256(core) != digest:
        raise IndependentReviewError("review_sha256 is invalid")
    if document.get("review_id") != f"INDEPENDENT-REVIEW-{digest}":
        raise IndependentReviewError("review_id is invalid")
    for digest_field in ("fact_graph_digest", "source_snapshot_sha256"):
        value = str(document.get(digest_field, ""))
        if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
            raise IndependentReviewError(f"{digest_field} must be a SHA-256 digest")
    provenance = document.get("provenance")
    if not isinstance(provenance, Mapping):
        raise IndependentReviewError("review provenance is invalid")
    try:
        binding = ProvenanceBinding(
            source_id=str(provenance.get("source_id", "")),
            revision=str(provenance.get("revision", "")),
            content_sha256=str(provenance.get("content_sha256", "")),
            source_type=str(provenance.get("source_type", "")),
        )
    except FactModelError as exc:
        raise IndependentReviewError("review provenance is invalid") from exc
    if binding.content_sha256 != digest or binding.source_type != "CANONICAL_MACHINE_EVIDENCE":
        raise IndependentReviewError("review provenance does not bind the review digest")
    if binding.source_id != f"SOURCE-INDEPENDENT-REVIEW-{digest}" or binding.revision != (
        f"FACT-GRAPH-{document['fact_graph_digest']}"
    ):
        raise IndependentReviewError("review provenance identity is invalid")

    reviews = document.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise IndependentReviewError("reviews must be a non-empty list")
    claim_ids: list[str] = []
    all_blockers: list[str] = []
    verdicts: list[ProofVerdict] = []
    finding_count = 0
    expected_review_fields = {
        "capability_id",
        "claim_id",
        "claim_text",
        "contract",
        "declared_status",
        "evidence_assessments",
        "findings",
        "limitations",
        "open_blocker_finding_ids",
        "registration_id",
        "review_id",
        "review_sha256",
        "verdict",
    }
    expected_finding_fields = {
        "blocker",
        "challenge",
        "claim_id",
        "evidence_fact_ids",
        "evidence_relationship_ids",
        "evidence_source_ids",
        "expected",
        "explanation",
        "finding_id",
        "finding_sha256",
        "limitation_ids",
        "observed",
        "severity",
        "verdict",
    }
    for review in reviews:
        if not isinstance(review, Mapping) or set(review) != expected_review_fields:
            raise IndependentReviewError("serialized claim review is invalid")
        _validate_identity(
            review,
            id_field="review_id",
            digest_field="review_sha256",
            prefix="CLAIM-REVIEW-",
        )
        claim_id = str(review.get("claim_id", ""))
        try:
            _public_identifier(claim_id, "claim_id")
            verdict = ProofVerdict(str(review.get("verdict", "")))
        except (FactModelError, ValueError) as exc:
            raise IndependentReviewError("serialized claim review is invalid") from exc
        if verdict not in REVIEWER_VERDICTS:
            raise IndependentReviewError("claim verdict is outside reviewer vocabulary")
        verdicts.append(verdict)
        claim_ids.append(claim_id)
        findings = review.get("findings")
        if not isinstance(findings, list) or len(findings) != len(CHALLENGE_ORDER):
            raise IndependentReviewError("claim review must preserve every challenge finding")
        finding_count += len(findings)
        challenges: list[ChallengeKind] = []
        derived_verdicts: list[ProofVerdict] = []
        derived_blockers: list[str] = []
        for finding in findings:
            if not isinstance(finding, Mapping) or set(finding) != expected_finding_fields:
                raise IndependentReviewError("serialized finding is invalid")
            _validate_identity(
                finding,
                id_field="finding_id",
                digest_field="finding_sha256",
                prefix="REVIEW-FINDING-",
            )
            try:
                challenge = ChallengeKind(str(finding.get("challenge", "")))
                finding_verdict = ProofVerdict(str(finding.get("verdict", "")))
                severity = FindingSeverity(str(finding.get("severity", "")))
            except ValueError as exc:
                raise IndependentReviewError("serialized finding vocabulary is invalid") from exc
            if finding_verdict not in REVIEWER_VERDICTS:
                raise IndependentReviewError("finding verdict is outside reviewer vocabulary")
            blocker = finding.get("blocker")
            if not isinstance(blocker, bool):
                raise IndependentReviewError("serialized blocker must be a boolean")
            if finding_verdict in {ProofVerdict.PROVEN, ProofVerdict.NOT_APPLICABLE}:
                if blocker or severity is not FindingSeverity.INFO:
                    raise IndependentReviewError("positive finding cannot be a blocker")
            if blocker:
                derived_blockers.append(str(finding["finding_id"]))
            challenges.append(challenge)
            derived_verdicts.append(finding_verdict)
        if challenges != list(CHALLENGE_ORDER):
            raise IndependentReviewError("skeptical challenges are not canonically ordered")
        if (
            challenges[0] is ChallengeKind.STATUS_FACT_INTEGRITY
            and derived_verdicts[0] is ProofVerdict.NOT_APPLICABLE
        ):
            derived_claim_verdict = ProofVerdict.NOT_APPLICABLE
        else:
            derived_claim_verdict = _aggregate_verdicts(derived_verdicts)
        if verdict is not derived_claim_verdict:
            raise IndependentReviewError("claim verdict is not evidence-derived")
        if review.get("open_blocker_finding_ids") != derived_blockers:
            raise IndependentReviewError("claim blockers were not preserved")
        all_blockers.extend(derived_blockers)
    if claim_ids != sorted(claim_ids) or len(claim_ids) != len(set(claim_ids)):
        raise IndependentReviewError("claim reviews are not uniquely and canonically ordered")
    if document.get("open_blocker_finding_ids") != sorted(all_blockers):
        raise IndependentReviewError("report blockers were not preserved")
    overall = _aggregate_verdicts(verdicts)
    if document.get("overall_verdict") != overall.value:
        raise IndependentReviewError("overall verdict is not evidence-derived")
    counts = {item.value: 0 for item in REVIEWER_VERDICTS}
    for verdict in verdicts:
        counts[verdict.value] += 1
    expected_summary = {
        "claim_count": len(reviews),
        "finding_count": finding_count,
        "open_blocker_count": len(all_blockers),
        "verdict_counts": dict(sorted(counts.items())),
    }
    if document.get("summary") != expected_summary:
        raise IndependentReviewError("review summary is not evidence-derived")
    return True


validate_independent_reviewer_evidence = validate_independent_review_document


def write_independent_review_evidence(
    report: IndependentReviewReport, path: Path
) -> dict[str, Any]:
    """Write canonical portable evidence and return a non-authoritative summary."""
    if not isinstance(report, IndependentReviewReport):
        raise IndependentReviewError("report must use IndependentReviewReport")
    if not isinstance(path, Path):
        raise IndependentReviewError("path must use pathlib.Path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return {
        "evidence_artifact": path.name,
        "open_blocker_count": len(report.open_blocker_finding_ids),
        "review_id": report.review_id,
        "status": report.overall_verdict.value,
    }
