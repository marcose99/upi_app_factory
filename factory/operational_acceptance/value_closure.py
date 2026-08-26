"""Deterministic enterprise value closure over the canonical evidence graph.

This module is a projection, not a second fact store.  Every closure status is
bound to an M2.4 ``FactNode`` and every PROVEN claim additionally requires
current, provenance-bound machine evidence.  Public eligibility is derived;
neither narrative text nor an AI-originated proposal can grant it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from typing import Any, ClassVar, Iterable, Mapping, cast

from factory.documentation import (
    Claim,
    EvidenceGraph,
    FactStatus,
    Freshness,
    canonical_json,
    canonical_sha256,
    validate_factuality,
)
from factory.documentation.facts import FactModelError, _identifier


class ValueClosureError(FactModelError):
    """Raised when capability closure would overstate authenticated facts."""


class ValueClosureStatus(str, Enum):
    """Closed vocabulary for enterprise value truth."""

    PROVEN = "PROVEN"
    PARTIAL = "PARTIAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NOT_YET_MEASURED = "NOT_YET_MEASURED"
    UNKNOWN_EXPLICIT = "UNKNOWN_EXPLICIT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BusinessValueDimension(str, Enum):
    """Stable, non-numeric description of why a capability matters."""

    DELIVERY_UTILITY = "DELIVERY_UTILITY"
    RISK_AND_CONTROL_CONFIDENCE = "RISK_AND_CONTROL_CONFIDENCE"
    CHANGE_EFFICIENCY = "CHANGE_EFFICIENCY"
    CONTINUITY_AND_RESILIENCE = "CONTINUITY_AND_RESILIENCE"
    HUMAN_DECISION_CONFIDENCE = "HUMAN_DECISION_CONFIDENCE"
    DEMONSTRATION_TRUST = "DEMONSTRATION_TRUST"


class PublicClaimEligibility(str, Enum):
    """Derived public-use decision with an explicit fail-closed reason."""

    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE_BY_POLICY = "NOT_ELIGIBLE_BY_POLICY"
    NOT_ELIGIBLE_NOT_PROVEN = "NOT_ELIGIBLE_NOT_PROVEN"


REQUIRED_CAPABILITY_IDS = frozenset(
    {
        "CAP-APPLICATION-ENGINEERING",
        "CAP-UPI-PAYMENT-PORTFOLIO",
        "CAP-SECURITY-GOVERNANCE",
        "CAP-MAINTAINABILITY",
        "CAP-REPRODUCIBILITY",
        "CAP-OPERATIONAL-ACCEPTANCE",
        "CAP-CLEAN-ROOM-RECONSTRUCTION",
        "CAP-EXTERNAL-DOMAIN-CONTINUITY",
        "CAP-SUPPLY-CHAIN-DEPENDENCY-CONTINUITY",
        "CAP-HUMAN-REVIEW",
        "CAP-GOLDEN-DEMO-READINESS",
    }
)

MACHINE_EVIDENCE_NODE_TYPES = frozenset(
    {
        "AUTHENTICATED_MACHINE_EVIDENCE",
        "EXECUTABLE_EVIDENCE",
        "MACHINE_EVIDENCE",
    }
)
MACHINE_EVIDENCE_SOURCE_TYPES = frozenset(
    {
        "AUTHENTICATED_MACHINE_RECORD",
        "CANONICAL_MACHINE_EVIDENCE",
        "EXECUTABLE_TEST_RESULT",
        "MACHINE_EXECUTION_RECORD",
    }
)
CAPABILITY_STATUS_NODE_TYPES = frozenset(
    {
        "APPLICATION_CAPABILITY",
        "CAPABILITY",
        "FACTORY_CAPABILITY",
        "VALUE_CLOSURE_CLAIM",
    }
)
MACHINE_EVIDENCE_RELATION = "VERIFIED_BY"

_PUBLIC_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_PERSONAL_OR_LOCAL_PATH = re.compile(
    r"(?:file://|(?:^|[\s'\"(])/(?:home|root|Users|tmp|workspace|mnt)/|"
    r"[A-Za-z]:\\(?:Users|Temp)\\)",
    re.IGNORECASE,
)
_TRANSIENT_CAMPAIGN_ID = re.compile(
    r"\bcampaign(?:[_ -]?id)?\s*[:=]\s*[A-Za-z0-9._:-]+", re.IGNORECASE
)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(?:api[_ -]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE
)


def _public_identifier(value: str, field_name: str) -> str:
    try:
        normalized = _identifier(value, field_name)
    except FactModelError as exc:
        raise ValueClosureError(str(exc)) from exc
    if not _PUBLIC_IDENTIFIER.fullmatch(normalized):
        raise ValueClosureError(f"{field_name} must be a public-safe stable identifier")
    if "campaign" in normalized.lower():
        raise ValueClosureError(f"{field_name} must not contain a transient campaign identity")
    if re.search(r"(?:api[_-]?key|password|secret|token):", normalized, re.IGNORECASE):
        raise ValueClosureError(f"{field_name} must not contain secret material")
    return normalized


def _public_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueClosureError(f"{field_name} must be non-empty normalized text")
    if _PERSONAL_OR_LOCAL_PATH.search(value):
        raise ValueClosureError(f"{field_name} must not contain a personal or local path")
    if _TRANSIENT_CAMPAIGN_ID.search(value):
        raise ValueClosureError(f"{field_name} must not contain a transient campaign identity")
    if _SECRET_ASSIGNMENT.search(value):
        raise ValueClosureError(f"{field_name} must not contain secret material")
    return value


def _identities(values: Iterable[str], field_name: str, *, required: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueClosureError(f"{field_name} must be a collection")
    try:
        normalized = tuple(_public_identifier(value, field_name) for value in values)
    except TypeError as exc:
        raise ValueClosureError(f"{field_name} must be a collection") from exc
    if required and not normalized:
        raise ValueClosureError(f"{field_name} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise ValueClosureError(f"{field_name} must contain unique identities")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class Limitation:
    """A stable, human-visible boundary on one capability claim."""

    limitation_id: str
    text: str

    def __post_init__(self) -> None:
        _public_identifier(self.limitation_id, "limitation_id")
        _public_text(self.text, "limitation text")

    def to_dict(self) -> dict[str, str]:
        return {"limitation_id": self.limitation_id, "text": self.text}


@dataclass(frozen=True)
class CapabilityClaim:
    """One typed value claim whose truth remains in the fact graph."""

    capability_id: str
    claim_id: str
    claim_text: str
    status: ValueClosureStatus
    status_fact_id: str
    business_value_dimension: BusinessValueDimension
    supporting_fact_ids: tuple[str, ...]
    machine_evidence_fact_ids: tuple[str, ...] = ()
    limitations: tuple[Limitation, ...] = ()
    public_claim_candidate: bool = False

    def __post_init__(self) -> None:
        _public_identifier(self.capability_id, "capability_id")
        _public_identifier(self.claim_id, "claim_id")
        _public_identifier(self.status_fact_id, "status_fact_id")
        _public_text(self.claim_text, "claim_text")
        if not isinstance(self.status, ValueClosureStatus):
            raise ValueClosureError("status must use ValueClosureStatus")
        if not isinstance(self.business_value_dimension, BusinessValueDimension):
            raise ValueClosureError(
                "business_value_dimension must use BusinessValueDimension"
            )
        if not isinstance(self.public_claim_candidate, bool):
            raise ValueClosureError("public_claim_candidate must be an explicit boolean")
        supporting = _identities(
            self.supporting_fact_ids, "supporting_fact_ids", required=True
        )
        evidence = _identities(
            self.machine_evidence_fact_ids,
            "machine_evidence_fact_ids",
            required=False,
        )
        if self.status_fact_id not in supporting:
            raise ValueClosureError("status_fact_id must be included in supporting_fact_ids")
        if not set(evidence).issubset(supporting):
            raise ValueClosureError(
                "machine_evidence_fact_ids must be included in supporting_fact_ids"
            )
        if isinstance(self.limitations, (str, bytes)):
            raise ValueClosureError("limitations must be a collection")
        limitations = tuple(self.limitations)
        if not limitations or any(not isinstance(item, Limitation) for item in limitations):
            raise ValueClosureError("claims require explicit Limitation values")
        limitation_ids = [item.limitation_id for item in limitations]
        if len(limitation_ids) != len(set(limitation_ids)):
            raise ValueClosureError("limitation IDs must be unique within a claim")
        object.__setattr__(self, "supporting_fact_ids", supporting)
        object.__setattr__(self, "machine_evidence_fact_ids", evidence)
        object.__setattr__(
            self, "limitations", tuple(sorted(limitations, key=lambda item: item.limitation_id))
        )

    @property
    def public_claim_eligibility(self) -> PublicClaimEligibility:
        if self.status is not ValueClosureStatus.PROVEN:
            return PublicClaimEligibility.NOT_ELIGIBLE_NOT_PROVEN
        if not self.public_claim_candidate:
            return PublicClaimEligibility.NOT_ELIGIBLE_BY_POLICY
        return PublicClaimEligibility.ELIGIBLE

    def to_dict(
        self, *, evidence_provenance: Iterable[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return {
            "business_value_dimension": self.business_value_dimension.value,
            "capability_id": self.capability_id,
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "evidence_provenance": [dict(item) for item in evidence_provenance],
            "limitations": [item.to_dict() for item in self.limitations],
            "machine_evidence_fact_ids": list(self.machine_evidence_fact_ids),
            "public_claim_candidate": self.public_claim_candidate,
            "public_claim_eligibility": self.public_claim_eligibility.value,
            "status": self.status.value,
            "status_fact_id": self.status_fact_id,
            "supporting_fact_ids": list(self.supporting_fact_ids),
        }


def _normalize_current_sources(
    current_sources: Mapping[str, tuple[str, str]],
) -> dict[str, tuple[str, str]]:
    if not isinstance(current_sources, Mapping):
        raise ValueClosureError("current_sources must be a source identity mapping")
    normalized: dict[str, tuple[str, str]] = {}
    for source_id, identity in current_sources.items():
        _public_identifier(source_id, "current source_id")
        if (
            not isinstance(identity, tuple)
            or len(identity) != 2
            or not all(isinstance(item, str) and item for item in identity)
        ):
            raise ValueClosureError(
                "current source identities must be (revision, content_sha256) tuples"
            )
        revision, content_sha256 = identity
        _public_identifier(revision, "current source revision")
        if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise ValueClosureError("current source content identity must be a SHA-256 digest")
        normalized[source_id] = (revision, content_sha256)
    return dict(sorted(normalized.items()))


@dataclass(frozen=True)
class ValueClosureInventory:
    """Complete, stable inventory derived from facts plus current source identity."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.enterprise-value-closure.v1"

    graph: EvidenceGraph = field(repr=False, compare=False)
    current_sources: Mapping[str, tuple[str, str]] = field(repr=False, compare=False)
    claims: tuple[CapabilityClaim, ...]
    _document: Mapping[str, Any] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.graph, EvidenceGraph):
            raise ValueClosureError("graph must be the canonical EvidenceGraph")
        sources = _normalize_current_sources(self.current_sources)
        if isinstance(self.claims, (str, bytes)):
            raise ValueClosureError("claims must be a collection")
        claims = tuple(self.claims)
        if any(not isinstance(item, CapabilityClaim) for item in claims):
            raise ValueClosureError("claims must contain CapabilityClaim values")
        if not claims:
            raise ValueClosureError("value closure requires capability claims")

        claim_ids = [item.claim_id for item in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueClosureError("claim IDs must be unique")
        pairs = [(item.capability_id, item.claim_id) for item in claims]
        if len(pairs) != len(set(pairs)):
            raise ValueClosureError("capability/claim pairs must be unique")
        missing = sorted(REQUIRED_CAPABILITY_IDS - {item.capability_id for item in claims})
        if missing:
            raise ValueClosureError(
                "value closure is missing required capabilities: " + ", ".join(missing)
            )

        ordered = tuple(sorted(claims, key=lambda item: (item.capability_id, item.claim_id)))
        for item in ordered:
            self._validate_claim(item, sources)
        object.__setattr__(self, "current_sources", sources)
        object.__setattr__(self, "claims", ordered)
        object.__setattr__(self, "_document", self._build_document(sources, ordered))

    def _validate_claim(
        self, item: CapabilityClaim, current_sources: Mapping[str, tuple[str, str]]
    ) -> None:
        try:
            status_node = self.graph.node(item.status_fact_id)
        except FactModelError as exc:
            raise ValueClosureError(str(exc)) from exc
        if status_node.status.value != item.status.value:
            raise ValueClosureError(
                f"claim {item.claim_id} status does not match {item.status_fact_id}"
            )
        if status_node.node_type not in CAPABILITY_STATUS_NODE_TYPES:
            raise ValueClosureError(
                f"claim {item.claim_id} status is not a canonical capability fact"
            )
        for fact_id in item.supporting_fact_ids:
            try:
                self.graph.node(fact_id)
            except FactModelError as exc:
                raise ValueClosureError(str(exc)) from exc

        if item.status is ValueClosureStatus.PROVEN:
            if not item.machine_evidence_fact_ids:
                raise ValueClosureError(
                    f"PROVEN claim {item.claim_id} requires machine evidence"
                )
            try:
                validate_factuality(
                    [Claim(item.claim_id, item.claim_text, item.supporting_fact_ids)],
                    self.graph,
                    current_sources,
                )
            except FactModelError as exc:
                raise ValueClosureError(str(exc)) from exc
        elif item.status is ValueClosureStatus.PARTIAL and not item.machine_evidence_fact_ids:
            raise ValueClosureError(
                f"PARTIAL claim {item.claim_id} requires evidence for the proven portion"
            )

        for evidence_id in item.machine_evidence_fact_ids:
            evidence = self.graph.node(evidence_id)
            if evidence.node_type not in MACHINE_EVIDENCE_NODE_TYPES:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} is not machine evidence"
                )
            if evidence.status is not FactStatus.PROVEN:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} is not PROVEN"
                )
            if not isinstance(evidence.value, Mapping) or evidence.value.get("result") not in {
                "PASS",
                "PROVEN",
            }:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} lacks a passing result"
                )
            if evidence.freshness(current_sources) is not Freshness.CURRENT:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} is stale"
                )
            if any(
                binding.source_type not in MACHINE_EVIDENCE_SOURCE_TYPES
                for binding in evidence.provenance
            ):
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} lacks an "
                    "authenticated machine source type"
                )
            evidence_relationships = [
                edge
                for edge in self.graph.to_dict()["edges"]
                if edge["source_id"] == item.status_fact_id
                and edge["relation"] == MACHINE_EVIDENCE_RELATION
                and edge["target_id"] == evidence_id
            ]
            if not evidence_relationships:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} is not linked "
                    f"by {MACHINE_EVIDENCE_RELATION}"
                )
            if len(evidence_relationships) != 1:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} has ambiguous "
                    "evidence relationships"
                )
            if set(evidence_relationships[0]["provenance_ids"]) != {
                binding.source_id for binding in evidence.provenance
            }:
                raise ValueClosureError(
                    f"claim {item.claim_id} evidence {evidence_id} relationship "
                    "does not bind its exact provenance"
                )

    def _evidence_provenance(self, item: CapabilityClaim) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for evidence_id in item.machine_evidence_fact_ids:
            node = self.graph.node(evidence_id)
            relationship = next(
                edge
                for edge in self.graph.to_dict()["edges"]
                if edge["source_id"] == item.status_fact_id
                and edge["relation"] == MACHINE_EVIDENCE_RELATION
                and edge["target_id"] == evidence_id
            )
            for binding in sorted(node.provenance, key=lambda value: value.source_id):
                _public_identifier(binding.revision, "evidence revision")
                _public_identifier(binding.source_type, "evidence source_type")
                result.append(
                    {
                        "content_sha256": binding.content_sha256,
                        "evidence_fact_id": evidence_id,
                        "relationship_id": relationship["edge_id"],
                        "relationship": MACHINE_EVIDENCE_RELATION,
                        "revision": binding.revision,
                        "source_id": binding.source_id,
                        "source_type": binding.source_type,
                    }
                )
        return result

    def _build_document(
        self,
        sources: Mapping[str, tuple[str, str]],
        claims: tuple[CapabilityClaim, ...],
    ) -> Mapping[str, Any]:
        statuses = {status.value: 0 for status in ValueClosureStatus}
        entries: list[dict[str, Any]] = []
        for item in claims:
            statuses[item.status.value] += 1
            entries.append(
                item.to_dict(evidence_provenance=self._evidence_provenance(item))
            )
        source_snapshot = {
            source_id: {"content_sha256": identity[1], "revision": identity[0]}
            for source_id, identity in sources.items()
        }
        core = {
            "capabilities": entries,
            "fact_graph_digest": self.graph.to_dict()["graph_digest"],
            "required_capability_ids": sorted(REQUIRED_CAPABILITY_IDS),
            "schema_version": self.SCHEMA_VERSION,
            "source_snapshot_sha256": canonical_sha256(source_snapshot),
            "status_summary": statuses,
        }
        inventory_digest = canonical_sha256(core)
        return cast(
            Mapping[str, Any],
            json.loads(
                canonical_json(
                    {
                        **core,
                        "inventory_digest": inventory_digest,
                        "inventory_id": f"VALUE-CLOSURE-{inventory_digest}",
                    }
                )
            ),
        )

    @property
    def inventory_digest(self) -> str:
        return str(self._document["inventory_digest"])

    @property
    def inventory_id(self) -> str:
        return str(self._document["inventory_id"])

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(canonical_json(self._document)))

    def to_json(self) -> str:
        return canonical_json(self._document)

    def public_claims(self) -> dict[str, Any]:
        """Project only eligible claims while retaining their limitations."""
        claims = [
            {
                "capability_id": item.capability_id,
                "claim_id": item.claim_id,
                "claim_text": item.claim_text,
                "limitations": [value.to_dict() for value in item.limitations],
                "source_inventory_id": self.inventory_id,
                "status": item.status.value,
            }
            for item in self.claims
            if item.public_claim_eligibility is PublicClaimEligibility.ELIGIBLE
        ]
        core = {
            "claims": claims,
            "schema_version": "upi_app_factory.public-value-claims.v1",
            "source_inventory_digest": self.inventory_digest,
        }
        return {**core, "projection_digest": canonical_sha256(core)}


def validate_value_closure_document(document: Mapping[str, Any]) -> bool:
    """Validate canonical integrity and minimum fail-closed publication semantics."""
    expected_document_fields = {
        "capabilities",
        "fact_graph_digest",
        "inventory_digest",
        "inventory_id",
        "required_capability_ids",
        "schema_version",
        "source_snapshot_sha256",
        "status_summary",
    }
    if set(document) != expected_document_fields:
        raise ValueClosureError("value-closure document fields do not match the contract")
    if document.get("schema_version") != ValueClosureInventory.SCHEMA_VERSION:
        raise ValueClosureError("unsupported value-closure schema_version")
    for digest_field in ("fact_graph_digest", "source_snapshot_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(document.get(digest_field, ""))):
            raise ValueClosureError(f"{digest_field} must be a SHA-256 digest")
    if document.get("required_capability_ids") != sorted(REQUIRED_CAPABILITY_IDS):
        raise ValueClosureError("required_capability_ids do not match the closed contract")
    supplied_digest = document.get("inventory_digest")
    supplied_id = document.get("inventory_id")
    if not isinstance(supplied_digest, str) or supplied_id != f"VALUE-CLOSURE-{supplied_digest}":
        raise ValueClosureError("value-closure identity is invalid")
    core = {
        key: value
        for key, value in document.items()
        if key not in {"inventory_digest", "inventory_id"}
    }
    if supplied_digest != canonical_sha256(core):
        raise ValueClosureError("value-closure digest is invalid")
    entries = document.get("capabilities")
    if not isinstance(entries, list):
        raise ValueClosureError("capabilities must be a list")
    order = [
        (str(item.get("capability_id", "")), str(item.get("claim_id", "")))
        for item in entries
        if isinstance(item, Mapping)
    ]
    if len(order) != len(entries) or order != sorted(order) or len(order) != len(set(order)):
        raise ValueClosureError("capability claims are not uniquely and canonically ordered")
    covered = {capability_id for capability_id, _claim_id in order}
    if not REQUIRED_CAPABILITY_IDS.issubset(covered):
        raise ValueClosureError("value closure does not cover every required capability")
    expected_entry_fields = {
        "business_value_dimension",
        "capability_id",
        "claim_id",
        "claim_text",
        "evidence_provenance",
        "limitations",
        "machine_evidence_fact_ids",
        "public_claim_candidate",
        "public_claim_eligibility",
        "status",
        "status_fact_id",
        "supporting_fact_ids",
    }
    for item in entries:
        if set(item) != expected_entry_fields:
            raise ValueClosureError("capability claim fields do not match the contract")
        status = item.get("status")
        evidence_ids = item.get("machine_evidence_fact_ids")
        eligibility = item.get("public_claim_eligibility")
        _public_identifier(str(item.get("capability_id", "")), "capability_id")
        _public_identifier(str(item.get("claim_id", "")), "claim_id")
        _public_identifier(str(item.get("status_fact_id", "")), "status_fact_id")
        try:
            BusinessValueDimension(str(item.get("business_value_dimension", "")))
        except ValueError as exc:
            raise ValueClosureError("business_value_dimension is invalid") from exc
        supporting_ids = item.get("supporting_fact_ids")
        if (
            not isinstance(supporting_ids, list)
            or supporting_ids != sorted(supporting_ids)
            or len(supporting_ids) != len(set(supporting_ids))
        ):
            raise ValueClosureError("supporting_fact_ids are not canonical")
        if item["status_fact_id"] not in supporting_ids:
            raise ValueClosureError("status_fact_id is not a supporting fact")
        for fact_id in supporting_ids:
            _public_identifier(str(fact_id), "supporting_fact_id")
        if (
            not isinstance(evidence_ids, list)
            or evidence_ids != sorted(evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))
            or not set(evidence_ids).issubset(supporting_ids)
        ):
            raise ValueClosureError("machine_evidence_fact_ids are not canonical")
        for evidence_id in evidence_ids:
            _public_identifier(str(evidence_id), "machine_evidence_fact_id")
        if status == ValueClosureStatus.PROVEN.value and not evidence_ids:
            raise ValueClosureError("serialized PROVEN claim lacks machine evidence")
        candidate = item.get("public_claim_candidate")
        if not isinstance(candidate, bool):
            raise ValueClosureError("public_claim_candidate must be an explicit boolean")
        expected_eligibility = (
            PublicClaimEligibility.NOT_ELIGIBLE_NOT_PROVEN.value
            if status != "PROVEN"
            else (
                PublicClaimEligibility.ELIGIBLE.value
                if candidate
                else PublicClaimEligibility.NOT_ELIGIBLE_BY_POLICY.value
            )
        )
        if eligibility != expected_eligibility:
            raise ValueClosureError("public claim eligibility is not evidence-derived")
        _public_text(str(item.get("claim_text", "")), "claim_text")
        limitations = item.get("limitations")
        if not isinstance(limitations, list) or not limitations:
            raise ValueClosureError("serialized claim lacks explicit limitations")
        limitation_ids: list[str] = []
        for limitation in limitations:
            if not isinstance(limitation, Mapping):
                raise ValueClosureError("serialized limitation is invalid")
            if set(limitation) != {"limitation_id", "text"}:
                raise ValueClosureError("limitation fields do not match the contract")
            limitation_ids.append(
                _public_identifier(
                    str(limitation.get("limitation_id", "")), "limitation_id"
                )
            )
            _public_text(str(limitation.get("text", "")), "limitation text")
        if limitation_ids != sorted(limitation_ids) or len(limitation_ids) != len(
            set(limitation_ids)
        ):
            raise ValueClosureError("limitations are not uniquely and canonically ordered")
        provenance = item.get("evidence_provenance")
        if not isinstance(provenance, list):
            raise ValueClosureError("evidence_provenance must be a list")
        provenance_evidence_ids: set[str] = set()
        for binding in provenance:
            if not isinstance(binding, Mapping):
                raise ValueClosureError("serialized evidence provenance is invalid")
            if set(binding) != {
                "content_sha256",
                "evidence_fact_id",
                "relationship",
                "relationship_id",
                "revision",
                "source_id",
                "source_type",
            }:
                raise ValueClosureError(
                    "evidence provenance fields do not match the contract"
                )
            provenance_evidence_ids.add(
                _public_identifier(
                    str(binding.get("evidence_fact_id", "")), "evidence_fact_id"
                )
            )
            _public_identifier(str(binding.get("source_id", "")), "source_id")
            _public_identifier(
                str(binding.get("relationship_id", "")), "relationship_id"
            )
            if binding.get("relationship") != MACHINE_EVIDENCE_RELATION:
                raise ValueClosureError("serialized evidence relationship is invalid")
            _public_identifier(str(binding.get("revision", "")), "revision")
            source_type = _public_identifier(
                str(binding.get("source_type", "")), "source_type"
            )
            if source_type not in MACHINE_EVIDENCE_SOURCE_TYPES:
                raise ValueClosureError("serialized evidence is not from a machine source")
            if not re.fullmatch(r"[0-9a-f]{64}", str(binding.get("content_sha256", ""))):
                raise ValueClosureError("serialized evidence provenance digest is invalid")
        if set(evidence_ids) != provenance_evidence_ids:
            raise ValueClosureError("machine evidence lacks exact provenance coverage")
    expected_summary = {status.value: 0 for status in ValueClosureStatus}
    for item in entries:
        status = str(item["status"])
        if status not in expected_summary:
            raise ValueClosureError("serialized claim has an invalid status")
        expected_summary[status] += 1
    if document.get("status_summary") != expected_summary:
        raise ValueClosureError("status_summary does not match capability claims")
    return True
