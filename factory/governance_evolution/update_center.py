"""Deterministic, read-only Governance Update Center projections.

The Update Center consumes the immutable M2.5 governance objects; it does not
create lifecycle transitions, authority decisions, or execution pins.  Its
canonical JSON is the evidence artifact.  HTML rendering accepts only that
canonical JSON and binds itself to the SHA-256 of the exact input bytes.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Iterable, Mapping, cast

from factory.documentation import EvidenceGraph, Freshness, canonical_json, canonical_sha256
from factory.documentation.facts import FactModelError

from .control_plane import (
    AuthorityDecision,
    GovernanceControlPlane,
    GovernanceProposal,
    GovernanceValidation,
    LifecycleEvent,
    LifecycleTransition,
)
from .impact import ImpactProjection, SemanticDiff, diff_governance_snapshots, project_impact
from .snapshots import GovernanceModelError, GovernanceSnapshot, _freeze_json
from .sources import GovernanceLifecycleState, SourceVerification


class UpdateCenterError(GovernanceModelError):
    """Raised when an Update Center would contain ambiguous or broken evidence."""


class QualificationState(str, Enum):
    """Deterministic qualification states projected from the control plane."""

    NOT_PROPOSED = "NOT_PROPOSED"
    AWAITING_VALIDATION = "AWAITING_VALIDATION"
    PASSED = "PASSED"
    FAILED = "FAILED"


class AuthorityDecisionStatus(str, Enum):
    """Whether a governed authority record is ready, required, or applied."""

    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    RECORDED_AND_APPLIED = "RECORDED_AND_APPLIED"
    NOT_REQUIRED = "NOT_REQUIRED"


class UpdateCenterFreshness(str, Enum):
    """Freshness vocabulary including the explicit absence of usable evidence."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DOCUMENT_ID = "DOC-upi_app_factory-governance-update-center"
_ASSURANCE_BOUNDARIES: dict[str, str] = {
    "certification": "NOT_ASSERTED",
    "deployment": "NOT_ASSERTED",
    "production_readiness": "NOT_ASSERTED",
    "regulatory_approval": "NOT_ASSERTED",
}
_LIMITATION_TEXT: dict[str, str] = {
    "LIMITATION-AUTHORITY": (
        "This Update Center is a read-only evidence projection and is not a source "
        "of governance authority."
    ),
    "LIMITATION-EXTERNAL-ASSURANCE": (
        "Certification, regulatory approval, production readiness, deployment, and "
        "other external assurance are not asserted."
    ),
    "LIMITATION-IMPACT-UNKNOWN": (
        "Unresolved or unsupported downstream impact remains explicitly unknown."
    ),
    "LIMITATION-LINEAGE": (
        "Candidate lineage does not currently satisfy deterministic promotion preconditions."
    ),
    "LIMITATION-NO-ACTIVE-SNAPSHOT": (
        "No active governance snapshot is available for semantic comparison."
    ),
    "LIMITATION-PROVENANCE": (
        "Current authoritative provenance has not been recorded for this candidate."
    ),
}


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise UpdateCenterError(f"{field_name} must be a non-empty stable identifier")
    return value


def _frozen_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Detach and deeply freeze a JSON mapping exposed by the captured model."""
    detached = json.loads(canonical_json(dict(value)))
    return cast(Mapping[str, Any], _freeze_json(detached))


def _normalize_verifications(
    values: SourceVerification | Iterable[SourceVerification],
) -> tuple[SourceVerification, ...]:
    supplied: tuple[SourceVerification, ...]
    if isinstance(values, SourceVerification):
        supplied = (values,)
    else:
        if isinstance(values, (str, bytes)):
            raise UpdateCenterError("source_verifications must be a collection")
        try:
            supplied = tuple(values)
        except TypeError as exc:
            raise UpdateCenterError("source_verifications must be a collection") from exc
    if any(not isinstance(item, SourceVerification) for item in supplied):
        raise UpdateCenterError("source_verifications must contain SourceVerification values")
    identities = [item.verification_id for item in supplied]
    if len(identities) != len(set(identities)):
        raise UpdateCenterError("source_verifications contain duplicate identities")
    return tuple(sorted(supplied, key=lambda item: item.verification_id))


def _event(
    history: tuple[LifecycleTransition, ...], events: frozenset[LifecycleEvent]
) -> LifecycleTransition | None:
    return next((item for item in reversed(history) if item.event in events), None)


def _snapshot_view(snapshot: GovernanceSnapshot, state: GovernanceLifecycleState) -> dict[str, Any]:
    return {**snapshot.to_dict(), "lifecycle_state": state.value}


def _recorded_verification(
    control_projection: Mapping[str, Any], candidate_snapshot_id: str
) -> Mapping[str, Any] | None:
    records = control_projection.get("authority_verifications")
    if not isinstance(records, list):
        raise UpdateCenterError("control plane authority verification projection is invalid")
    matches = [
        item
        for item in records
        if isinstance(item, Mapping) and item.get("snapshot_id") == candidate_snapshot_id
    ]
    if len(matches) > 1:
        raise UpdateCenterError("candidate has ambiguous authority verification records")
    return matches[0] if matches else None


def _provenance_views(
    candidate: GovernanceSnapshot,
    recorded: Mapping[str, Any] | None,
    supplied: tuple[SourceVerification, ...],
    configured_registry_ids: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any]]:
    unconfigured_registry_ids = sorted(
        {
            item.authority_registry_id
            for item in supplied
            if item.authority_registry_id not in configured_registry_ids
        }
    )
    if unconfigured_registry_ids:
        raise UpdateCenterError(
            "source verification evidence uses an unconfigured authority registry"
        )
    recorded_ids: tuple[str, ...] = ()
    registry_id: str | None = None
    if recorded is not None:
        raw_ids = recorded.get("verification_ids")
        if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
            raise UpdateCenterError("recorded verification identities are invalid")
        recorded_ids = tuple(sorted(cast(list[str], raw_ids)))
        if len(recorded_ids) != len(set(recorded_ids)):
            raise UpdateCenterError("recorded verification identities are duplicated")
        registry_id = _identifier(recorded.get("authority_registry_id"), "authority_registry_id")
        if supplied and tuple(item.verification_id for item in supplied) != recorded_ids:
            raise UpdateCenterError(
                "supplied verification evidence does not match the recorded verification set"
            )

    candidate_bindings = {item.source_id: item for item in candidate.source_bindings}
    supplied_current: dict[str, SourceVerification] = {}
    for verification in supplied:
        binding = verification.source_binding
        if binding is None:
            continue
        expected = candidate_bindings.get(binding.source_id)
        if expected is None or expected != binding:
            raise UpdateCenterError(
                "source verification evidence references provenance outside the candidate"
            )
        if binding.source_id in supplied_current:
            raise UpdateCenterError(
                "source verification evidence duplicates a candidate source identity"
            )
        supplied_current[binding.source_id] = verification

    recorded_authority = recorded is not None
    complete_current = set(supplied_current) == set(candidate_bindings)
    any_stale = any(item.freshness is Freshness.STALE for item in supplied)
    if recorded_authority:
        overall = UpdateCenterFreshness.CURRENT
    elif any_stale:
        overall = UpdateCenterFreshness.STALE
    elif (
        supplied
        and complete_current
        and all(item.freshness is Freshness.CURRENT for item in supplied)
    ):
        overall = UpdateCenterFreshness.CURRENT
    else:
        overall = UpdateCenterFreshness.UNKNOWN

    sources: list[dict[str, Any]] = []
    for source_id, binding in sorted(candidate_bindings.items()):
        if recorded_authority or source_id in supplied_current:
            source_freshness = UpdateCenterFreshness.CURRENT
        else:
            source_freshness = UpdateCenterFreshness.UNKNOWN
        sources.append(
            {
                **binding.to_dict(),
                "authority_verified_for_snapshot": recorded_authority,
                "freshness": source_freshness.value,
            }
        )

    provenance = {
        "authority_registry_id": registry_id,
        "candidate_snapshot_id": candidate.snapshot_id,
        "recorded_verification_ids": list(recorded_ids),
        "source_bindings": sources,
        "status": ("AUTHORITY_VERIFIED" if recorded_authority else "NOT_AUTHORITY_VERIFIED"),
        "supplied_verification_evidence": [item.to_dict() for item in supplied],
    }
    freshness = {
        "candidate_snapshot_id": candidate.snapshot_id,
        "overall_status": overall.value,
        "source_statuses": [
            {"freshness": item["freshness"], "source_id": item["source_id"]} for item in sources
        ],
        "unknown_is_explicit": True,
        "verification_evidence_freshness": sorted({item.freshness.value for item in supplied}),
    }
    return provenance, freshness


def _lineage_status(
    active: GovernanceSnapshot | None,
    candidate: GovernanceSnapshot,
    candidate_state: GovernanceLifecycleState,
    known_snapshot_ids: tuple[str, ...],
    history: tuple[LifecycleTransition, ...],
) -> str:
    references = tuple(
        item
        for item in (
            candidate.previous_snapshot_id,
            candidate.supersedes_snapshot_id,
        )
        if item is not None
    )
    dangling = sorted(set(references) - set(known_snapshot_ids))
    if dangling:
        raise UpdateCenterError(
            "candidate lineage contains an unknown snapshot reference: " + ", ".join(dangling)
        )
    if active is candidate:
        return "ACTIVE_CANDIDATE"
    if candidate_state in {
        GovernanceLifecycleState.SUPERSEDED,
        GovernanceLifecycleState.REVOKED,
        GovernanceLifecycleState.QUARANTINED,
    } and any(item.to_state is GovernanceLifecycleState.ACTIVE for item in history):
        return "HISTORICALLY_ACTIVATED"
    if active is None:
        return (
            "MATCHES_NO_ACTIVE_SNAPSHOT"
            if candidate.previous_snapshot_id is None and candidate.supersedes_snapshot_id is None
            else "MISMATCH"
        )
    return (
        "MATCHES_ACTIVE_SNAPSHOT"
        if candidate.previous_snapshot_id == active.snapshot_id
        and candidate.supersedes_snapshot_id == active.snapshot_id
        else "MISMATCH"
    )


def _qualification_view(
    candidate: GovernanceSnapshot,
    proposal: GovernanceProposal | None,
    validation: GovernanceValidation | None,
) -> tuple[QualificationState, dict[str, Any]]:
    if proposal is None:
        state = QualificationState.NOT_PROPOSED
    elif validation is None:
        state = QualificationState.AWAITING_VALIDATION
    elif validation.passed:
        state = QualificationState.PASSED
    else:
        state = QualificationState.FAILED
    return state, {
        "candidate_snapshot_id": candidate.snapshot_id,
        "proposal": proposal.to_dict() if proposal is not None else None,
        "proposal_confers_authority": False,
        "state": state.value,
        "validation": validation.to_dict() if validation is not None else None,
    }


def _authority_view(
    plane: GovernanceControlPlane,
    candidate: GovernanceSnapshot,
    state: GovernanceLifecycleState,
    lineage_status: str,
    decision: AuthorityDecision | None,
) -> dict[str, Any]:
    lineage_ready = lineage_status in {
        "MATCHES_ACTIVE_SNAPSHOT",
        "MATCHES_NO_ACTIVE_SNAPSHOT",
    }
    blocker: str | None = None
    required_action: str | None = None
    decision_required = False
    if state is GovernanceLifecycleState.VALIDATED and not lineage_ready:
        status = AuthorityDecisionStatus.BLOCKED
        blocker = "PROMOTION_LINEAGE_MISMATCH"
    elif state is GovernanceLifecycleState.VALIDATED:
        status = AuthorityDecisionStatus.DECISION_REQUIRED
        required_action = "PROMOTE"
        decision_required = True
    elif decision is not None:
        status = AuthorityDecisionStatus.RECORDED_AND_APPLIED
    elif state is GovernanceLifecycleState.QUARANTINED:
        status = AuthorityDecisionStatus.NOT_REQUIRED
        blocker = "QUALIFICATION_FAILED_OR_TERMINAL_QUARANTINE"
    else:
        status = AuthorityDecisionStatus.NOT_READY

    return {
        "blocker": blocker,
        "candidate_snapshot_id": candidate.snapshot_id,
        "configured_authority_ids": list(plane.decision_authority_ids),
        "decision_record": decision.to_dict() if decision is not None else None,
        "decision_required": decision_required,
        "expected_active_snapshot_id": plane.expected_active_snapshot_id,
        "explicit_governed_authority_decision_required": True,
        "lineage_status": lineage_status,
        "required_action": required_action,
        "status": status.value,
        "ui_can_create_authority": False,
        "ui_can_mutate_pinned_execution": False,
    }


def _limitations(
    *,
    active: GovernanceSnapshot | None,
    provenance: Mapping[str, Any],
    impact: ImpactProjection | None,
    lineage_status: str,
) -> tuple[dict[str, str], ...]:
    limitation_ids = {
        "LIMITATION-AUTHORITY",
        "LIMITATION-EXTERNAL-ASSURANCE",
    }
    if active is None:
        limitation_ids.add("LIMITATION-NO-ACTIVE-SNAPSHOT")
    if provenance.get("status") != "AUTHORITY_VERIFIED":
        limitation_ids.add("LIMITATION-PROVENANCE")
    if impact is not None and impact.has_unknown_impact:
        limitation_ids.add("LIMITATION-IMPACT-UNKNOWN")
    if lineage_status == "MISMATCH":
        limitation_ids.add("LIMITATION-LINEAGE")
    return tuple(
        {"description": _LIMITATION_TEXT[item], "limitation_id": item}
        for item in sorted(limitation_ids)
    )


@dataclass(frozen=True, init=False)
class GovernanceUpdateCenter:
    """Immutable evidence view captured from one control-plane state."""

    SCHEMA_VERSION: ClassVar[str] = "upi_app_factory.governance-update-center.v1"

    active_snapshot: GovernanceSnapshot | None
    observed_candidate: GovernanceSnapshot
    candidate_state: GovernanceLifecycleState
    known_snapshot_ids: tuple[str, ...]
    verified_provenance: Mapping[str, Any]
    freshness: Mapping[str, Any]
    semantic_diff: SemanticDiff | None
    impact_projection: ImpactProjection | None
    qualification_state: Mapping[str, Any]
    authority_decision_status: Mapping[str, Any]
    execution_pinning: Mapping[str, Any]
    limitations: tuple[Mapping[str, str], ...]
    _update_center_sha256: str = field(repr=False, compare=False)

    def __init__(
        self,
        control_plane: GovernanceControlPlane,
        candidate_snapshot_id: str,
        *,
        source_verifications: SourceVerification | Iterable[SourceVerification] = (),
        semantic_diff: SemanticDiff | None = None,
        impact_projection: ImpactProjection | None = None,
        evidence_graph: EvidenceGraph | None = None,
        current_sources: Mapping[str, tuple[str, str]] | None = None,
    ) -> None:
        if not isinstance(control_plane, GovernanceControlPlane):
            raise UpdateCenterError("control_plane must be GovernanceControlPlane")
        _identifier(candidate_snapshot_id, "candidate_snapshot_id")
        candidate = control_plane.snapshot(candidate_snapshot_id)
        candidate_state = control_plane.snapshot_state(candidate_snapshot_id)
        active = control_plane.active_snapshot
        known_ids = control_plane.snapshot_ids
        history = control_plane.snapshot_history(candidate_snapshot_id)
        supplied = _normalize_verifications(source_verifications)
        recorded = _recorded_verification(control_plane.to_dict(), candidate_snapshot_id)
        provenance, freshness = _provenance_views(
            candidate,
            recorded,
            supplied,
            control_plane.authority_registry_ids,
        )

        if active is None:
            if semantic_diff is not None or impact_projection is not None:
                raise UpdateCenterError(
                    "semantic diff and impact require an active comparison snapshot"
                )
            governed_diff = None
            governed_impact = None
        else:
            governed_diff = semantic_diff or diff_governance_snapshots(active, candidate)
            if not isinstance(governed_diff, SemanticDiff):
                raise UpdateCenterError("semantic_diff must be SemanticDiff")
            if (
                governed_diff.before_snapshot_id != active.snapshot_id
                or governed_diff.after_snapshot_id != candidate.snapshot_id
            ):
                raise UpdateCenterError(
                    "semantic diff references do not match the active and candidate snapshots"
                )
            if impact_projection is not None:
                if evidence_graph is not None or current_sources is not None:
                    raise UpdateCenterError(
                        "provide either impact_projection or impact evidence inputs, not both"
                    )
                governed_impact = impact_projection
            else:
                governed_impact = project_impact(governed_diff, evidence_graph, current_sources)
            if not isinstance(governed_impact, ImpactProjection):
                raise UpdateCenterError("impact_projection must be ImpactProjection")
            if governed_impact.semantic_diff_id != governed_diff.diff_id:
                raise UpdateCenterError("impact projection references a different semantic diff")

        proposal_event = _event(history, frozenset({LifecycleEvent.PROPOSE}))
        validation_event = _event(
            history,
            frozenset({LifecycleEvent.VALIDATE, LifecycleEvent.QUALIFICATION_FAILED}),
        )
        proposal = (
            control_plane.proposal(proposal_event.cause_identity)
            if proposal_event is not None
            else None
        )
        validation = (
            control_plane.validation(validation_event.cause_identity)
            if validation_event is not None
            else None
        )
        _qualification, qualification_view = _qualification_view(candidate, proposal, validation)

        decision: AuthorityDecision | None = None
        for transition in reversed(history):
            if transition.authority_decision_id is None:
                continue
            candidate_decision = control_plane.authority_decision(transition.authority_decision_id)
            if candidate_decision.target_snapshot_id == candidate.snapshot_id:
                decision = candidate_decision
                break

        lineage = _lineage_status(active, candidate, candidate_state, known_ids, history)
        authority_view = _authority_view(
            control_plane, candidate, candidate_state, lineage, decision
        )
        pins = control_plane.execution_pins
        classifications = control_plane.classify_pinned_executions()
        execution_view: dict[str, Any] = {
            "classifications": [item.to_dict() for item in classifications],
            "immutable_execution_pins": [item.to_dict() for item in pins],
            "pinned_execution_count": len(pins),
            "ui_mutation_supported": False,
        }
        limitations = _limitations(
            active=active,
            provenance=provenance,
            impact=governed_impact,
            lineage_status=lineage,
        )

        object.__setattr__(self, "active_snapshot", active)
        object.__setattr__(self, "observed_candidate", candidate)
        object.__setattr__(self, "candidate_state", candidate_state)
        object.__setattr__(self, "known_snapshot_ids", known_ids)
        object.__setattr__(self, "verified_provenance", _frozen_mapping(provenance))
        object.__setattr__(self, "freshness", _frozen_mapping(freshness))
        object.__setattr__(self, "semantic_diff", governed_diff)
        object.__setattr__(self, "impact_projection", governed_impact)
        object.__setattr__(self, "qualification_state", _frozen_mapping(qualification_view))
        object.__setattr__(self, "authority_decision_status", _frozen_mapping(authority_view))
        object.__setattr__(self, "execution_pinning", _frozen_mapping(execution_view))
        object.__setattr__(
            self,
            "limitations",
            tuple(cast(Mapping[str, str], _freeze_json(dict(item))) for item in limitations),
        )
        object.__setattr__(
            self,
            "_update_center_sha256",
            canonical_sha256(self.identity_payload()),
        )

    @classmethod
    def from_control_plane(
        cls,
        control_plane: GovernanceControlPlane,
        candidate_snapshot_id: str,
        **kwargs: Any,
    ) -> GovernanceUpdateCenter:
        """Build a captured view without retaining a mutable plane reference."""
        return cls(control_plane, candidate_snapshot_id, **kwargs)

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def document_id(self) -> str:
        return _DOCUMENT_ID

    @property
    def update_center_sha256(self) -> str:
        return self._update_center_sha256

    @property
    def identity_sha256(self) -> str:
        return self.update_center_sha256

    @property
    def update_center_id(self) -> str:
        return f"GOVERNANCE-UPDATE-CENTER-{self.update_center_sha256}"

    @property
    def json_sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def identity_payload(self) -> dict[str, Any]:
        projection = {
            "active_snapshot": (
                _snapshot_view(self.active_snapshot, GovernanceLifecycleState.ACTIVE)
                if self.active_snapshot is not None
                else None
            ),
            "assurance_boundaries": dict(_ASSURANCE_BOUNDARIES),
            "authority_decision_status": dict(self.authority_decision_status),
            "document_id": self.document_id,
            "execution_pinning": dict(self.execution_pinning),
            "freshness": dict(self.freshness),
            "impact": (
                self.impact_projection.to_dict() if self.impact_projection is not None else None
            ),
            "limitations": [dict(item) for item in self.limitations],
            "observed_candidate": _snapshot_view(self.observed_candidate, self.candidate_state),
            "qualification_state": dict(self.qualification_state),
            "schema_version": self.schema_version,
            "semantic_diff": (
                self.semantic_diff.to_dict() if self.semantic_diff is not None else None
            ),
            "snapshot_catalog_ids": list(self.known_snapshot_ids),
            "verified_provenance": dict(self.verified_provenance),
        }
        return cast(dict[str, Any], json.loads(canonical_json(projection)))

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "update_center_id": self.update_center_id,
            "update_center_sha256": self.update_center_sha256,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UpdateCenterError(f"{field_name} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _list(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise UpdateCenterError(f"{field_name} must be a JSON array")
    return value


def validate_update_center_document(document: Mapping[str, Any]) -> None:
    """Fail closed on digest tampering, broken references, or authority claims."""
    if not isinstance(document, Mapping):
        raise UpdateCenterError("Update Center document must be a JSON object")
    if document.get("schema_version") != GovernanceUpdateCenter.SCHEMA_VERSION:
        raise UpdateCenterError("unsupported Governance Update Center schema")
    if document.get("document_id") != _DOCUMENT_ID:
        raise UpdateCenterError("unexpected Governance Update Center document identity")
    supplied_sha = document.get("update_center_sha256")
    if not isinstance(supplied_sha, str) or not _SHA256.fullmatch(supplied_sha):
        raise UpdateCenterError("update_center_sha256 must be a lowercase SHA-256 digest")
    identity = dict(document)
    identity.pop("update_center_id", None)
    identity.pop("update_center_sha256", None)
    if canonical_sha256(identity) != supplied_sha:
        raise UpdateCenterError("Governance Update Center identity digest mismatch")
    if document.get("update_center_id") != f"GOVERNANCE-UPDATE-CENTER-{supplied_sha}":
        raise UpdateCenterError("Governance Update Center identity is inconsistent")

    if document.get("assurance_boundaries") != _ASSURANCE_BOUNDARIES:
        raise UpdateCenterError("unsupported assurance claim in Update Center")
    limitations = _list(document.get("limitations"), "limitations")
    for raw in limitations:
        limitation = _mapping(raw, "limitation")
        limitation_id = limitation.get("limitation_id")
        if not isinstance(limitation_id, str) or _LIMITATION_TEXT.get(limitation_id) != (
            limitation.get("description")
        ):
            raise UpdateCenterError("unsupported or altered limitation claim")

    catalog = _list(document.get("snapshot_catalog_ids"), "snapshot_catalog_ids")
    if any(not isinstance(item, str) for item in catalog) or catalog != sorted(set(catalog)):
        raise UpdateCenterError("snapshot_catalog_ids must be stable, unique, and ordered")
    known_ids = set(cast(list[str], catalog))
    candidate = _mapping(document.get("observed_candidate"), "observed_candidate")
    candidate_id = _identifier(candidate.get("snapshot_id"), "candidate snapshot_id")
    if candidate_id not in known_ids:
        raise UpdateCenterError("observed candidate is absent from the snapshot catalog")
    for field_name in ("previous_snapshot_id", "supersedes_snapshot_id"):
        reference = candidate.get(field_name)
        if reference is not None and reference not in known_ids:
            raise UpdateCenterError(f"broken candidate {field_name} reference")

    active_raw = document.get("active_snapshot")
    active_id: str | None = None
    if active_raw is not None:
        active = _mapping(active_raw, "active_snapshot")
        active_id = _identifier(active.get("snapshot_id"), "active snapshot_id")
        if active_id not in known_ids:
            raise UpdateCenterError("active snapshot is absent from the snapshot catalog")
        if active.get("lifecycle_state") != GovernanceLifecycleState.ACTIVE.value:
            raise UpdateCenterError("active snapshot must have ACTIVE lifecycle state")

    semantic_raw = document.get("semantic_diff")
    semantic_id: str | None = None
    if semantic_raw is not None:
        semantic = _mapping(semantic_raw, "semantic_diff")
        semantic_id = _identifier(semantic.get("diff_id"), "semantic diff_id")
        if semantic.get("before_snapshot_id") != active_id:
            raise UpdateCenterError("semantic diff has a broken active snapshot reference")
        if semantic.get("after_snapshot_id") != candidate_id:
            raise UpdateCenterError("semantic diff has a broken candidate snapshot reference")
    elif active_id is not None:
        raise UpdateCenterError("an active snapshot requires a semantic diff")

    impact_raw = document.get("impact")
    if impact_raw is not None:
        impact = _mapping(impact_raw, "impact")
        if impact.get("semantic_diff_id") != semantic_id:
            raise UpdateCenterError("impact has a broken semantic diff reference")
    elif semantic_id is not None:
        raise UpdateCenterError("a semantic diff requires an impact projection")

    provenance = _mapping(document.get("verified_provenance"), "verified_provenance")
    freshness = _mapping(document.get("freshness"), "freshness")
    if provenance.get("candidate_snapshot_id") != candidate_id:
        raise UpdateCenterError("provenance has a broken candidate snapshot reference")
    if freshness.get("candidate_snapshot_id") != candidate_id:
        raise UpdateCenterError("freshness has a broken candidate snapshot reference")

    qualification = _mapping(document.get("qualification_state"), "qualification_state")
    if qualification.get("candidate_snapshot_id") != candidate_id:
        raise UpdateCenterError("qualification has a broken candidate snapshot reference")
    proposal_raw = qualification.get("proposal")
    proposal_id: str | None = None
    if proposal_raw is not None:
        proposal = _mapping(proposal_raw, "qualification proposal")
        if proposal.get("target_snapshot_id") != candidate_id:
            raise UpdateCenterError("proposal has a broken candidate snapshot reference")
        proposal_id = _identifier(proposal.get("proposal_id"), "proposal_id")
    validation_raw = qualification.get("validation")
    validation_id: str | None = None
    if validation_raw is not None:
        validation = _mapping(validation_raw, "qualification validation")
        if validation.get("target_snapshot_id") != candidate_id:
            raise UpdateCenterError("validation has a broken candidate snapshot reference")
        if validation.get("proposal_id") != proposal_id:
            raise UpdateCenterError("validation has a broken proposal reference")
        validation_id = _identifier(validation.get("validation_id"), "validation_id")
    if qualification.get("proposal_confers_authority") is not False:
        raise UpdateCenterError("a proposal cannot confer governance authority")

    authority = _mapping(document.get("authority_decision_status"), "authority_decision_status")
    if authority.get("candidate_snapshot_id") != candidate_id:
        raise UpdateCenterError("authority status has a broken candidate snapshot reference")
    if authority.get("explicit_governed_authority_decision_required") is not True:
        raise UpdateCenterError("authority requirement cannot be omitted")
    if authority.get("ui_can_create_authority") is not False:
        raise UpdateCenterError("Update Center cannot manufacture authority")
    if authority.get("ui_can_mutate_pinned_execution") is not False:
        raise UpdateCenterError("Update Center cannot mutate a pinned execution")
    decision_raw = authority.get("decision_record")
    if decision_raw is not None:
        decision = _mapping(decision_raw, "authority decision")
        if decision.get("target_snapshot_id") != candidate_id:
            raise UpdateCenterError("authority decision has a broken candidate reference")
        if decision.get("action") == "PROMOTE":
            if decision.get("proposal_id") != proposal_id:
                raise UpdateCenterError("authority decision has a broken proposal reference")
            if decision.get("validation_id") != validation_id:
                raise UpdateCenterError("authority decision has a broken validation reference")
    if authority.get("decision_required") is True:
        if authority.get("status") != AuthorityDecisionStatus.DECISION_REQUIRED.value:
            raise UpdateCenterError("decision-required status is inconsistent")
        if decision_raw is not None:
            raise UpdateCenterError("decision-required state cannot contain a decision record")

    execution = _mapping(document.get("execution_pinning"), "execution_pinning")
    if execution.get("ui_mutation_supported") is not False:
        raise UpdateCenterError("Update Center cannot mutate execution pins")
    pins = _list(execution.get("immutable_execution_pins"), "immutable_execution_pins")
    if execution.get("pinned_execution_count") != len(pins):
        raise UpdateCenterError("pinned execution count is inconsistent")
    for raw_pin in pins:
        pin = _mapping(raw_pin, "execution pin")
        snapshot_id = pin.get("governance_snapshot_id")
        if snapshot_id not in known_ids:
            raise UpdateCenterError("execution pin has a broken snapshot reference")
        fingerprint = _mapping(pin.get("execution_fingerprint"), "execution fingerprint")
        if fingerprint.get("governance_snapshot_identity") != snapshot_id:
            raise UpdateCenterError("execution pin has a broken fingerprint reference")


def _canonical_document(value: str | bytes) -> tuple[str, Mapping[str, Any], str]:
    if isinstance(value, bytes):
        try:
            encoded = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UpdateCenterError("Update Center JSON must be UTF-8") from exc
    elif isinstance(value, str):
        encoded = value
    else:
        raise UpdateCenterError("HTML rendering requires canonical JSON text or bytes")
    try:
        parsed = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise UpdateCenterError("Update Center JSON is invalid") from exc
    if not isinstance(parsed, Mapping):
        raise UpdateCenterError("Update Center JSON must contain an object")
    try:
        normalized = canonical_json(parsed)
    except FactModelError as exc:
        raise UpdateCenterError("Update Center JSON is not canonical data") from exc
    if encoded != normalized:
        raise UpdateCenterError("HTML rendering requires exact canonical JSON")
    document = cast(Mapping[str, Any], parsed)
    validate_update_center_document(document)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return encoded, document, digest


def _display(value: object) -> str:
    if value is None:
        rendered = "NOT AVAILABLE"
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, list):
        rendered = ", ".join(str(item) for item in value) if value else "NONE"
    else:
        rendered = str(value)
    return html.escape(rendered, quote=True)


def _summary_table(caption: str, rows: Iterable[tuple[str, object]], table_id: str) -> str:
    body = "".join(
        '<tr><th scope="row">'
        + html.escape(label, quote=True)
        + "</th><td>"
        + _display(value)
        + "</td></tr>"
        for label, value in rows
    )
    return (
        f'<table id="{table_id}"><caption>{html.escape(caption)}</caption>'
        f"<tbody>{body}</tbody></table>"
    )


def render_update_center_html(canonical_update_center_json: str | bytes) -> str:
    """Render accessible offline HTML from canonical JSON and no other state."""
    encoded, document, json_digest = _canonical_document(canonical_update_center_json)
    active_raw = document.get("active_snapshot")
    active = _mapping(active_raw, "active_snapshot") if active_raw is not None else {}
    candidate = _mapping(document["observed_candidate"], "observed_candidate")
    provenance = _mapping(document["verified_provenance"], "verified_provenance")
    freshness = _mapping(document["freshness"], "freshness")
    semantic_raw = document.get("semantic_diff")
    semantic = _mapping(semantic_raw, "semantic_diff") if semantic_raw is not None else {}
    impact_raw = document.get("impact")
    impact = _mapping(impact_raw, "impact") if impact_raw is not None else {}
    qualification = _mapping(document["qualification_state"], "qualification_state")
    authority = _mapping(document["authority_decision_status"], "authority_decision_status")
    execution = _mapping(document["execution_pinning"], "execution_pinning")
    limitations = _list(document["limitations"], "limitations")

    diff_counts = {
        name: len(_list(semantic.get(name, []), f"semantic_diff.{name}"))
        for name in ("added", "changed", "removed")
    }
    affected_count = sum(
        len(_list(impact.get(field_name, []), f"impact.{field_name}"))
        for field_name in (
            "affected_fact_ids",
            "affected_rule_ids",
            "affected_capability_ids",
            "affected_template_ids",
            "affected_generated_application_provenance_ids",
        )
    )
    limitation_items = "".join(
        "<li><strong>"
        + _display(_mapping(item, "limitation").get("limitation_id"))
        + ":</strong> "
        + _display(_mapping(item, "limitation").get("description"))
        + "</li>"
        for item in limitations
    )
    canonical_payload = html.escape(encoded, quote=False)

    active_table = _summary_table(
        "Active governance snapshot",
        (
            ("Snapshot identity", active.get("snapshot_id")),
            ("Version", active.get("version_id")),
            ("Lifecycle", active.get("lifecycle_state", "NO ACTIVE SNAPSHOT")),
            ("Payload SHA-256", active.get("payload_sha256")),
        ),
        "active-snapshot-summary",
    )
    candidate_table = _summary_table(
        "Observed candidate",
        (
            ("Snapshot identity", candidate.get("snapshot_id")),
            ("Version", candidate.get("version_id")),
            ("Lifecycle", candidate.get("lifecycle_state")),
            ("Payload SHA-256", candidate.get("payload_sha256")),
        ),
        "candidate-summary",
    )
    provenance_table = _summary_table(
        "Provenance and freshness",
        (
            ("Authority verification", provenance.get("status")),
            ("Authority registry", provenance.get("authority_registry_id")),
            ("Verification identities", provenance.get("recorded_verification_ids")),
            ("Overall freshness", freshness.get("overall_status")),
        ),
        "provenance-summary",
    )
    diff_table = _summary_table(
        "Deterministic semantic diff",
        (
            ("Diff identity", semantic.get("diff_id")),
            ("Added", diff_counts["added"]),
            ("Changed", diff_counts["changed"]),
            ("Removed", diff_counts["removed"]),
        ),
        "diff-summary",
    )
    impact_table = _summary_table(
        "Evidence-backed impact",
        (
            ("Impact identity", impact.get("impact_id")),
            ("Affected governed identities", affected_count),
            ("Unknown impact", impact.get("has_unknown_impact", "NOT AVAILABLE")),
            ("Unresolved references", impact.get("unresolved_reference_ids", [])),
        ),
        "impact-summary",
    )
    qualification_table = _summary_table(
        "Qualification",
        (
            ("State", qualification.get("state")),
            (
                "Proposal origin",
                _mapping(qualification["proposal"], "proposal").get("origin")
                if qualification.get("proposal") is not None
                else None,
            ),
            ("Proposal confers authority", qualification.get("proposal_confers_authority")),
        ),
        "qualification-summary",
    )
    authority_table = _summary_table(
        "Authority decision status",
        (
            ("Status", authority.get("status")),
            ("Decision required", authority.get("decision_required")),
            ("Required action", authority.get("required_action")),
            ("Explicit governed authority record required", True),
            ("Expected active snapshot", authority.get("expected_active_snapshot_id")),
        ),
        "authority-summary",
    )

    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="json-sha256" content="{json_digest}">'
        "<title>UPI App Factory Governance Update Center</title>"
        "<style>body{font-family:system-ui,sans-serif;line-height:1.5;max-width:76rem;"
        "margin:auto;padding:1rem;color:#17202a}section{margin:1.5rem 0}table{border-collapse:"
        "collapse;width:100%}caption{text-align:left;font-weight:700}th,td{border:1px solid "
        "#68737d;padding:.45rem;text-align:left;vertical-align:top}th{width:34%}code,pre{font-"
        "family:ui-monospace,monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;border:"
        "1px solid #68737d;padding:.75rem}button[disabled]{cursor:not-allowed}</style></head>"
        '<body><a href="#main">Skip to evidence</a><main id="main">'
        "<h1>Governance Update Center</h1>"
        '<p role="status">Read-only evidence projection. Observation is not activation.</p>'
        f"<p>Canonical JSON SHA-256: <code>{json_digest}</code></p>"
        '<section aria-labelledby="snapshots-heading"><h2 id="snapshots-heading">Snapshots</h2>'
        f"{active_table}{candidate_table}</section>"
        '<section aria-labelledby="provenance-heading"><h2 id="provenance-heading">Verified provenance and freshness</h2>'
        f"{provenance_table}</section>"
        '<section aria-labelledby="change-heading"><h2 id="change-heading">Semantic change and impact</h2>'
        f"{diff_table}{impact_table}</section>"
        '<section aria-labelledby="qualification-heading"><h2 id="qualification-heading">Qualification</h2>'
        f"{qualification_table}</section>"
        '<section aria-labelledby="authority-heading"><h2 id="authority-heading">Authority decision</h2>'
        f"{authority_table}"
        '<button type="button" disabled aria-disabled="true" data-requires-authority-record="true">'
        "Read-only: submit an explicit governed AuthorityDecision through the control plane"
        "</button></section>"
        '<section aria-labelledby="execution-heading"><h2 id="execution-heading">Execution pinning</h2>'
        + _summary_table(
            "Immutable execution pins",
            (
                ("Pinned executions", execution.get("pinned_execution_count")),
                ("UI mutation supported", execution.get("ui_mutation_supported")),
            ),
            "execution-summary",
        )
        + "</section>"
        '<section aria-labelledby="limitations-heading"><h2 id="limitations-heading">Limitations</h2>'
        f"<ul>{limitation_items}</ul></section>"
        '<section aria-labelledby="canonical-heading"><h2 id="canonical-heading">Canonical JSON evidence</h2>'
        "<details><summary>Show exact canonical JSON</summary>"
        f'<pre id="canonical-json">{canonical_payload}</pre></details></section>'
        "</main><footer><p>This HTML is a deterministic offline projection of canonical JSON "
        f"with SHA-256 <code>{json_digest}</code>.</p></footer></body></html>\n"
    )


def _relative_stem(value: str) -> PurePosixPath:
    _identifier(value, "relative_stem")
    if "\\" in value:
        raise UpdateCenterError("relative_stem must use portable POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise UpdateCenterError("relative_stem must be a safe relative path")
    if path.suffix:
        raise UpdateCenterError("relative_stem must not include a file extension")
    return path


def write_update_center_pair(
    root: Path, relative_stem: str, update_center: GovernanceUpdateCenter
) -> dict[str, str]:
    """Write a portal-compatible pair while returning relative public paths only."""
    if not isinstance(root, Path):
        raise UpdateCenterError("root must be pathlib.Path")
    if not isinstance(update_center, GovernanceUpdateCenter):
        raise UpdateCenterError("update_center must be GovernanceUpdateCenter")
    stem = _relative_stem(relative_stem)
    json_relative = PurePosixPath(f"{stem.as_posix()}.json")
    html_relative = PurePosixPath(f"{stem.as_posix()}.html")
    json_path = root.joinpath(*json_relative.parts)
    html_path = root.joinpath(*html_relative.parts)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = update_center.to_json().encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    json_path.write_bytes(encoded)
    html_path.write_text(render_update_center_html(encoded), encoding="utf-8")
    return {
        "document_id": update_center.document_id,
        "html_path": html_relative.as_posix(),
        "json_path": json_relative.as_posix(),
        "json_sha256": digest,
    }


# Concise aliases retain a single canonical model and renderer.
UpdateCenterModel = GovernanceUpdateCenter
build_update_center = GovernanceUpdateCenter.from_control_plane
build_governance_update_center = GovernanceUpdateCenter.from_control_plane
render_governance_update_center_html = render_update_center_html
