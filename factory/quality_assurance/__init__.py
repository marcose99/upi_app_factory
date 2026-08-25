"""Public assurance APIs. Canonical JSON is the authority for all derived views."""

from __future__ import annotations

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
    return _build(
        "application",
        output_dir=target,
        claims=claims,
        evidence=evidence,
        raw_measures=raw_measures,
        context=context,
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
