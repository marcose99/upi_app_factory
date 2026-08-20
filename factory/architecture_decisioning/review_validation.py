"""Frozen contract loading and strict review-report validation."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Union

from .canonical import canonical_sha256
from .review_models import ArchitectureReviewError

PathLike = Union[str, Path]
V1_SCHEMA = "upi-app-factory.architecture-review-adjudication-contract.v1"
V2_SCHEMA = "upi-app-factory.architecture-review-adjudication-contract.v2"
SUPPORTED_SCHEMAS = {V1_SCHEMA, V2_SCHEMA}


def _list_of_unique_strings(value: Any, name: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise ArchitectureReviewError(
            f"{name} must be a unique non-empty string list"
        )
    return value


def contract_digest_valid(contract: Mapping[str, Any]) -> bool:
    supplied = contract.get("contract_digest")
    body = {key: value for key, value in contract.items() if key != "contract_digest"}
    return isinstance(supplied, str) and supplied == canonical_sha256(body)


def require_contract_integrity(contract: Mapping[str, Any], name: str) -> None:
    if not contract_digest_valid(contract):
        raise ArchitectureReviewError(f"{name} digest is invalid")


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchitectureReviewError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ArchitectureReviewError(f"{name} must be finite")
    return result


def _validate_contract(contract: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "report_schema_version",
        "review_set_schema_version",
        "adjudication_schema_version",
        "execution_mode",
        "required_lanes",
        "max_parallelism",
        "blind_first_pass_required",
        "all_lanes_required_before_adjudication",
        "score_adjustment_min",
        "score_adjustment_max",
        "score_adjustment_aggregation",
        "protected_veto_categories",
        "protected_veto_severities",
        "severities",
        "finding_dispositions",
        "upstream_non_bypassable_statuses",
        "confidence",
        "near_tie_margin",
    }
    if not required.issubset(contract):
        raise ArchitectureReviewError("review contract is missing required fields")
    schema = contract["schema_version"]
    if schema not in SUPPORTED_SCHEMAS:
        raise ArchitectureReviewError("unsupported review contract schema")
    lanes = _list_of_unique_strings(contract["required_lanes"], "required_lanes")
    if len(lanes) != 6 or contract["execution_mode"] != "PARALLEL_BLIND":
        raise ArchitectureReviewError(
            "review contract must define exactly six parallel blind lanes"
        )
    if contract["max_parallelism"] != 6 or not contract["blind_first_pass_required"]:
        raise ArchitectureReviewError(
            "review contract parallelism/blindness is invalid"
        )
    if not contract["all_lanes_required_before_adjudication"]:
        raise ArchitectureReviewError("review contract must require all lanes")
    _list_of_unique_strings(
        contract["protected_veto_categories"], "protected categories"
    )
    _list_of_unique_strings(
        contract["protected_veto_severities"], "protected severities"
    )
    if contract["score_adjustment_aggregation"] != "MEAN_PER_DIMENSION":
        raise ArchitectureReviewError("unsupported score adjustment aggregation")
    low = _finite_number(contract["score_adjustment_min"], "score_adjustment_min")
    high = _finite_number(contract["score_adjustment_max"], "score_adjustment_max")
    if low > high:
        raise ArchitectureReviewError("invalid score adjustment bounds")
    near_tie = _finite_number(contract["near_tie_margin"], "near_tie_margin")
    if near_tie < 0:
        raise ArchitectureReviewError("near_tie_margin cannot be negative")
    confidence = contract["confidence"]
    if (
        not isinstance(confidence, dict)
        or set(confidence.get("weights", {}))
        != {
            "evidence_quality",
            "reviewer_agreement",
            "score_margin",
            "sensitivity_stability",
        }
        or sum(confidence["weights"].values()) != 100
    ):
        raise ArchitectureReviewError("invalid confidence policy")
    high_threshold = _finite_number(
        confidence.get("high_threshold"), "confidence.high_threshold"
    )
    medium_threshold = _finite_number(
        confidence.get("medium_threshold"), "confidence.medium_threshold"
    )
    full_credit = _finite_number(
        confidence.get("score_margin_full_credit"),
        "confidence.score_margin_full_credit",
    )
    if not 0 <= medium_threshold <= high_threshold <= 1 or full_credit <= 0:
        raise ArchitectureReviewError("invalid confidence thresholds")

    if schema == V2_SCHEMA:
        v2_required = {
            "provider_timeout_seconds",
            "require_rich_review_context",
            "near_tie_basis",
            "contract_integrity_recheck",
            "max_findings_per_report",
            "max_evidence_refs_per_finding",
            "max_summary_chars",
            "review_packet_schema_version",
        }
        if not v2_required.issubset(contract):
            raise ArchitectureReviewError("V2 review contract is incomplete")
        timeout = _finite_number(
            contract["provider_timeout_seconds"], "provider_timeout_seconds"
        )
        if timeout <= 0:
            raise ArchitectureReviewError("provider timeout must be positive")
        if contract["require_rich_review_context"] is not True:
            raise ArchitectureReviewError("V2 requires rich reviewer context")
        if contract["near_tie_basis"] != "REVISED_ELIGIBLE_MARGIN":
            raise ArchitectureReviewError("V2 near-tie basis is invalid")
        if contract["contract_integrity_recheck"] is not True:
            raise ArchitectureReviewError("V2 requires contract integrity rechecks")
        for field in (
            "max_findings_per_report",
            "max_evidence_refs_per_finding",
            "max_summary_chars",
        ):
            value = contract[field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ArchitectureReviewError(f"{field} must be a positive integer")
        if (
            contract["review_packet_schema_version"]
            != "upi-app-factory.architecture-review-packet.v2"
        ):
            raise ArchitectureReviewError("V2 packet schema is invalid")


def load_architecture_review_contract(path: PathLike) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchitectureReviewError(f"cannot load review contract: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArchitectureReviewError("review contract must be an object")
    contract = deepcopy(raw)
    supplied = contract.pop("contract_digest", None)
    _validate_contract(contract)
    digest = canonical_sha256(contract)
    if supplied is not None and supplied != digest:
        raise ArchitectureReviewError("review contract digest is invalid")
    contract["contract_digest"] = digest
    return contract


def _digest_valid(value: Mapping[str, Any], field: str) -> bool:
    supplied = value.get(field)
    return isinstance(supplied, str) and supplied == canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def validate_review_report(
    report: dict[str, Any],
    request: dict[str, Any],
    packet: dict[str, Any],
    review_contract: dict[str, Any],
    architecture_contract: dict[str, Any],
) -> dict[str, Any]:
    """Validate and return a defensive copy of one blind first-pass report."""
    require_contract_integrity(review_contract, "review contract")
    require_contract_integrity(architecture_contract, "architecture contract")
    if not isinstance(report, dict):
        raise ArchitectureReviewError("review report must be an object")
    result = deepcopy(report)
    required = {
        "schema_version",
        "lane_id",
        "request_digest",
        "architecture_packet_digest",
        "prior_reports_visible",
        "recommended_candidate_id",
        "candidate_assessments",
        "findings",
        "confidence",
        "report_digest",
    }
    if set(result) != required:
        raise ArchitectureReviewError("review report fields do not match the schema")
    if result["schema_version"] != review_contract["report_schema_version"]:
        raise ArchitectureReviewError("review report schema is invalid")
    if (
        result["lane_id"] != request.get("lane_id")
        or result["lane_id"] not in review_contract["required_lanes"]
    ):
        raise ArchitectureReviewError("review report lane binding is invalid")
    if (
        result["request_digest"] != request.get("request_digest")
        or not _digest_valid(request, "request_digest")
    ):
        raise ArchitectureReviewError("review request binding is invalid")
    if (
        result["architecture_packet_digest"] != packet.get("packet_digest")
        or request.get("architecture_packet_digest") != packet.get("packet_digest")
        or not _digest_valid(packet, "packet_digest")
    ):
        raise ArchitectureReviewError("review packet binding is invalid")
    if result["prior_reports_visible"] is not False:
        raise ArchitectureReviewError("blind review cannot expose prior reports")
    candidate_ids = [
        row.get("pattern_id")
        for row in packet.get("scores", [])
        if isinstance(row, dict)
    ]
    contract_ids = [
        row.get("pattern_id")
        for row in architecture_contract.get("patterns", [])
        if isinstance(row, dict)
    ]
    if (
        not candidate_ids
        or len(candidate_ids) != len(set(candidate_ids))
        or not set(candidate_ids).issubset(contract_ids)
    ):
        raise ArchitectureReviewError("packet candidate IDs are invalid")
    if result["recommended_candidate_id"] not in candidate_ids:
        raise ArchitectureReviewError("review recommends an unknown candidate")
    assessments = result["candidate_assessments"]
    if not isinstance(assessments, list) or len(assessments) != len(candidate_ids):
        raise ArchitectureReviewError(
            "review must assess every packet candidate exactly once"
        )
    seen: set[str] = set()
    dimensions = set(architecture_contract["score_dimensions"])
    max_summary = int(review_contract.get("max_summary_chars", 100_000))
    for assessment in assessments:
        assessment_fields = {"candidate_id", "score_adjustments", "summary"}
        if not isinstance(assessment, dict) or set(assessment) != assessment_fields:
            raise ArchitectureReviewError("candidate assessment fields are invalid")
        candidate = assessment["candidate_id"]
        if candidate not in candidate_ids or candidate in seen:
            raise ArchitectureReviewError(
                "candidate assessments contain an unknown or duplicate ID"
            )
        seen.add(candidate)
        summary = assessment["summary"]
        if (
            not isinstance(summary, str)
            or not summary.strip()
            or len(summary) > max_summary
        ):
            raise ArchitectureReviewError("candidate assessment summary is invalid")
        adjustments = assessment["score_adjustments"]
        if not isinstance(adjustments, dict) or not set(adjustments).issubset(
            dimensions
        ):
            raise ArchitectureReviewError("score adjustment dimension is invalid")
        for value in adjustments.values():
            numeric = _finite_number(value, "score adjustment")
            if not (
                review_contract["score_adjustment_min"]
                <= numeric
                <= review_contract["score_adjustment_max"]
            ):
                raise ArchitectureReviewError(
                    "score adjustment is outside frozen bounds"
                )
    findings = result["findings"]
    if not isinstance(findings, list):
        raise ArchitectureReviewError("findings must be a list")
    max_findings = int(review_contract.get("max_findings_per_report", 100_000))
    if len(findings) > max_findings:
        raise ArchitectureReviewError("review contains too many findings")
    finding_ids: set[str] = set()
    max_refs = int(review_contract.get("max_evidence_refs_per_finding", 100_000))
    for finding in findings:
        fields = {
            "finding_id",
            "candidate_id",
            "category",
            "severity",
            "disposition",
            "claim",
            "evidence_refs",
        }
        if not isinstance(finding, dict) or set(finding) != fields:
            raise ArchitectureReviewError("finding fields are invalid")
        finding_id = finding["finding_id"]
        if (
            not isinstance(finding_id, str)
            or not finding_id
            or finding_id in finding_ids
        ):
            raise ArchitectureReviewError("finding ID is invalid or duplicated")
        finding_ids.add(finding_id)
        if finding["candidate_id"] not in candidate_ids:
            raise ArchitectureReviewError("finding names an unknown candidate")
        if (
            finding["severity"] not in review_contract["severities"]
            or finding["disposition"]
            not in review_contract["finding_dispositions"]
        ):
            raise ArchitectureReviewError(
                "finding severity or disposition is invalid"
            )
        if not isinstance(finding["claim"], str) or not finding["claim"].strip():
            raise ArchitectureReviewError("finding claim is required")
        refs = finding["evidence_refs"]
        if (
            not isinstance(refs, list)
            or len(refs) > max_refs
            or any(not isinstance(ref, str) or not ref for ref in refs)
        ):
            raise ArchitectureReviewError(
                "finding evidence references are invalid"
            )
        if finding["disposition"] == "VETO" and (
            finding["category"]
            not in review_contract["protected_veto_categories"]
            or finding["severity"]
            not in review_contract["protected_veto_severities"]
            or not refs
        ):
            raise ArchitectureReviewError(
                "veto is not a protected evidence-backed high-severity veto"
            )
    confidence = result["confidence"]
    numeric_confidence = _finite_number(confidence, "report confidence")
    if not 0 <= numeric_confidence <= 1:
        raise ArchitectureReviewError(
            "report confidence must be between zero and one"
        )
    if not _digest_valid(result, "report_digest"):
        raise ArchitectureReviewError("review report digest is invalid")
    return result
