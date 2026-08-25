"""Public assurance APIs. Canonical JSON is the authority for all derived views."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .kernel import (
    DIMENSION_WEIGHTS,
    HARD_GATES,
    QualityAssuranceError,
    evaluate_acceptance,
    validate_acceptance,
    validate_claim_ledger,
)
from .reporting import validate_report_suite, write_report_suite


def _architecture_dossier_report_sections(application_root: Path) -> list[dict[str, str]]:
    evidence_root = application_root / "evidence" / "architecture"
    freeze = evidence_root / "architecture_freeze.json"
    dossier_path = evidence_root / "architecture_decision_dossier.json"
    if freeze.is_file() and not dossier_path.is_file():
        raise QualityAssuranceError(
            "reviewed architecture application is missing architecture decision dossier"
        )
    if not dossier_path.is_file():
        return []
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    supplied = dossier.get("dossier_digest")
    body = {key: value for key, value in dossier.items() if key != "dossier_digest"}
    expected = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if supplied != expected:
        raise QualityAssuranceError("architecture decision dossier digest is invalid")
    nfr = dossier.get("nfr_sufficiency_gate", {})
    review = dossier.get("review_consensus", {})
    confidence = dossier.get("final_confidence") or {}
    conformance = dossier.get("architecture_conformance", {})
    tradeoffs = dossier.get("known_tradeoffs", {})
    matrix = dossier.get("candidate_matrix", [])
    disqualified = dossier.get("disqualified_candidates", [])
    sensitivity = dossier.get("sensitivity", {})
    prototype = dossier.get("prototype_and_human_resolution", {})
    summary = "; ".join(
        [
            f"claim={dossier.get('architecture_claim_status')}",
            f"requirements={dossier.get('requirements_sha256')}",
            f"drivers={len(dossier.get('architecture_drivers', []))}",
            f"nfr_gate={nfr.get('gate_outcome')}",
            f"unknown_nfrs={nfr.get('unknown_driver_ids', [])}",
            f"candidates={len(matrix)}",
            f"disqualified={len(disqualified)}",
            f"winner_stability={sensitivity.get('winner_stability')}",
            f"review_consensus={review.get('selected_recommendation_count', 0)}/{review.get('lane_count', 0)}",
            f"prototype_human_resolution={bool(prototype.get('human_resolution_applied'))}",
            f"confidence={confidence.get('level')}:{confidence.get('score')}",
            f"selected={dossier.get('selected_candidate_id')}",
            f"adapter={dossier.get('selected_adapter_id')}",
            f"conformance={conformance.get('status')}",
            f"tradeoff_dimensions={tradeoffs.get('lowest_revised_dimensions', [])}",
            f"reconsideration_triggers={dossier.get('reconsideration_triggers', [])}",
            f"dossier_digest={supplied}",
        ]
    )
    return [
        {
            "heading": "Architecture Decision Dossier Gate",
            "content": summary,
        }
    ]


def _build(
    kind: str,
    *,
    output_dir: str | Path | None,
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    raw_measures: Mapping[str, Any],
    acceptance_claim_ids: Sequence[str] = (),
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    grounding = validate_claim_ledger(claims, evidence, acceptance_claim_ids=acceptance_claim_ids)
    if grounding["unsupported_claim_count"]:
        raise QualityAssuranceError("unsupported published claims must equal zero")
    acceptance = evaluate_acceptance(raw_measures)
    acceptance["claim_grounding"] = grounding
    acceptance["bounded_scope_coverage"] = dict(raw_measures.get("bounded_scope_coverage", {}))
    acceptance["test_evidence"] = dict(raw_measures.get("test_evidence", {}))
    bundle = {
        "schema_version": "upi-app-factory.quality-bundle.v1",
        "kind": kind,
        "claims": list(claims),
        "evidence": list(evidence),
        "acceptance": acceptance,
    }
    if output_dir is not None:
        root = Path(output_dir)
        reports = root / "reports"
        report_context = dict(context or {})
        report_context.setdefault("status", acceptance["decision"])
        report_context.setdefault("claim_ids", [row["claim_id"] for row in claims])
        report_context.setdefault("evidence_ids", [row["evidence_id"] for row in evidence])
        write_report_suite(reports, kind=kind, context=report_context)
        (root / "acceptance.json").write_text(
            json.dumps(acceptance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return bundle


def build_factory_quality_bundle(
    *,
    output_dir: str | Path | None = None,
    claims: Sequence[Mapping[str, Any]] = (),
    evidence: Sequence[Mapping[str, Any]] = (),
    raw_measures: Mapping[str, Any],
    **context: Any,
) -> dict[str, Any]:
    return _build(
        "factory",
        output_dir=output_dir,
        claims=claims,
        evidence=evidence,
        raw_measures=raw_measures,
        context=context,
    )


def build_application_quality_bundle(
    *,
    application_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    claims: Sequence[Mapping[str, Any]] = (),
    evidence: Sequence[Mapping[str, Any]] = (),
    raw_measures: Mapping[str, Any],
    **context: Any,
) -> dict[str, Any]:
    target = output_dir if output_dir is not None else application_root
    report_context = dict(context)
    if application_root is not None:
        sections = _architecture_dossier_report_sections(Path(application_root))
        if sections:
            report_context["architecture_decision_sections"] = sections
    return _build(
        "application",
        output_dir=target,
        claims=claims,
        evidence=evidence,
        raw_measures=raw_measures,
        context=report_context,
    )


def validate_quality_bundle(bundle: Mapping[str, Any], *, root: str | Path | None = None) -> bool:
    validate_claim_ledger(bundle.get("claims", []), bundle.get("evidence", []))
    validate_acceptance(bundle.get("acceptance", {}))
    if root is not None:
        validate_report_suite(Path(root) / "reports")
    return True


def finalize_internal_review_acceptance(
    review_reports: Sequence[Mapping[str, Any]],
    *,
    signed_external_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    roles = {str(row.get("role", "")) for row in review_reports if row.get("status") == "PASS"}
    if len(review_reports) != 8 or len(roles) != 8:
        raise QualityAssuranceError("eight distinct passing internal review lanes required")
    open_blockers = [
        row for row in review_reports if row.get("critical_open", 0) or row.get("high_open", 0)
    ]
    if open_blockers:
        raise QualityAssuranceError("critical or high review findings remain open")
    external = "PENDING_EXTERNAL_HUMAN_REVIEW"
    if signed_external_evidence:
        required = {
            "identity",
            "organization",
            "credentials",
            "scope",
            "evidence_hashes",
            "independence_declaration",
            "findings",
            "limitations",
            "date",
            "signature",
        }
        if required <= set(signed_external_evidence):
            external = "SIGNED_EXTERNAL_HUMAN_REVIEW_COMPLETE"
        else:
            raise QualityAssuranceError("external evidence is not a complete signed record")
    return {
        "internal_review_lanes_passed": 8,
        "internal_status": "PASS",
        "external_human_review_status": external,
        "production_ready": False,
    }


__all__ = [
    "DIMENSION_WEIGHTS",
    "HARD_GATES",
    "QualityAssuranceError",
    "build_factory_quality_bundle",
    "build_application_quality_bundle",
    "validate_quality_bundle",
    "evaluate_acceptance",
    "finalize_internal_review_acceptance",
]
