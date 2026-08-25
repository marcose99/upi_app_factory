"""Governed human resolution after mandatory architecture prototype qualification.

The automated review confidence remains evidence-derived.  Human approval resolves the
selection boundary only after the approved prototype has passed every supplied mandatory
qualification check; it never rewrites or inflates machine confidence.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from .canonical import canonical_sha256
from .confidence import calculate_architecture_confidence
from .models import ArchitectureDecisionError, require_sha256
from .review_validation import require_contract_integrity


HUMAN_RESOLUTION_STATUS = (
    "HUMAN_RESOLVED_AFTER_MANDATORY_PROTOTYPE_QUALIFICATION"
)
APPROVAL_SCOPE = "ARCHITECTURE_SELECTION_ONLY_NO_TECHNICAL_GATE_WAIVER"
_BASE_PROTOTYPE_CHECKS = frozenset(
    {
        "generation_success",
        "deterministic_regeneration",
        "compileall_pass",
        "pytest_pass",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _valid_digest(value: Mapping[str, Any], field: str) -> bool:
    supplied = value.get(field)
    return isinstance(supplied, str) and supplied == canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _require_sha256_text(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ArchitectureDecisionError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _candidate_margin(
    adjudication: Mapping[str, Any],
    selected_candidate_id: str,
    review_contract: Mapping[str, Any],
) -> float:
    rows = adjudication.get("revised_scores")
    if not isinstance(rows, list):
        raise ArchitectureDecisionError("pre-resolution revised scores are missing")
    by_candidate: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ArchitectureDecisionError("pre-resolution score row is invalid")
        candidate = row.get("pattern_id")
        score = row.get("total_score")
        if not isinstance(candidate, str) or not isinstance(score, (int, float)):
            raise ArchitectureDecisionError("pre-resolution score identity is invalid")
        by_candidate[candidate] = float(score)
    if selected_candidate_id not in by_candidate:
        raise ArchitectureDecisionError("approved candidate has no revised score")
    alternatives = [
        score for candidate, score in by_candidate.items()
        if candidate != selected_candidate_id
    ]
    if not alternatives:
        return float(review_contract["confidence"]["score_margin_full_credit"])
    # A human-selected runner-up has no positive automated winner margin.  The
    # confidence calculator clamps the negative value to zero; approval does not
    # manufacture statistical certainty.
    return by_candidate[selected_candidate_id] - max(alternatives)


def _validate_approval_binding(
    binding: Mapping[str, Any],
    *,
    selected_candidate_id: str,
    requirements_sha256: str,
) -> None:
    required = {
        "schema_version",
        "status",
        "scenario_id",
        "requirements_sha256",
        "approved_selected_candidate_id",
        "approval_statement",
        "approval_record_sha256",
        "selection_digest_sha256",
        "scope",
        "quality_gates_waived",
        "approval_binding_digest",
    }
    if set(binding) != required:
        raise ArchitectureDecisionError("human approval binding fields are invalid")
    if binding.get("schema_version") != (
        "upi-app-factory.architecture-human-approval-binding.v1"
    ):
        raise ArchitectureDecisionError("human approval binding schema is invalid")
    if binding.get("status") != "APPROVED":
        raise ArchitectureDecisionError("human architecture approval is not active")
    if not isinstance(binding.get("scenario_id"), str) or not binding["scenario_id"]:
        raise ArchitectureDecisionError("human approval scenario identity is missing")
    if binding.get("requirements_sha256") != requirements_sha256:
        raise ArchitectureDecisionError("human approval requirements binding mismatch")
    if binding.get("approved_selected_candidate_id") != selected_candidate_id:
        raise ArchitectureDecisionError("human approval candidate binding mismatch")
    if not isinstance(binding.get("approval_statement"), str) or not binding[
        "approval_statement"
    ]:
        raise ArchitectureDecisionError("human approval statement is missing")
    _require_sha256_text(binding.get("approval_record_sha256"), "approval_record_sha256")
    _require_sha256_text(binding.get("selection_digest_sha256"), "selection_digest_sha256")
    if binding.get("scope") != APPROVAL_SCOPE:
        raise ArchitectureDecisionError("human approval scope is invalid")
    if binding.get("quality_gates_waived") != []:
        raise ArchitectureDecisionError("human approval cannot waive technical gates")
    if not _valid_digest(binding, "approval_binding_digest"):
        raise ArchitectureDecisionError("human approval binding digest is invalid")


def _validate_prototype_evidence(
    evidence: Mapping[str, Any],
    *,
    scenario_id: str,
    selected_candidate_id: str,
    requirements_sha256: str,
) -> None:
    required = {
        "schema_version",
        "scenario_id",
        "requirements_sha256",
        "selected_candidate_id",
        "mandatory_pass",
        "checks",
        "failure_codes",
        "prototype_package_sha256",
        "prototype_contract_sha256",
        "prototype_evidence_digest",
    }
    if set(evidence) != required:
        raise ArchitectureDecisionError("prototype qualification evidence fields are invalid")
    if evidence.get("schema_version") != (
        "upi-app-factory.architecture-prototype-qualification-evidence.v1"
    ):
        raise ArchitectureDecisionError("prototype qualification evidence schema is invalid")
    if evidence.get("scenario_id") != scenario_id:
        raise ArchitectureDecisionError("prototype scenario binding mismatch")
    if evidence.get("requirements_sha256") != requirements_sha256:
        raise ArchitectureDecisionError("prototype requirements binding mismatch")
    if evidence.get("selected_candidate_id") != selected_candidate_id:
        raise ArchitectureDecisionError("prototype candidate binding mismatch")
    if evidence.get("mandatory_pass") is not True:
        raise ArchitectureDecisionError("approved prototype did not pass mandatory gates")
    checks = evidence.get("checks")
    if not isinstance(checks, Mapping) or not checks:
        raise ArchitectureDecisionError("prototype gate outcomes are missing")
    if not _BASE_PROTOTYPE_CHECKS.issubset(checks):
        raise ArchitectureDecisionError("prototype base qualification checks are incomplete")
    if any(value is not True for value in checks.values()):
        raise ArchitectureDecisionError("approved prototype contains a failed gate")
    if evidence.get("failure_codes") != []:
        raise ArchitectureDecisionError("approved prototype contains failure codes")
    _require_sha256_text(
        evidence.get("prototype_package_sha256"), "prototype_package_sha256"
    )
    _require_sha256_text(
        evidence.get("prototype_contract_sha256"), "prototype_contract_sha256"
    )
    if not _valid_digest(evidence, "prototype_evidence_digest"):
        raise ArchitectureDecisionError("prototype qualification evidence digest is invalid")


def resolve_prototype_required_adjudication(
    *,
    pre_resolution_adjudication: Mapping[str, Any],
    packet: Mapping[str, Any],
    review_set: Mapping[str, Any],
    review_contract: Mapping[str, Any],
    selected_candidate_id: str,
    requirements_sha256: str,
    approval_binding: Mapping[str, Any],
    prototype_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deterministic, evidence-bound human resolution.

    The function is intentionally strict and reconstructable.  Package verification
    reruns it and requires byte-for-byte equality with the supplied adjudication.
    """
    require_contract_integrity(dict(review_contract), "review contract")
    require_sha256(requirements_sha256, "requirements_sha256")
    pre = deepcopy(dict(pre_resolution_adjudication))
    if not _valid_digest(pre, "adjudication_digest"):
        raise ArchitectureDecisionError("pre-resolution adjudication digest is invalid")
    if pre.get("status") != "PROTOTYPE_REQUIRED":
        raise ArchitectureDecisionError("only PROTOTYPE_REQUIRED may be human-resolved")
    if pre.get("selected_candidate_id") is not None:
        raise ArchitectureDecisionError("pre-resolution adjudication already selected a candidate")
    candidates = pre.get("prototype_candidates")
    if not isinstance(candidates, list) or selected_candidate_id not in candidates:
        raise ArchitectureDecisionError("approved candidate is not a required prototype")
    if (
        pre.get("architecture_packet_digest") != packet.get("packet_digest")
        or pre.get("review_set_digest") != review_set.get("review_set_digest")
        or pre.get("review_contract_digest") != review_contract.get("contract_digest")
    ):
        raise ArchitectureDecisionError("prototype-resolution review binding mismatch")

    _validate_approval_binding(
        approval_binding,
        selected_candidate_id=selected_candidate_id,
        requirements_sha256=requirements_sha256,
    )
    scenario_id = str(approval_binding["scenario_id"])
    _validate_prototype_evidence(
        prototype_evidence,
        scenario_id=scenario_id,
        selected_candidate_id=selected_candidate_id,
        requirements_sha256=requirements_sha256,
    )

    margin = _candidate_margin(pre, selected_candidate_id, review_contract)
    confidence = calculate_architecture_confidence(
        dict(packet),
        dict(review_set),
        selected_candidate_id,
        dict(review_contract),
        score_margin=margin,
    )
    human_resolution: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-human-prototype-resolution.v1",
        "status": HUMAN_RESOLUTION_STATUS,
        "requirements_sha256": requirements_sha256,
        "scenario_id": scenario_id,
        "approved_selected_candidate_id": selected_candidate_id,
        "pre_resolution_adjudication": deepcopy(pre),
        "pre_resolution_adjudication_digest": pre["adjudication_digest"],
        "approval_binding": deepcopy(dict(approval_binding)),
        "prototype_evidence": deepcopy(dict(prototype_evidence)),
        "automated_confidence_digest": confidence["digest"],
        "automated_confidence_level": confidence["level"],
        "automated_confidence_score": confidence["score"],
        "confidence_inflated_by_human_approval": False,
        "quality_gates_waived": [],
    }
    human_resolution["human_resolution_digest"] = canonical_sha256(human_resolution)

    result = deepcopy(pre)
    result.update(
        {
            "status": "SELECTED_REVIEWED",
            "selected_candidate_id": selected_candidate_id,
            "prototype_candidates": [],
            "selection_changed_by_review": (
                selected_candidate_id != packet.get("upstream_selected_candidate_id")
            ),
            "confidence": confidence,
            "governance_resolution_status": HUMAN_RESOLUTION_STATUS,
            "human_resolution": human_resolution,
        }
    )
    result.pop("adjudication_digest", None)
    result["adjudication_digest"] = canonical_sha256(result)
    return result


def verify_human_resolved_adjudication(
    adjudication: Mapping[str, Any],
    *,
    deterministic_pre_resolution: Mapping[str, Any],
    packet: Mapping[str, Any],
    review_set: Mapping[str, Any],
    review_contract: Mapping[str, Any],
    requirements_sha256: str,
) -> bool:
    """Reconstruct and exactly verify a human-resolved adjudication."""
    try:
        resolution = adjudication.get("human_resolution")
        if not isinstance(resolution, Mapping):
            return False
        if resolution.get("pre_resolution_adjudication") != dict(
            deterministic_pre_resolution
        ):
            return False
        selected = resolution.get("approved_selected_candidate_id")
        approval_binding = resolution.get("approval_binding")
        prototype_evidence = resolution.get("prototype_evidence")
        if (
            not isinstance(selected, str)
            or not isinstance(approval_binding, Mapping)
            or not isinstance(prototype_evidence, Mapping)
        ):
            return False
        expected = resolve_prototype_required_adjudication(
            pre_resolution_adjudication=deterministic_pre_resolution,
            packet=packet,
            review_set=review_set,
            review_contract=review_contract,
            selected_candidate_id=selected,
            requirements_sha256=requirements_sha256,
            approval_binding=approval_binding,
            prototype_evidence=prototype_evidence,
        )
        return dict(adjudication) == expected
    except (ArchitectureDecisionError, KeyError, TypeError, ValueError):
        return False
