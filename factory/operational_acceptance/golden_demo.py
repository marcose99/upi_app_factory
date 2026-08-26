"""Canonical Golden Demo dossier and deterministic human projection.

The dossier composes existing fact, operational-acceptance, independent-review,
portfolio, and governance-evolution evidence.  It is deliberately a projection:
it cannot create a fact, promote governance, accept a delivery, or grant an AI
authority.  Human HTML is rendered only from validated canonical JSON and can
be checked byte-for-byte against that source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, ClassVar, Iterable, Mapping, cast

from factory.documentation import (
    FactStatus,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.documentation.facts import FactModelError
from factory.governance_evolution import (
    ExecutionFingerprint,
    GovernanceSnapshot,
    ImpactProjection,
    SemanticDiff,
    project_impact,
)

from .failure_recovery import ProofVerdict
from .harness import (
    AcceptanceStatus,
    ArtifactAvailability,
    OperationalAcceptanceEvidence,
    validate_operational_acceptance_evidence,
)
from .independent_reviewer import (
    IndependentReviewReport,
    REVIEWER_VERDICTS,
    validate_independent_review_document,
)
from .value_closure import (
    BusinessValueDimension,
    MACHINE_EVIDENCE_SOURCE_TYPES,
    PublicClaimEligibility,
    ValueClosureInventory,
    ValueClosureStatus,
    _public_identifier,
    _public_text,
    validate_value_closure_document,
)


class GoldenDemoError(FactModelError):
    """Raised when a dossier or projection would overstate its source evidence."""


PORTFOLIO_SCHEMA_VERSION = "upi-app-factory.portfolio-acceptance.v1"
PORTFOLIO_APPLICATION_COUNT = 8
GOVERNANCE_DEMONSTRATION_CLASSIFICATION = (
    "SYNTHETIC_GOVERNED_CHANGE_DEMONSTRATION"
)
CONTROLLED_EVOLUTION_RULE = "NEW_SNAPSHOT_AND_NEW_EXECUTION_FINGERPRINT_REQUIRED"

MANDATORY_NONCLAIMS = (
    "No live payment authority is claimed.",
    "No production deployment or production readiness is claimed.",
    "No certification is claimed.",
    "No NPCI, RBI, or other regulatory approval is claimed.",
    "The governance change shown is synthetic and is not a live NPCI or RBI change.",
    "This dossier and its human projection grant no delivery or acceptance authority.",
)

JOURNEY_STAGE_IDS = (
    "REQUIREMENT",
    "APPLICATION_ENGINEERING",
    "PRODUCT_ARTIFACTS_AND_TESTS",
    "QUALIFICATION_AND_REVIEW",
    "GOVERNANCE_CHANGE_AND_IMPACT",
    "CONTROLLED_EVOLUTION",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_PUBLIC_VALUE = re.compile(
    r"(?:file://|(?:^|[\s'\"(])/(?:home|root|Users|tmp|workspace|mnt)/|"
    r"[A-Za-z]:\\(?:Users|Temp)\\|"
    r"\bcampaign(?:[_ -]?id)?\s*[:=]\s*[A-Za-z0-9._:-]+|"
    r"\b(?:api[_ -]?key|password|secret|token)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise GoldenDemoError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, field_name: str) -> str:
    try:
        return _public_identifier(cast(str, value), field_name)
    except (TypeError, FactModelError) as exc:
        raise GoldenDemoError(str(exc)) from exc


def _text(value: object, field_name: str) -> str:
    try:
        return _public_text(cast(str, value), field_name)
    except (TypeError, FactModelError) as exc:
        raise GoldenDemoError(str(exc)) from exc


def _detached(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GoldenDemoError(f"{field_name} must be a canonical JSON object")
    try:
        return cast(dict[str, Any], json.loads(canonical_json(dict(value))))
    except FactModelError as exc:
        raise GoldenDemoError(str(exc)) from exc


def _records(
    values: Iterable[Any], field_name: str, expected_type: type[Any], *, required: bool
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise GoldenDemoError(f"{field_name} must be a collection")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise GoldenDemoError(f"{field_name} must be a collection") from exc
    if required and not result:
        raise GoldenDemoError(f"{field_name} must not be empty")
    if any(not isinstance(item, expected_type) for item in result):
        raise GoldenDemoError(
            f"{field_name} must contain {expected_type.__name__} values"
        )
    return result


def _identifiers(
    values: Iterable[str], field_name: str, *, required: bool
) -> tuple[str, ...]:
    raw = _records(values, field_name, str, required=required)
    result = tuple(sorted(_identifier(item, field_name) for item in raw))
    if len(result) != len(set(result)):
        raise GoldenDemoError(f"{field_name} must contain unique identities")
    return result


def _public_path(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise GoldenDemoError(f"{field_name} must be a portable relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or "." in path.parts or ".." in path.parts:
        raise GoldenDemoError(f"{field_name} must be a portable relative POSIX path")
    if path.parts[0].lower() in {"tmp", "workspace"}:
        raise GoldenDemoError(
            f"{field_name} must not reference transient local evidence roots"
        )
    if path.as_posix() != value:
        raise GoldenDemoError(f"{field_name} must be a normalized relative POSIX path")
    return value


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _validate_public_surface(value: Mapping[str, Any]) -> None:
    for item in _walk_strings(value):
        if _FORBIDDEN_PUBLIC_VALUE.search(item):
            raise GoldenDemoError(
                "Golden Demo public data contains a personal path, transient identity, "
                "or secret-like assignment"
            )


def _portfolio_rows(
    portfolio: Mapping[str, Any], selected_scenario_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the existing M2.2 portfolio envelope and return selected rows."""
    if portfolio.get("schema_version") != PORTFOLIO_SCHEMA_VERSION:
        raise GoldenDemoError("portfolio evidence schema_version is unsupported")
    applications = portfolio.get("applications")
    packages = portfolio.get("application_packages")
    fingerprints = portfolio.get("scenario_semantic_fingerprints")
    if not isinstance(applications, list) or len(applications) != PORTFOLIO_APPLICATION_COUNT:
        raise GoldenDemoError("portfolio evidence must contain exactly eight applications")
    if not isinstance(packages, list) or len(packages) != PORTFOLIO_APPLICATION_COUNT:
        raise GoldenDemoError("portfolio evidence must contain exactly eight packages")
    if not isinstance(fingerprints, Mapping) or len(fingerprints) != PORTFOLIO_APPLICATION_COUNT:
        raise GoldenDemoError(
            "portfolio evidence must contain exactly eight semantic fingerprints"
        )

    application_index: dict[str, dict[str, Any]] = {}
    for row in applications:
        if not isinstance(row, Mapping):
            raise GoldenDemoError("portfolio application rows must be objects")
        scenario_id = _identifier(row.get("scenario_id"), "portfolio scenario_id")
        if scenario_id in application_index:
            raise GoldenDemoError("portfolio scenario identities must be unique")
        if row.get("production_ready") is not False:
            raise GoldenDemoError(
                "portfolio application decisions must explicitly retain production_ready=false"
            )
        application_index[scenario_id] = dict(row)

    package_index: dict[str, dict[str, Any]] = {}
    for row in packages:
        if not isinstance(row, Mapping):
            raise GoldenDemoError("portfolio package rows must be objects")
        scenario_id = _identifier(row.get("scenario_id"), "package scenario_id")
        if scenario_id in package_index:
            raise GoldenDemoError("portfolio package scenario identities must be unique")
        path = _public_path(row.get("path"), "portfolio package path")
        digest = _digest(row.get("sha256"), "portfolio package sha256")
        package_index[scenario_id] = {
            "path": path,
            "scenario_id": scenario_id,
            "sha256": digest,
        }

    scenario_ids = set(application_index)
    if set(package_index) != scenario_ids or set(fingerprints) != scenario_ids:
        raise GoldenDemoError(
            "portfolio application, package, and fingerprint identities do not match"
        )
    fingerprint_values = []
    for scenario_id, value in fingerprints.items():
        _identifier(scenario_id, "semantic fingerprint scenario_id")
        fingerprint_values.append(_digest(value, "scenario semantic fingerprint"))
    if len(fingerprint_values) != len(set(fingerprint_values)):
        raise GoldenDemoError("portfolio semantic fingerprints must be distinct")
    if selected_scenario_id not in application_index:
        raise GoldenDemoError(
            "representative scenario must be selected from the authenticated portfolio"
        )
    return application_index[selected_scenario_id], package_index[selected_scenario_id]


def _portfolio_qualification(row: Mapping[str, Any]) -> dict[str, Any]:
    decision = row.get("decision", "UNKNOWN_EXPLICIT")
    external_status = row.get("external_human_review_status", "UNKNOWN_EXPLICIT")
    near_production = row.get("near_production_candidate", "UNKNOWN_EXPLICIT")
    if not isinstance(decision, str):
        raise GoldenDemoError("portfolio decision must be an explicit string")
    if not isinstance(external_status, str):
        raise GoldenDemoError("external review status must be an explicit string")
    if not isinstance(near_production, (bool, str)):
        raise GoldenDemoError(
            "near_production_candidate must be boolean or UNKNOWN_EXPLICIT"
        )
    return {
        "decision": _identifier(decision, "portfolio decision"),
        "external_human_review_status": _identifier(
            external_status, "external human review status"
        ),
        "near_production_candidate": near_production,
        "production_ready": False,
    }


def _binding_matches(left: ProvenanceBinding, right: ProvenanceBinding) -> bool:
    return left.to_dict() == right.to_dict()


def _source_ref(
    source_type: str, source_id: str, revision: str, sha256: str
) -> dict[str, str]:
    return {
        "revision": _text(revision, f"{source_type} revision"),
        "sha256": _digest(sha256, f"{source_type} sha256"),
        "source_id": _identifier(source_id, f"{source_type} source_id"),
        "source_type": _identifier(source_type, "source_type"),
    }


def _fingerprints_preserve_inputs(
    before: ExecutionFingerprint, after: ExecutionFingerprint
) -> bool:
    return all(
        getattr(before, field_name) == getattr(after, field_name)
        for field_name in (
            "factory_source_identity",
            "requirement_identity",
            "evidence_snapshot_identity",
            "tool_config_identity",
        )
    )


@dataclass(frozen=True)
class GoldenDemoDossier:
    """Immutable machine source for future short and deep-dive presentations."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.golden-demo-dossier.v1"

    portfolio_evidence: Mapping[str, Any] = field(repr=False, compare=False)
    portfolio_provenance: ProvenanceBinding
    selected_scenario_id: str
    selected_claim_ids: tuple[str, ...]
    value_closure: ValueClosureInventory = field(repr=False, compare=False)
    operational_acceptance: OperationalAcceptanceEvidence = field(
        repr=False, compare=False
    )
    independent_review: IndependentReviewReport = field(repr=False, compare=False)
    before_governance: GovernanceSnapshot = field(repr=False, compare=False)
    after_governance: GovernanceSnapshot = field(repr=False, compare=False)
    semantic_diff: SemanticDiff = field(repr=False, compare=False)
    impact: ImpactProjection = field(repr=False, compare=False)
    evolved_execution_fingerprint: ExecutionFingerprint = field(
        repr=False, compare=False
    )
    _document: Mapping[str, Any] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        portfolio = _detached(self.portfolio_evidence, "portfolio_evidence")
        if not isinstance(self.portfolio_provenance, ProvenanceBinding):
            raise GoldenDemoError("portfolio_provenance must use ProvenanceBinding")
        if self.portfolio_provenance.source_type not in MACHINE_EVIDENCE_SOURCE_TYPES:
            raise GoldenDemoError(
                "portfolio provenance must use an authenticated machine evidence source type"
            )
        if self.portfolio_provenance.content_sha256 != canonical_sha256(portfolio):
            raise GoldenDemoError(
                "portfolio provenance does not bind the canonical portfolio evidence"
            )
        scenario_id = _identifier(self.selected_scenario_id, "selected_scenario_id")
        claim_ids = _identifiers(
            self.selected_claim_ids, "selected_claim_ids", required=True
        )
        selected_application, selected_package = _portfolio_rows(portfolio, scenario_id)

        typed_inputs = (
            (self.value_closure, ValueClosureInventory, "value_closure"),
            (
                self.operational_acceptance,
                OperationalAcceptanceEvidence,
                "operational_acceptance",
            ),
            (
                self.independent_review,
                IndependentReviewReport,
                "independent_review",
            ),
            (self.before_governance, GovernanceSnapshot, "before_governance"),
            (self.after_governance, GovernanceSnapshot, "after_governance"),
            (self.semantic_diff, SemanticDiff, "semantic_diff"),
            (self.impact, ImpactProjection, "impact"),
            (
                self.evolved_execution_fingerprint,
                ExecutionFingerprint,
                "evolved_execution_fingerprint",
            ),
        )
        for value, expected_type, field_name in typed_inputs:
            if not isinstance(value, expected_type):
                raise GoldenDemoError(f"{field_name} must use {expected_type.__name__}")

        closure_document = self.value_closure.to_dict()
        operational_document = self.operational_acceptance.to_dict()
        review_document = self.independent_review.to_dict()
        validate_value_closure_document(closure_document)
        validate_operational_acceptance_evidence(operational_document)
        validate_independent_review_document(review_document)

        graph = self.value_closure.graph
        graph_digest = str(graph.to_dict()["graph_digest"])
        if closure_document["fact_graph_digest"] != graph_digest:
            raise GoldenDemoError("value closure does not bind its supplied fact graph")
        if review_document["fact_graph_digest"] != graph_digest:
            raise GoldenDemoError("independent review does not bind the value fact graph")
        if review_document["source_snapshot_sha256"] != closure_document[
            "source_snapshot_sha256"
        ]:
            raise GoldenDemoError(
                "independent review and value closure do not bind the same source snapshot"
            )

        claim_index = {
            str(item["claim_id"]): item for item in closure_document["capabilities"]
        }
        review_index = {
            str(item["claim_id"]): item for item in review_document["reviews"]
        }
        if not set(claim_ids).issubset(claim_index):
            raise GoldenDemoError("selected claims are not registered in value closure")
        if not set(claim_ids).issubset(review_index):
            raise GoldenDemoError("selected claims lack deterministic independent review")

        operational_fact = self.operational_acceptance.machine_evidence_fact()
        try:
            registered_operational_fact = graph.node(operational_fact.node_id)
        except FactModelError as exc:
            raise GoldenDemoError(
                "operational acceptance is not registered in the selected fact graph"
            ) from exc
        if registered_operational_fact.to_dict() != operational_fact.to_dict():
            raise GoldenDemoError(
                "registered operational-acceptance fact does not match its evidence"
            )

        selected_evidence_ids = {
            evidence_id
            for claim_id in claim_ids
            for evidence_id in claim_index[claim_id]["machine_evidence_fact_ids"]
        }
        if operational_fact.node_id not in selected_evidence_ids:
            raise GoldenDemoError(
                "selected claims do not trace to operational-acceptance evidence"
            )

        portfolio_fact_ids: list[str] = []
        for evidence_id in sorted(selected_evidence_ids):
            node = graph.node(evidence_id)
            if any(
                _binding_matches(binding, self.portfolio_provenance)
                for binding in node.provenance
            ):
                if (
                    node.status is FactStatus.PROVEN
                    and isinstance(node.value, Mapping)
                    and node.value.get("result") in {"PASS", "PROVEN"}
                ):
                    portfolio_fact_ids.append(evidence_id)
        if not portfolio_fact_ids:
            raise GoldenDemoError(
                "selected claims do not trace to authenticated eight-application portfolio evidence"
            )

        claim_rows: list[dict[str, Any]] = []
        for claim_id in claim_ids:
            claim = claim_index[claim_id]
            review = review_index[claim_id]
            if (
                review["claim_text"] != claim["claim_text"]
                or review["declared_status"] != claim["status"]
                or review["capability_id"] != claim["capability_id"]
            ):
                raise GoldenDemoError(
                    f"review {claim_id} does not match its registered value claim"
                )
            claim_limitations = tuple(
                sorted(
                    {
                        _text(item["text"], "claim limitation")
                        for item in claim["limitations"]
                    }
                )
            )
            claim_rows.append(
                {
                    "business_value_dimension": claim["business_value_dimension"],
                    "capability_id": claim["capability_id"],
                    "claim_id": claim_id,
                    "claim_text": claim["claim_text"],
                    "limitations": list(claim_limitations),
                    "machine_evidence_fact_ids": claim["machine_evidence_fact_ids"],
                    "open_blocker_finding_ids": review[
                        "open_blocker_finding_ids"
                    ],
                    "public_claim_eligibility": claim[
                        "public_claim_eligibility"
                    ],
                    "review_id": review["review_id"],
                    "reviewer_verdict": review["verdict"],
                    "status": claim["status"],
                    "status_fact_id": claim["status_fact_id"],
                    "supporting_fact_ids": claim["supporting_fact_ids"],
                }
            )

        old_fingerprint = self.operational_acceptance.scenario.execution_fingerprint
        if old_fingerprint.governance_snapshot_identity != self.before_governance.snapshot_id:
            raise GoldenDemoError(
                "operational execution is not pinned to the before-governance snapshot"
            )
        if self.before_governance.snapshot_id == self.after_governance.snapshot_id:
            raise GoldenDemoError("Golden Demo governance evolution must not be a no-op")
        if not {
            self.after_governance.previous_snapshot_id,
            self.after_governance.supersedes_snapshot_id,
        }.intersection({self.before_governance.snapshot_id}):
            raise GoldenDemoError(
                "after-governance snapshot must explicitly bind predecessor lineage"
            )
        expected_diff = SemanticDiff.between(
            self.before_governance, self.after_governance
        )
        if self.semantic_diff.to_dict() != expected_diff.to_dict() or self.semantic_diff.is_noop:
            raise GoldenDemoError(
                "semantic diff is not the exact non-empty difference between snapshots"
            )
        expected_impact = project_impact(
            self.semantic_diff,
            graph,
            self.value_closure.current_sources,
        )
        if self.impact.to_dict() != expected_impact.to_dict():
            raise GoldenDemoError(
                "governance impact is not derived from the supplied fact graph"
            )
        evolved = self.evolved_execution_fingerprint
        if evolved.governance_snapshot_identity != self.after_governance.snapshot_id:
            raise GoldenDemoError(
                "evolved execution fingerprint must pin the new governance snapshot"
            )
        if not _fingerprints_preserve_inputs(old_fingerprint, evolved):
            raise GoldenDemoError(
                "controlled evolution cannot silently move non-governance execution inputs"
            )
        if old_fingerprint.fingerprint_id == evolved.fingerprint_id:
            raise GoldenDemoError(
                "a governance change requires a distinct execution fingerprint"
            )

        aggregate_limitations = {
            *(_text(item, "operational limitation") for item in self.operational_acceptance.limitations),
            *(
                limitation
                for claim in claim_rows
                for limitation in claim["limitations"]
            ),
        }
        if self.impact.has_unknown_impact:
            aggregate_limitations.add(
                "Governance impact contains unresolved or unknown identities; those impacts are not claimed as known."
            )
        if _portfolio_qualification(selected_application)[
            "external_human_review_status"
        ] != "SIGNED_EXTERNAL_HUMAN_REVIEW_COMPLETE":
            aggregate_limitations.add(
                "Signed external human review is not proven by the selected portfolio record."
            )

        operational_source = self.operational_acceptance.provenance_binding
        review_source = self.independent_review.provenance_binding
        portfolio_qualification = _portfolio_qualification(selected_application)
        source_bindings = {
            "fact_graph": _source_ref(
                "FACT_EVIDENCE_GRAPH",
                f"FACT-GRAPH-{graph_digest}",
                "fact-graph:v1",
                graph_digest,
            ),
            "independent_review": _source_ref(
                review_source.source_type,
                review_source.source_id,
                review_source.revision,
                review_source.content_sha256,
            ),
            "operational_acceptance": _source_ref(
                operational_source.source_type,
                operational_source.source_id,
                operational_source.revision,
                operational_source.content_sha256,
            ),
            "portfolio": _source_ref(
                self.portfolio_provenance.source_type,
                self.portfolio_provenance.source_id,
                self.portfolio_provenance.revision,
                self.portfolio_provenance.content_sha256,
            ),
            "value_closure": _source_ref(
                "CANONICAL_MACHINE_EVIDENCE",
                closure_document["inventory_id"],
                "value-closure:v1",
                closure_document["inventory_digest"],
            ),
        }
        journey = [
            {
                "evidence_outcome": "BOUND_TO_OPERATIONAL_SCENARIO",
                "source_ids": [operational_document["scenario"]["scenario_id"]],
                "stage_id": "REQUIREMENT",
            },
            {
                "evidence_outcome": operational_document["result"]["status"],
                "source_ids": sorted(
                    [
                        operational_document["scenario"]["execution_fingerprint"][
                            "fingerprint_id"
                        ],
                        operational_document["evidence_id"],
                    ]
                ),
                "stage_id": "APPLICATION_ENGINEERING",
            },
            {
                "evidence_outcome": portfolio_qualification["decision"],
                "source_ids": sorted(
                    [
                        selected_package["sha256"],
                        cast(
                            str,
                            portfolio["scenario_semantic_fingerprints"][scenario_id],
                        ),
                    ]
                ),
                "stage_id": "PRODUCT_ARTIFACTS_AND_TESTS",
            },
            {
                "evidence_outcome": review_document["overall_verdict"],
                "source_ids": sorted(
                    [
                        operational_document["evidence_id"],
                        review_document["review_id"],
                    ]
                ),
                "stage_id": "QUALIFICATION_AND_REVIEW",
            },
            {
                "evidence_outcome": GOVERNANCE_DEMONSTRATION_CLASSIFICATION,
                "source_ids": sorted(
                    [self.semantic_diff.diff_id, self.impact.impact_id]
                ),
                "stage_id": "GOVERNANCE_CHANGE_AND_IMPACT",
            },
            {
                "evidence_outcome": CONTROLLED_EVOLUTION_RULE,
                "source_ids": sorted(
                    [old_fingerprint.fingerprint_id, evolved.fingerprint_id]
                ),
                "stage_id": "CONTROLLED_EVOLUTION",
            },
        ]
        core = {
            "authority_boundary": {
                "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
                "ai_authority": "NONE",
                "canonical_json_is_evidence_source": True,
                "human_projection_is_authority": False,
                "self_awarded_readiness": False,
            },
            "claims": claim_rows,
            "governance_evolution": {
                "after_snapshot_id": self.after_governance.snapshot_id,
                "before_snapshot_id": self.before_governance.snapshot_id,
                "change_count": len(self.semantic_diff.changes),
                "classification": GOVERNANCE_DEMONSTRATION_CLASSIFICATION,
                "controlled_evolution_rule": CONTROLLED_EVOLUTION_RULE,
                "evolved_execution_fingerprint_id": evolved.fingerprint_id,
                "existing_execution_fingerprint_id": old_fingerprint.fingerprint_id,
                "existing_execution_pin_unchanged": (
                    old_fingerprint.governance_snapshot_identity
                    == self.before_governance.snapshot_id
                ),
                "impact_id": self.impact.impact_id,
                "is_live_regulatory_change": False,
                "semantic_change_ids": sorted(
                    item.change_id for item in self.semantic_diff.changes
                ),
                "semantic_diff_id": self.semantic_diff.diff_id,
                "unknown_impact_ids": list(self.impact.unknown_impact_ids),
                "unresolved_reference_ids": list(
                    self.impact.unresolved_reference_ids
                ),
            },
            "journey": journey,
            "limitations": sorted(aggregate_limitations),
            "nonclaims": list(MANDATORY_NONCLAIMS),
            "operational_observation": {
                "command_entrypoint": operational_document["scenario"]["command"][
                    "entrypoint"
                ],
                "evidence_id": operational_document["evidence_id"],
                "output_artifacts": [
                    {
                        "availability": item["availability"],
                        "logical_path": item["logical_path"],
                        "sha256": item["sha256"],
                    }
                    for item in operational_document["result"]["output_artifacts"]
                ],
                "result_id": operational_document["result"]["result_id"],
                "status": operational_document["result"]["status"],
            },
            "portfolio_selection": {
                "application_count": PORTFOLIO_APPLICATION_COUNT,
                "portfolio_fact_ids": sorted(portfolio_fact_ids),
                "qualification": portfolio_qualification,
                "selected_package": selected_package,
                "selected_scenario_id": scenario_id,
                "semantic_fingerprint_sha256": portfolio[
                    "scenario_semantic_fingerprints"
                ][scenario_id],
                "selection_rule": "EXACT_AUTHENTICATED_PORTFOLIO_MEMBERSHIP",
            },
            "schema_version": self.SCHEMA_VERSION,
            "source_bindings": source_bindings,
            "title": "UPI App Factory Golden Demo Evidence Dossier",
        }
        dossier_sha256 = canonical_sha256(core)
        document = {
            **core,
            "dossier_id": f"GOLDEN-DEMO-DOSSIER-{dossier_sha256}",
            "dossier_sha256": dossier_sha256,
        }
        validate_golden_demo_document(document)
        object.__setattr__(self, "portfolio_evidence", portfolio)
        object.__setattr__(self, "selected_scenario_id", scenario_id)
        object.__setattr__(self, "selected_claim_ids", claim_ids)
        object.__setattr__(self, "_document", document)

    @property
    def dossier_sha256(self) -> str:
        return str(self._document["dossier_sha256"])

    @property
    def dossier_id(self) -> str:
        return str(self._document["dossier_id"])

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(canonical_json(self._document)))

    def to_json(self) -> str:
        return canonical_json(self._document)


def build_golden_demo_dossier(**kwargs: Any) -> GoldenDemoDossier:
    """Build a canonical dossier without introducing a competing fact model."""
    return GoldenDemoDossier(**kwargs)


def validate_golden_demo_document(document: Mapping[str, Any]) -> bool:
    """Validate identity, traceability, limitations, and non-authority semantics."""
    expected_fields = {
        "authority_boundary",
        "claims",
        "dossier_id",
        "dossier_sha256",
        "governance_evolution",
        "journey",
        "limitations",
        "nonclaims",
        "operational_observation",
        "portfolio_selection",
        "schema_version",
        "source_bindings",
        "title",
    }
    if not isinstance(document, Mapping) or set(document) != expected_fields:
        raise GoldenDemoError("Golden Demo dossier fields do not match the contract")
    value = _detached(document, "dossier")
    if value["schema_version"] != GoldenDemoDossier.SCHEMA_VERSION:
        raise GoldenDemoError("Golden Demo dossier schema_version is unsupported")
    if value["title"] != "UPI App Factory Golden Demo Evidence Dossier":
        raise GoldenDemoError("Golden Demo dossier title is invalid")
    digest = _digest(value["dossier_sha256"], "dossier_sha256")
    core = {
        key: item
        for key, item in value.items()
        if key not in {"dossier_id", "dossier_sha256"}
    }
    if canonical_sha256(core) != digest:
        raise GoldenDemoError("Golden Demo dossier digest is invalid")
    if value["dossier_id"] != f"GOLDEN-DEMO-DOSSIER-{digest}":
        raise GoldenDemoError("Golden Demo dossier ID is invalid")
    if value["authority_boundary"] != {
        "acceptance_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "canonical_json_is_evidence_source": True,
        "human_projection_is_authority": False,
        "self_awarded_readiness": False,
    }:
        raise GoldenDemoError("Golden Demo authority boundary is invalid")
    if value["nonclaims"] != list(MANDATORY_NONCLAIMS):
        raise GoldenDemoError("Golden Demo mandatory nonclaims were weakened")
    limitations = value["limitations"]
    if (
        not isinstance(limitations, list)
        or not limitations
        or limitations != sorted(set(limitations))
    ):
        raise GoldenDemoError("Golden Demo limitations must be explicit and canonical")
    for limitation in limitations:
        _text(limitation, "Golden Demo limitation")

    source_bindings = value["source_bindings"]
    expected_sources = {
        "fact_graph",
        "independent_review",
        "operational_acceptance",
        "portfolio",
        "value_closure",
    }
    if not isinstance(source_bindings, Mapping) or set(source_bindings) != expected_sources:
        raise GoldenDemoError("Golden Demo source bindings are incomplete")
    for source_name, source in source_bindings.items():
        if not isinstance(source, Mapping) or set(source) != {
            "revision",
            "sha256",
            "source_id",
            "source_type",
        }:
            raise GoldenDemoError(f"source binding {source_name} is invalid")
        _digest(source["sha256"], f"{source_name} sha256")
        _text(source["revision"], f"{source_name} revision")
        _identifier(source["source_id"], f"{source_name} source_id")
        _identifier(source["source_type"], f"{source_name} source_type")

    claims = value["claims"]
    if not isinstance(claims, list) or not claims:
        raise GoldenDemoError("Golden Demo must display registered claims")
    claim_ids: list[str] = []
    expected_claim_fields = {
        "business_value_dimension",
        "capability_id",
        "claim_id",
        "claim_text",
        "limitations",
        "machine_evidence_fact_ids",
        "open_blocker_finding_ids",
        "public_claim_eligibility",
        "review_id",
        "reviewer_verdict",
        "status",
        "status_fact_id",
        "supporting_fact_ids",
    }
    for claim in claims:
        if not isinstance(claim, Mapping) or set(claim) != expected_claim_fields:
            raise GoldenDemoError("Golden Demo displayed claim is invalid")
        claim_id = _identifier(claim["claim_id"], "claim_id")
        _identifier(claim["capability_id"], "capability_id")
        _identifier(claim["status_fact_id"], "status_fact_id")
        _identifier(claim["review_id"], "review_id")
        _text(claim["claim_text"], "claim_text")
        try:
            BusinessValueDimension(claim["business_value_dimension"])
            PublicClaimEligibility(claim["public_claim_eligibility"])
            ValueClosureStatus(claim["status"])
            verdict = ProofVerdict(claim["reviewer_verdict"])
        except (TypeError, ValueError) as exc:
            raise GoldenDemoError("Golden Demo claim status or verdict is invalid") from exc
        if verdict not in REVIEWER_VERDICTS:
            raise GoldenDemoError("Golden Demo reviewer verdict is outside the closed subset")
        supporting = claim["supporting_fact_ids"]
        evidence = claim["machine_evidence_fact_ids"]
        blockers = claim["open_blocker_finding_ids"]
        if not all(isinstance(items, list) for items in (supporting, evidence, blockers)):
            raise GoldenDemoError("Golden Demo claim trace references must be lists")
        for field_name, items in (
            ("supporting_fact_ids", supporting),
            ("machine_evidence_fact_ids", evidence),
            ("open_blocker_finding_ids", blockers),
        ):
            if items != sorted(set(items)):
                raise GoldenDemoError(f"{field_name} must be canonically ordered")
            for item in items:
                _identifier(item, field_name)
        if claim["status_fact_id"] not in supporting or not set(evidence).issubset(
            supporting
        ):
            raise GoldenDemoError("Golden Demo claim fact trace is incomplete")
        claim_limitations = claim["limitations"]
        if (
            not isinstance(claim_limitations, list)
            or not claim_limitations
            or claim_limitations != sorted(set(claim_limitations))
        ):
            raise GoldenDemoError("every displayed claim requires limitations")
        for limitation in claim_limitations:
            _text(limitation, "claim limitation")
            if limitation not in limitations:
                raise GoldenDemoError(
                    "displayed claim limitation is absent from dossier limitations"
                )
        claim_ids.append(claim_id)
    if claim_ids != sorted(set(claim_ids)):
        raise GoldenDemoError("Golden Demo claims must be uniquely ordered")

    journey = value["journey"]
    if not isinstance(journey, list) or [item.get("stage_id") for item in journey] != list(
        JOURNEY_STAGE_IDS
    ):
        raise GoldenDemoError("Golden Demo journey is incomplete or out of order")
    for stage in journey:
        if not isinstance(stage, Mapping) or set(stage) != {
            "evidence_outcome",
            "source_ids",
            "stage_id",
        }:
            raise GoldenDemoError("Golden Demo journey stage is invalid")
        _identifier(stage["stage_id"], "stage_id")
        _identifier(stage["evidence_outcome"], "evidence_outcome")
        if not isinstance(stage["source_ids"], list) or not stage["source_ids"]:
            raise GoldenDemoError("Golden Demo journey stage lacks evidence sources")
        if stage["source_ids"] != sorted(set(stage["source_ids"])):
            raise GoldenDemoError(
                "Golden Demo journey sources must be unique and canonically ordered"
            )
        for source_id in stage["source_ids"]:
            _identifier(source_id, "journey source_id")

    portfolio = value["portfolio_selection"]
    if not isinstance(portfolio, Mapping) or set(portfolio) != {
        "application_count",
        "portfolio_fact_ids",
        "qualification",
        "selected_package",
        "selected_scenario_id",
        "selection_rule",
        "semantic_fingerprint_sha256",
    }:
        raise GoldenDemoError("Golden Demo portfolio selection is invalid")
    if portfolio.get("application_count") != PORTFOLIO_APPLICATION_COUNT:
        raise GoldenDemoError("Golden Demo portfolio count is not eight")
    _identifier(portfolio.get("selected_scenario_id"), "selected_scenario_id")
    _digest(
        portfolio.get("semantic_fingerprint_sha256"),
        "semantic_fingerprint_sha256",
    )
    if portfolio.get("selection_rule") != "EXACT_AUTHENTICATED_PORTFOLIO_MEMBERSHIP":
        raise GoldenDemoError("Golden Demo scenario selection rule is invalid")
    package = portfolio.get("selected_package")
    if not isinstance(package, Mapping) or set(package) != {
        "path",
        "scenario_id",
        "sha256",
    }:
        raise GoldenDemoError("Golden Demo selected package is invalid")
    _public_path(package.get("path"), "selected package path")
    _digest(package.get("sha256"), "selected package sha256")
    if package.get("scenario_id") != portfolio.get("selected_scenario_id"):
        raise GoldenDemoError("Golden Demo package does not bind the selected scenario")
    qualification = portfolio.get("qualification")
    if not isinstance(qualification, Mapping) or set(qualification) != {
        "decision",
        "external_human_review_status",
        "near_production_candidate",
        "production_ready",
    }:
        raise GoldenDemoError("Golden Demo qualification fields are invalid")
    if qualification.get("production_ready") is not False:
        raise GoldenDemoError("Golden Demo qualification overstates production readiness")
    _identifier(qualification.get("decision"), "portfolio decision")
    _identifier(
        qualification.get("external_human_review_status"),
        "external human review status",
    )
    if not isinstance(
        qualification.get("near_production_candidate"), (bool, str)
    ):
        raise GoldenDemoError("Golden Demo near-production state is invalid")
    if isinstance(qualification["near_production_candidate"], str) and qualification[
        "near_production_candidate"
    ] != "UNKNOWN_EXPLICIT":
        raise GoldenDemoError("Golden Demo near-production unknown state is invalid")
    facts = portfolio.get("portfolio_fact_ids")
    if not isinstance(facts, list) or not facts or facts != sorted(set(facts)):
        raise GoldenDemoError("Golden Demo portfolio facts are missing or ambiguous")
    for fact_id in facts:
        _identifier(fact_id, "portfolio fact_id")

    operational = value["operational_observation"]
    if not isinstance(operational, Mapping) or set(operational) != {
        "command_entrypoint",
        "evidence_id",
        "output_artifacts",
        "result_id",
        "status",
    }:
        raise GoldenDemoError("Golden Demo operational observation is invalid")
    for field_name in ("command_entrypoint", "evidence_id", "result_id"):
        _identifier(operational.get(field_name), field_name)
    try:
        AcceptanceStatus(operational.get("status"))
    except (TypeError, ValueError) as exc:
        raise GoldenDemoError("Golden Demo operational status is invalid") from exc
    output_artifacts = operational.get("output_artifacts")
    if not isinstance(output_artifacts, list):
        raise GoldenDemoError("Golden Demo output artifacts must be a list")
    output_paths: list[str] = []
    for artifact in output_artifacts:
        if not isinstance(artifact, Mapping):
            raise GoldenDemoError("Golden Demo output artifact is invalid")
        logical_path = artifact.get("logical_path")
        if not isinstance(logical_path, str):
            raise GoldenDemoError("Golden Demo output artifact path is invalid")
        output_paths.append(logical_path)
    if output_paths != sorted(set(output_paths)):
        raise GoldenDemoError("Golden Demo output artifacts are not canonical")
    for artifact in output_artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {
            "availability",
            "logical_path",
            "sha256",
        }:
            raise GoldenDemoError("Golden Demo output artifact is invalid")
        _public_path(artifact.get("logical_path"), "output artifact logical_path")
        availability = artifact.get("availability")
        if availability == ArtifactAvailability.PRESENT.value:
            _digest(artifact.get("sha256"), "output artifact sha256")
        elif availability != ArtifactAvailability.MISSING.value or artifact.get(
            "sha256"
        ) is not None:
            raise GoldenDemoError("Golden Demo output artifact availability is invalid")

    governance = value["governance_evolution"]
    if not isinstance(governance, Mapping) or set(governance) != {
        "after_snapshot_id",
        "before_snapshot_id",
        "change_count",
        "classification",
        "controlled_evolution_rule",
        "evolved_execution_fingerprint_id",
        "existing_execution_fingerprint_id",
        "existing_execution_pin_unchanged",
        "impact_id",
        "is_live_regulatory_change",
        "semantic_change_ids",
        "semantic_diff_id",
        "unknown_impact_ids",
        "unresolved_reference_ids",
    }:
        raise GoldenDemoError("Golden Demo governance evolution is invalid")
    if governance.get("classification") != GOVERNANCE_DEMONSTRATION_CLASSIFICATION:
        raise GoldenDemoError("Golden Demo governance change is not explicitly synthetic")
    if governance.get("is_live_regulatory_change") is not False:
        raise GoldenDemoError("Golden Demo cannot claim a live regulatory change")
    if governance.get("controlled_evolution_rule") != CONTROLLED_EVOLUTION_RULE:
        raise GoldenDemoError("Golden Demo controlled-evolution rule is invalid")
    if governance.get("existing_execution_pin_unchanged") is not True:
        raise GoldenDemoError("Golden Demo silently moved an existing execution pin")
    if governance.get("before_snapshot_id") == governance.get("after_snapshot_id"):
        raise GoldenDemoError("Golden Demo governance snapshots must be distinct")
    if governance.get("existing_execution_fingerprint_id") == governance.get(
        "evolved_execution_fingerprint_id"
    ):
        raise GoldenDemoError("Golden Demo controlled evolution requires a new fingerprint")
    for field_name in (
        "after_snapshot_id",
        "before_snapshot_id",
        "evolved_execution_fingerprint_id",
        "existing_execution_fingerprint_id",
        "impact_id",
        "semantic_diff_id",
    ):
        _identifier(governance.get(field_name), field_name)
    if not isinstance(governance.get("change_count"), int) or governance["change_count"] < 1:
        raise GoldenDemoError("Golden Demo governance change must be non-empty")
    change_ids = governance.get("semantic_change_ids")
    if (
        not isinstance(change_ids, list)
        or len(change_ids) != governance["change_count"]
        or change_ids != sorted(set(change_ids))
    ):
        raise GoldenDemoError("Golden Demo semantic change identities are incomplete")
    for change_id in change_ids:
        _identifier(change_id, "semantic_change_id")
    for field_name in ("unknown_impact_ids", "unresolved_reference_ids"):
        impact_ids = governance.get(field_name)
        if not isinstance(impact_ids, list) or impact_ids != sorted(set(impact_ids)):
            raise GoldenDemoError(f"Golden Demo {field_name} are not canonical")
        for impact_id in impact_ids:
            _identifier(impact_id, field_name)

    _validate_public_surface(value)
    return True


def _canonical_document(
    canonical_dossier_json: str | bytes,
) -> tuple[str, dict[str, Any], str]:
    if isinstance(canonical_dossier_json, bytes):
        try:
            encoded = canonical_dossier_json.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GoldenDemoError("Golden Demo JSON must be UTF-8") from exc
    elif isinstance(canonical_dossier_json, str):
        encoded = canonical_dossier_json
    else:
        raise GoldenDemoError("Golden Demo JSON must be str or bytes")
    try:
        value = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise GoldenDemoError("Golden Demo JSON is invalid") from exc
    if not isinstance(value, dict):
        raise GoldenDemoError("Golden Demo JSON must contain an object")
    if canonical_json(value) != encoded:
        raise GoldenDemoError("Golden Demo JSON must use canonical serialization")
    validate_golden_demo_document(value)
    return encoded, value, _sha256_bytes(encoded.encode("utf-8"))


def _display(value: object) -> str:
    if value is None:
        rendered = "UNKNOWN_EXPLICIT"
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, list):
        rendered = ", ".join(str(item) for item in value) if value else "NONE"
    else:
        rendered = str(value)
    return html.escape(rendered, quote=True)


def render_golden_demo_html(canonical_dossier_json: str | bytes) -> str:
    """Render accessible offline HTML solely from validated canonical JSON."""
    encoded, document, json_sha256 = _canonical_document(canonical_dossier_json)
    portfolio = cast(Mapping[str, Any], document["portfolio_selection"])
    operational = cast(Mapping[str, Any], document["operational_observation"])
    governance = cast(Mapping[str, Any], document["governance_evolution"])
    claims = cast(list[Mapping[str, Any]], document["claims"])
    journey = cast(list[Mapping[str, Any]], document["journey"])

    journey_rows = "".join(
        "<tr><th scope=\"row\">"
        + _display(stage["stage_id"])
        + "</th><td>"
        + _display(stage["evidence_outcome"])
        + "</td><td><code>"
        + _display(stage["source_ids"])
        + "</code></td></tr>"
        for stage in journey
    )
    claim_rows = "".join(
        '<article class="claim" data-claim-id="'
        + _display(claim["claim_id"])
        + '" data-status-fact-id="'
        + _display(claim["status_fact_id"])
        + '"><h3>'
        + _display(claim["claim_id"])
        + "</h3><p>"
        + _display(claim["claim_text"])
        + "</p><dl><dt>Value status</dt><dd>"
        + _display(claim["status"])
        + "</dd><dt>Reviewer verdict</dt><dd>"
        + _display(claim["reviewer_verdict"])
        + "</dd><dt>Public eligibility</dt><dd>"
        + _display(claim["public_claim_eligibility"])
        + "</dd><dt>Fact trace</dt><dd><code>"
        + _display(claim["supporting_fact_ids"])
        + "</code></dd><dt>Limitations</dt><dd>"
        + _display(claim["limitations"])
        + "</dd></dl></article>"
        for claim in claims
    )
    limitation_items = "".join(
        "<li>" + _display(item) + "</li>" for item in document["limitations"]
    )
    nonclaim_items = "".join(
        "<li>" + _display(item) + "</li>" for item in document["nonclaims"]
    )
    source_rows = "".join(
        "<tr><th scope=\"row\">"
        + _display(name)
        + "</th><td><code>"
        + _display(source["source_id"])
        + "</code></td><td><code>"
        + _display(source["revision"])
        + "</code></td><td><code>"
        + _display(source["sha256"])
        + "</code></td></tr>"
        for name, source in sorted(document["source_bindings"].items())
    )
    canonical_payload = html.escape(encoded, quote=False)
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="canonical-json-sha256" content="{json_sha256}">'
        f'<meta name="golden-demo-dossier-id" content="{_display(document["dossier_id"])}">'
        "<title>UPI App Factory Golden Demo Evidence Dossier</title>"
        "<style>:root{color-scheme:light;--ink:#14212b;--blue:#073b66;--line:#64727d;"
        "--surface:#f2f7fb;--warn:#7a4100}*{box-sizing:border-box}body{font:1rem/1.55 "
        "system-ui,sans-serif;color:var(--ink);max-width:78rem;margin:auto;padding:1rem}"
        "header{border-bottom:.35rem solid var(--blue);padding-bottom:1rem}h1,h2{color:var(--blue)}"
        "table{width:100%;border-collapse:collapse}th,td{border:1px solid var(--line);padding:.5rem;"
        "text-align:left;vertical-align:top}.claim{background:var(--surface);padding:.75rem;margin:1rem 0}"
        "dt{font-weight:700}dd{margin:0 0 .5rem}code,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap;"
        "border:1px solid var(--line);padding:.75rem}.boundary{border-left:.35rem solid var(--warn);"
        "padding-left:.75rem}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}"
        "</style></head><body><a href=\"#main\">Skip to evidence</a><header>"
        "<h1>Golden Demo Evidence Dossier</h1>"
        '<p class="boundary" role="status">Canonical machine evidence is the source of truth. '
        "This presentation is not acceptance authority.</p>"
        f'<p>Representative portfolio scenario: <strong>{_display(portfolio["selected_scenario_id"])}</strong> '
        f'from exactly {_display(portfolio["application_count"])} authenticated applications.</p>'
        f'<p>Operational observation: <strong>{_display(operational["status"])}</strong>. '
        f'Canonical JSON SHA-256: <code>{json_sha256}</code>.</p></header><main id="main">'
        '<section aria-labelledby="journey-heading"><h2 id="journey-heading">Evidence journey</h2>'
        '<table><caption>Requirement to controlled evolution</caption><thead><tr><th>Stage</th>'
        f"<th>Evidence outcome</th><th>Canonical source identities</th></tr></thead><tbody>{journey_rows}"
        "</tbody></table></section>"
        '<section aria-labelledby="claims-heading"><h2 id="claims-heading">Typed reviewed claims</h2>'
        f"{claim_rows}</section>"
        '<section aria-labelledby="change-heading"><h2 id="change-heading">Synthetic governance change</h2>'
        '<p class="boundary">This is explicitly synthetic, not a live NPCI or RBI change.</p><dl>'
        f'<dt>Before snapshot</dt><dd><code>{_display(governance["before_snapshot_id"])}</code></dd>'
        f'<dt>After snapshot</dt><dd><code>{_display(governance["after_snapshot_id"])}</code></dd>'
        f'<dt>Semantic diff</dt><dd><code>{_display(governance["semantic_diff_id"])}</code></dd>'
        f'<dt>Impact</dt><dd><code>{_display(governance["impact_id"])}</code></dd>'
        f'<dt>Existing pin preserved</dt><dd>{_display(governance["existing_execution_pin_unchanged"])}</dd>'
        f'<dt>Controlled evolution</dt><dd>{_display(governance["controlled_evolution_rule"])}</dd>'
        "</dl></section>"
        '<section aria-labelledby="sources-heading"><h2 id="sources-heading">Source bindings</h2><table>'
        f"<thead><tr><th>Source</th><th>Identity</th><th>Revision</th><th>SHA-256</th></tr></thead><tbody>{source_rows}"
        "</tbody></table></section>"
        '<section aria-labelledby="limitations-heading"><h2 id="limitations-heading">Limitations</h2>'
        f"<ul>{limitation_items}</ul></section>"
        '<section aria-labelledby="nonclaims-heading"><h2 id="nonclaims-heading">Nonclaims</h2>'
        f"<ul>{nonclaim_items}</ul></section>"
        '<section aria-labelledby="canonical-heading"><h2 id="canonical-heading">Canonical JSON</h2>'
        f'<details><summary>Inspect exact machine source</summary><pre id="canonical-json">{canonical_payload}</pre>'
        "</details></section></main><footer><p>Deterministic offline projection bound to canonical JSON "
        f"SHA-256 <code>{json_sha256}</code>. AI authority: NONE.</p></footer></body></html>\n"
    )


def build_golden_demo_projection_binding(
    canonical_dossier_json: str | bytes, projection_html: str
) -> dict[str, Any]:
    """Bind exact canonical JSON bytes to an exact deterministic HTML projection."""
    encoded, document, json_sha256 = _canonical_document(canonical_dossier_json)
    if not isinstance(projection_html, str):
        raise GoldenDemoError("projection_html must be text")
    if projection_html != render_golden_demo_html(encoded):
        raise GoldenDemoError("Golden Demo HTML is not a parity projection of the JSON")
    core = {
        "canonical_json_sha256": json_sha256,
        "dossier_id": document["dossier_id"],
        "dossier_sha256": document["dossier_sha256"],
        "projection_format": "HTML",
        "projection_sha256": _sha256_bytes(projection_html.encode("utf-8")),
        "renderer_id": "UPI-APP-FACTORY-GOLDEN-DEMO-HTML-V1",
        "schema_version": "upi_app_factory.golden-demo-projection-binding.v1",
    }
    binding_sha256 = canonical_sha256(core)
    return {
        **core,
        "binding_id": f"GOLDEN-DEMO-PROJECTION-BINDING-{binding_sha256}",
        "binding_sha256": binding_sha256,
    }


def validate_golden_demo_projection(
    canonical_dossier_json: str | bytes,
    projection_html: str,
    binding: Mapping[str, Any] | None = None,
) -> bool:
    """Verify byte parity and, when supplied, the canonical digest binding."""
    expected = build_golden_demo_projection_binding(
        canonical_dossier_json, projection_html
    )
    if binding is not None and _detached(binding, "projection binding") != expected:
        raise GoldenDemoError("Golden Demo projection binding is invalid")
    return True


def _relative_stem(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise GoldenDemoError("relative_stem must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix or "." in path.parts or ".." in path.parts:
        raise GoldenDemoError("relative_stem must be a safe extension-free relative path")
    return path


def write_golden_demo_evidence(
    root: Path, relative_stem: str, dossier: GoldenDemoDossier
) -> dict[str, str]:
    """Write canonical JSON, verified HTML, and their binding using relative paths."""
    if not isinstance(root, Path):
        raise GoldenDemoError("root must be pathlib.Path")
    if not isinstance(dossier, GoldenDemoDossier):
        raise GoldenDemoError("dossier must use GoldenDemoDossier")
    stem = _relative_stem(relative_stem)
    json_relative = PurePosixPath(f"{stem.as_posix()}.json")
    html_relative = PurePosixPath(f"{stem.as_posix()}.html")
    binding_relative = PurePosixPath(f"{stem.as_posix()}.projection.json")
    json_path = root.joinpath(*json_relative.parts)
    html_path = root.joinpath(*html_relative.parts)
    binding_path = root.joinpath(*binding_relative.parts)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = dossier.to_json()
    projection = render_golden_demo_html(encoded)
    binding = build_golden_demo_projection_binding(encoded, projection)
    json_path.write_text(encoded, encoding="utf-8")
    html_path.write_text(projection, encoding="utf-8")
    binding_path.write_text(canonical_json(binding), encoding="utf-8")
    validate_golden_demo_projection(encoded, projection, binding)
    return {
        "binding_path": binding_relative.as_posix(),
        "binding_sha256": binding["binding_sha256"],
        "dossier_id": dossier.dossier_id,
        "html_path": html_relative.as_posix(),
        "html_sha256": binding["projection_sha256"],
        "json_path": json_relative.as_posix(),
        "json_sha256": binding["canonical_json_sha256"],
    }


# Descriptive aliases keep call sites concise without introducing another model.
render_golden_demo_projection = render_golden_demo_html
validate_golden_demo_evidence = validate_golden_demo_document
write_golden_demo_pair = write_golden_demo_evidence
