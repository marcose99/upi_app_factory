"""Architecture-decision dossier and NFR sufficiency claim-scope gate.

The dossier is a deterministic, human-reviewable projection of the already-governed
architecture package.  It does not rescore candidates or manufacture missing NFRs.
Instead it binds the requirements, drivers, candidate comparison, review/prototype
outcomes, selected realization, conformance proof, trade-off evidence and evolution
triggers into one reconstructable artifact.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping

from .canonical import canonical_sha256
from .models import ArchitectureDecisionError
from .reviewed_freeze import verify_reviewed_architecture_package


DOSSIER_SCHEMA_VERSION = "upi-app-factory.architecture-decision-dossier.v1"
NFR_GATE_SCHEMA_VERSION = "upi-app-factory.architecture-nfr-sufficiency-gate.v1"
BOUNDED_CLAIM_STATUS = "ARCHITECTURE_BEST_FIT_WITHIN_CURRENT_EVIDENCE_ENVELOPE"
SUFFICIENT_CLAIM_STATUS = "ARCHITECTURE_BEST_FIT_WITHIN_GOVERNED_CANDIDATE_SET"
NFR_CONFIDENCE_FLOOR = 0.8
ARCHITECTURE_CHANGING_NFR_DRIVER_IDS = (
    "availability_slo",
    "peak_tps",
    "latency_slo_ms",
    "data_volume",
    "retention_days",
    "rpo_seconds",
    "rto_seconds",
    "deployment_independence",
)


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArchitectureDecisionError(f"{label} must be a mapping")
    return value


def _finite_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    return number if 0.0 <= number <= 1.0 else 0.0


def evaluate_nfr_sufficiency(driver_ir: Mapping[str, Any]) -> dict[str, Any]:
    """Gate the scope of architecture claims without inventing missing NFR values."""
    drivers = driver_ir.get("drivers")
    if not isinstance(drivers, list):
        raise ArchitectureDecisionError("architecture driver IR is missing drivers")
    by_id: dict[str, Mapping[str, Any]] = {}
    for raw in drivers:
        row = _require_mapping(raw, "architecture driver")
        driver_id = row.get("driver_id")
        if not isinstance(driver_id, str) or not driver_id:
            raise ArchitectureDecisionError("architecture driver ID is invalid")
        if driver_id in by_id:
            raise ArchitectureDecisionError(f"duplicate architecture driver: {driver_id}")
        by_id[driver_id] = row

    observed: list[dict[str, Any]] = []
    missing: list[str] = []
    unknown: list[str] = []
    low_confidence: list[str] = []
    for driver_id in ARCHITECTURE_CHANGING_NFR_DRIVER_IDS:
        nfr_row = by_id.get(driver_id)
        if nfr_row is None:
            missing.append(driver_id)
            continue
        source_class = str(nfr_row.get("source_class", "UNKNOWN"))
        value = deepcopy(nfr_row.get("value"))
        confidence = _finite_confidence(nfr_row.get("confidence"))
        observed.append(
            {
                "driver_id": driver_id,
                "source_class": source_class,
                "value": value,
                "confidence": confidence,
                "evidence": deepcopy(nfr_row.get("evidence", [])),
            }
        )
        if source_class == "UNKNOWN" or value is None:
            unknown.append(driver_id)
        elif confidence < NFR_CONFIDENCE_FLOOR:
            low_confidence.append(driver_id)

    sufficient = not missing and not unknown and not low_confidence
    claim_status = SUFFICIENT_CLAIM_STATUS if sufficient else BOUNDED_CLAIM_STATUS
    claim_text = (
        "Selected architecture is the best fit among the governed candidate patterns "
        "for the currently evidenced requirements and architecture-changing NFRs."
        if sufficient
        else "Selected architecture is the best fit among the governed candidate patterns "
        "within the current evidence envelope; one or more architecture-changing NFRs "
        "remain missing, unknown, or below the confidence floor."
    )
    result: dict[str, Any] = {
        "schema_version": NFR_GATE_SCHEMA_VERSION,
        "requirements_sha256": driver_ir.get("requirements_sha256"),
        "required_driver_ids": list(ARCHITECTURE_CHANGING_NFR_DRIVER_IDS),
        "confidence_floor": NFR_CONFIDENCE_FLOOR,
        "observed_drivers": observed,
        "missing_driver_ids": sorted(missing),
        "unknown_driver_ids": sorted(unknown),
        "low_confidence_driver_ids": sorted(low_confidence),
        "sufficient_for_unbounded_within_candidate_set_claim": sufficient,
        "gate_outcome": "PASS_SUFFICIENT" if sufficient else "PASS_BOUNDED_CLAIM_REQUIRED",
        "architecture_claim_status": claim_status,
        "architecture_claim_text": claim_text,
        "global_optimum_claim_allowed": False,
    }
    result["digest"] = canonical_sha256(result)
    return result


def _selected_profile(packet: Mapping[str, Any], selected: str) -> Mapping[str, Any]:
    rows = [
        row
        for row in packet.get("candidate_profiles", [])
        if isinstance(row, Mapping) and row.get("pattern_id") == selected
    ]
    if len(rows) != 1:
        raise ArchitectureDecisionError("selected architecture candidate profile is missing")
    return rows[0]


def _candidate_matrix(package: Mapping[str, Any], selected: str) -> list[dict[str, Any]]:
    packet = _require_mapping(package.get("architecture_packet"), "architecture packet")
    adjudication = _require_mapping(package.get("adjudication"), "architecture adjudication")
    base_scores = {
        str(row.get("pattern_id")): row
        for row in packet.get("scores", [])
        if isinstance(row, Mapping) and isinstance(row.get("pattern_id"), str)
    }
    revised_scores = {
        str(row.get("pattern_id")): row
        for row in adjudication.get("revised_scores", [])
        if isinstance(row, Mapping) and isinstance(row.get("pattern_id"), str)
    }
    profiles = {
        str(row.get("pattern_id")): row
        for row in packet.get("candidate_profiles", [])
        if isinstance(row, Mapping) and isinstance(row.get("pattern_id"), str)
    }
    constraints = packet.get("constraints", {})
    constraints_map = constraints if isinstance(constraints, Mapping) else {}
    vetoed = set(adjudication.get("vetoed_candidates", []))
    candidate_ids = sorted(set(base_scores) | set(revised_scores) | set(profiles))
    matrix: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        profile = profiles.get(candidate_id, {})
        constraint = constraints_map.get(candidate_id, {})
        constraint_outcome = (
            str(constraint.get("outcome", "UNKNOWN"))
            if isinstance(constraint, Mapping)
            else "UNKNOWN"
        )
        execution_state = str(profile.get("execution_state", "UNKNOWN"))
        if candidate_id in vetoed:
            disposition = "VETOED_BY_REVIEW"
        elif constraint_outcome != "ALLOW":
            disposition = f"CONSTRAINT_{constraint_outcome}"
        elif execution_state != "EXECUTABLE":
            disposition = execution_state
        else:
            disposition = "ELIGIBLE"
        base = base_scores.get(candidate_id, {})
        revised = revised_scores.get(candidate_id, {})
        matrix.append(
            {
                "pattern_id": candidate_id,
                "selected": candidate_id == selected,
                "disposition": disposition,
                "constraint_outcome": constraint_outcome,
                "constraint_findings": deepcopy(
                    constraint.get("findings", []) if isinstance(constraint, Mapping) else []
                ),
                "execution_state": execution_state,
                "required_technologies": deepcopy(profile.get("required_technologies", [])),
                "base_total_score": base.get("total_score"),
                "revised_total_score": revised.get("total_score"),
                "revised_dimension_scores": deepcopy(revised.get("dimension_scores", {})),
            }
        )
    return sorted(
        matrix,
        key=lambda row: (
            -float(row["revised_total_score"] or row["base_total_score"] or -1),
            row["pattern_id"],
        ),
    )


def _review_summary(package: Mapping[str, Any], selected: str) -> dict[str, Any]:
    review_set = _require_mapping(package.get("review_set"), "architecture review set")
    adjudication = _require_mapping(package.get("adjudication"), "architecture adjudication")
    reports = review_set.get("reports", [])
    if not isinstance(reports, list) or not reports:
        raise ArchitectureDecisionError("architecture review reports are missing")
    recommendations = Counter(
        str(report.get("recommended_candidate_id", ""))
        for report in reports
        if isinstance(report, Mapping)
    )
    selected_findings: list[dict[str, Any]] = []
    for report in reports:
        if not isinstance(report, Mapping):
            continue
        for finding in report.get("findings", []):
            if isinstance(finding, Mapping) and finding.get("candidate_id") == selected:
                selected_findings.append(deepcopy(dict(finding)))
    return {
        "lane_count": len(reports),
        "lane_ids": deepcopy(review_set.get("lane_ids", [])),
        "recommendations_by_candidate": dict(sorted(recommendations.items())),
        "selected_recommendation_count": recommendations[selected],
        "selected_recommendation_ratio": round(recommendations[selected] / len(reports), 6),
        "selected_candidate_findings": selected_findings,
        "vetoed_candidates": deepcopy(adjudication.get("vetoed_candidates", [])),
        "veto_findings": deepcopy(adjudication.get("veto_findings", [])),
    }


def _sensitivity_summary(packet: Mapping[str, Any]) -> dict[str, Any]:
    sensitivity = packet.get("sensitivity", {})
    source = sensitivity if isinstance(sensitivity, Mapping) else {}
    scenarios: list[dict[str, Any]] = []
    for raw in source.get("scenarios", []):
        if not isinstance(raw, Mapping):
            continue
        scenarios.append(
            {
                "scenario_id": raw.get("scenario_id"),
                "winner": raw.get("winner"),
            }
        )
    return {
        "base_winner": source.get("base_winner"),
        "winner_stability": packet.get("winner_stability", source.get("winner_stability")),
        "scenarios": scenarios,
        "sensitivity_digest": packet.get("sensitivity_digest", source.get("digest")),
    }


def _prototype_summary(adjudication: Mapping[str, Any]) -> dict[str, Any]:
    resolution = adjudication.get("human_resolution")
    if not isinstance(resolution, Mapping):
        return {
            "human_resolution_applied": False,
            "prototype_evidence": None,
            "approval_scope": None,
            "quality_gates_waived": [],
            "confidence_inflated_by_human_approval": False,
        }
    binding = resolution.get("approval_binding", {})
    binding_map = binding if isinstance(binding, Mapping) else {}
    return {
        "human_resolution_applied": True,
        "governance_resolution_status": adjudication.get("governance_resolution_status"),
        "approved_selected_candidate_id": resolution.get("approved_selected_candidate_id"),
        "approval_scope": binding_map.get("scope"),
        "prototype_evidence": deepcopy(resolution.get("prototype_evidence")),
        "quality_gates_waived": deepcopy(resolution.get("quality_gates_waived", [])),
        "confidence_inflated_by_human_approval": bool(
            resolution.get("confidence_inflated_by_human_approval", False)
        ),
    }


def _tradeoff_summary(matrix: list[dict[str, Any]], review: Mapping[str, Any]) -> dict[str, Any]:
    selected = next((row for row in matrix if row["selected"]), None)
    if selected is None:
        raise ArchitectureDecisionError("selected architecture is absent from candidate matrix")
    dimensions = selected.get("revised_dimension_scores", {})
    dimension_rows = (
        sorted(
            (
                {"dimension": str(name), "score": float(score)}
                for name, score in dimensions.items()
                if isinstance(score, (int, float)) and not isinstance(score, bool)
            ),
            key=lambda row: (row["score"], row["dimension"]),
        )[:4]
        if isinstance(dimensions, Mapping)
        else []
    )
    return {
        "basis": (
            "Evidence-derived only: lowest revised score dimensions plus selected-candidate "
            "review findings. No additional trade-offs are inferred."
        ),
        "lowest_revised_dimensions": dimension_rows,
        "selected_candidate_review_findings": deepcopy(
            review.get("selected_candidate_findings", [])
        ),
    }


def build_architecture_decision_dossier(
    package: Mapping[str, Any], conformance_report: Mapping[str, Any]
) -> dict[str, Any]:
    """Build the deterministic decision dossier from governed architecture evidence."""
    if not verify_reviewed_architecture_package(package):
        raise ArchitectureDecisionError("reviewed architecture package is invalid")
    conformance = _require_mapping(conformance_report, "architecture conformance report")
    if conformance.get("status") != "PASS":
        raise ArchitectureDecisionError("architecture dossier requires passing conformance")
    supplied_conformance_digest = conformance.get("conformance_digest")
    expected_conformance_digest = canonical_sha256(
        {key: value for key, value in conformance.items() if key != "conformance_digest"}
    )
    if supplied_conformance_digest != expected_conformance_digest:
        raise ArchitectureDecisionError("architecture conformance digest is invalid")
    selected = package["reviewed_freeze"].get("selected_candidate_id")
    adapter_id = package["reviewed_freeze"].get("adapter_id")
    if (
        conformance.get("selected_candidate_id") != selected
        or conformance.get("adapter_id") != adapter_id
        or conformance.get("architecture_freeze_digest")
        != package["reviewed_freeze"].get("freeze_digest")
        or conformance.get("realization_contract_digest")
        != package["reviewed_freeze"].get("realization_contract_digest")
    ):
        raise ArchitectureDecisionError("architecture conformance binding mismatch")
    if not isinstance(selected, str) or not selected:
        raise ArchitectureDecisionError("reviewed architecture selection is missing")
    packet = _require_mapping(package.get("architecture_packet"), "architecture packet")
    adjudication = _require_mapping(package.get("adjudication"), "architecture adjudication")
    driver_ir = _require_mapping(package.get("driver_ir"), "architecture driver IR")
    matrix = _candidate_matrix(package, selected)
    review = _review_summary(package, selected)
    nfr = evaluate_nfr_sufficiency(driver_ir)
    selected_profile = _selected_profile(packet, selected)
    dossier: dict[str, Any] = {
        "schema_version": DOSSIER_SCHEMA_VERSION,
        "requirements_sha256": package["reviewed_freeze"].get("requirements_sha256"),
        "reviewed_architecture_package_digest": package.get("package_digest"),
        "selected_candidate_id": selected,
        "selected_adapter_id": adapter_id,
        "architecture_claim_status": nfr["architecture_claim_status"],
        "architecture_claim_text": nfr["architecture_claim_text"],
        "global_optimum_claim_allowed": False,
        "nfr_sufficiency_gate": nfr,
        "architecture_drivers": deepcopy(driver_ir.get("drivers", [])),
        "candidate_matrix": matrix,
        "disqualified_candidates": [
            {
                "pattern_id": row["pattern_id"],
                "disposition": row["disposition"],
                "constraint_findings": deepcopy(row["constraint_findings"]),
            }
            for row in matrix
            if row["disposition"] != "ELIGIBLE" and not row["selected"]
        ],
        "sensitivity": _sensitivity_summary(packet),
        "review_consensus": review,
        "prototype_and_human_resolution": _prototype_summary(adjudication),
        "final_confidence": deepcopy(adjudication.get("confidence")),
        "selected_realization": {
            "pattern_id": selected,
            "adapter_id": adapter_id,
            "execution_state": selected_profile.get("execution_state"),
            "required_technologies": deepcopy(selected_profile.get("required_technologies", [])),
        },
        "architecture_conformance": {
            "status": conformance.get("status"),
            "failed_rules": deepcopy(conformance.get("failed_rules", [])),
            "conformance_digest": conformance.get("conformance_digest"),
        },
        "known_tradeoffs": _tradeoff_summary(matrix, review),
        "reconsideration_triggers": deepcopy(
            package["evolution_contract"].get("reconsideration_triggers", [])
        ),
        "evidence_identity_chain": {
            "driver_ir_digest": package["reviewed_freeze"].get("driver_ir_digest"),
            "architecture_packet_digest": package["reviewed_freeze"].get(
                "architecture_packet_digest"
            ),
            "review_set_digest": package["reviewed_freeze"].get("review_set_digest"),
            "adjudication_digest": package["reviewed_freeze"].get("adjudication_digest"),
            "reviewed_decision_digest": package["reviewed_freeze"].get(
                "reviewed_decision_digest"
            ),
            "architecture_freeze_digest": package["reviewed_freeze"].get("freeze_digest"),
            "evolution_contract_digest": package["reviewed_freeze"].get(
                "evolution_contract_digest"
            ),
            "realization_contract_digest": package["reviewed_freeze"].get(
                "realization_contract_digest"
            ),
        },
    }
    dossier["dossier_digest"] = canonical_sha256(dossier)
    return dossier


def verify_architecture_decision_dossier(
    dossier: Mapping[str, Any], package: Mapping[str, Any], conformance_report: Mapping[str, Any]
) -> bool:
    try:
        return dict(dossier) == build_architecture_decision_dossier(package, conformance_report)
    except (ArchitectureDecisionError, KeyError, TypeError, ValueError):
        return False


def render_architecture_decision_dossier_markdown(dossier: Mapping[str, Any]) -> str:
    """Render a concise deterministic reviewer view from the canonical dossier."""
    nfr = _require_mapping(dossier.get("nfr_sufficiency_gate"), "NFR sufficiency gate")
    review = _require_mapping(dossier.get("review_consensus"), "review consensus")
    sensitivity = _require_mapping(dossier.get("sensitivity"), "sensitivity summary")
    confidence = dossier.get("final_confidence")
    confidence_map = confidence if isinstance(confidence, Mapping) else {}
    prototype = _require_mapping(
        dossier.get("prototype_and_human_resolution"), "prototype/human resolution"
    )
    tradeoffs = _require_mapping(dossier.get("known_tradeoffs"), "known trade-offs")
    matrix = dossier.get("candidate_matrix", [])
    lines = [
        "# Architecture Decision Dossier",
        "",
        f"**Claim status:** `{dossier.get('architecture_claim_status')}`",
        "",
        str(dossier.get("architecture_claim_text", "")),
        "",
        "**Global optimum claimed:** No.",
        "",
        "## Requirements and architecture drivers",
        "",
        f"Requirements SHA-256: `{dossier.get('requirements_sha256')}`",
        f"Architecture driver count: {len(dossier.get('architecture_drivers', []))}",
        "",
        "## NFR sufficiency gate",
        "",
        f"Outcome: `{nfr.get('gate_outcome')}`",
        f"Unknown: {', '.join(nfr.get('unknown_driver_ids', [])) or 'none'}",
        f"Missing: {', '.join(nfr.get('missing_driver_ids', [])) or 'none'}",
        f"Low confidence: {', '.join(nfr.get('low_confidence_driver_ids', [])) or 'none'}",
        "",
        "## Candidate decision matrix",
        "",
        "| Candidate | Disposition | Base score | Revised score | Selected |",
        "|---|---|---:|---:|---|",
    ]
    for raw in matrix:
        if not isinstance(raw, Mapping):
            continue
        lines.append(
            "| {pattern} | {disp} | {base} | {revised} | {selected} |".format(
                pattern=raw.get("pattern_id"),
                disp=raw.get("disposition"),
                base=raw.get("base_total_score"),
                revised=raw.get("revised_total_score"),
                selected="yes" if raw.get("selected") else "no",
            )
        )
    lines += [
        "",
        "## Sensitivity and review consensus",
        "",
        f"Winner stability: `{sensitivity.get('winner_stability')}`",
        f"Review recommendation: {review.get('selected_recommendation_count', 0)}/{review.get('lane_count', 0)} lanes selected the winner.",
        f"Final automated confidence: `{confidence_map.get('level', 'UNKNOWN')}` ({confidence_map.get('score', 'n/a')}).",
        "",
        "Sensitivity winners:",
    ]
    for scenario in sensitivity.get("scenarios", []):
        if isinstance(scenario, Mapping):
            lines.append(f"- {scenario.get('scenario_id')}: `{scenario.get('winner')}`")
    lines += [
        "",
        "## Prototype / human decision",
        "",
        f"Human resolution applied: {'yes' if prototype.get('human_resolution_applied') else 'no'}.",
        f"Approval scope: `{prototype.get('approval_scope')}`",
        f"Quality gates waived: {prototype.get('quality_gates_waived', [])}",
        "",
        "## Selected realization and conformance",
        "",
        f"Selected pattern: `{dossier.get('selected_candidate_id')}`",
        f"Realization adapter: `{dossier.get('selected_adapter_id')}`",
        f"Architecture conformance: `{dossier.get('architecture_conformance', {}).get('status')}`",
        "",
        "## Known trade-offs (evidence-derived)",
        "",
    ]
    for row in tradeoffs.get("lowest_revised_dimensions", []):
        if isinstance(row, Mapping):
            lines.append(f"- {row.get('dimension')}: {row.get('score')}")
    if not tradeoffs.get("lowest_revised_dimensions"):
        lines.append("- No revised dimension-score evidence available.")
    selected_findings = tradeoffs.get("selected_candidate_review_findings", [])
    lines.append(f"- Selected-candidate review finding count: {len(selected_findings)}")
    lines += [
        "",
        "## Reconsideration triggers",
        "",
    ]
    for trigger in dossier.get("reconsideration_triggers", []):
        lines.append(f"- {trigger}")
    lines += [
        "",
        f"Canonical dossier SHA-256: `{dossier.get('dossier_digest')}`",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "ARCHITECTURE_CHANGING_NFR_DRIVER_IDS",
    "BOUNDED_CLAIM_STATUS",
    "DOSSIER_SCHEMA_VERSION",
    "NFR_GATE_SCHEMA_VERSION",
    "SUFFICIENT_CLAIM_STATUS",
    "build_architecture_decision_dossier",
    "evaluate_nfr_sufficiency",
    "render_architecture_decision_dossier_markdown",
    "verify_architecture_decision_dossier",
]
