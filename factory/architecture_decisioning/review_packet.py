"""Digest-bound, provider-neutral blind review packets and review sets."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import canonical_sha256
from .review_models import ArchitectureReviewError, ArchitectureReviewIncomplete
from .review_validation import (
    require_contract_integrity,
    validate_review_report,
)


def _valid_digest(value: Mapping[str, Any], field: str) -> bool:
    supplied = value.get(field)
    return isinstance(supplied, str) and supplied == canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def _candidate_profiles(
    decision: Mapping[str, Any], architecture_contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    candidate_ids = [
        row.get("pattern_id")
        for row in decision.get("scores", [])
        if isinstance(row, Mapping)
    ]
    profiles = {
        row.get("pattern_id"): deepcopy(dict(row))
        for row in architecture_contract.get("patterns", [])
        if isinstance(row, Mapping)
    }
    if any(candidate_id not in profiles for candidate_id in candidate_ids):
        raise ArchitectureReviewError(
            "review packet candidate profile is missing from architecture contract"
        )
    return [profiles[candidate_id] for candidate_id in candidate_ids]


def build_architecture_review_packet(
    decision: dict[str, Any],
    sensitivity: dict[str, Any],
    architecture_contract: dict[str, Any],
    review_contract: dict[str, Any],
    *,
    driver_ir: dict[str, Any] | None = None,
    evolution_contract: dict[str, Any] | None = None,
    evidence_catalog: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    require_contract_integrity(architecture_contract, "architecture contract")
    require_contract_integrity(review_contract, "review contract")
    if not _valid_digest(decision, "decision_digest") or not _valid_digest(
        sensitivity, "digest"
    ):
        raise ArchitectureReviewError("decision or sensitivity digest is invalid")
    if decision.get("contract_digest") != architecture_contract.get(
        "contract_digest"
    ):
        raise ArchitectureReviewError(
            "decision architecture-contract binding is invalid"
        )
    scores = decision.get("scores")
    if not isinstance(scores, list) or not scores:
        raise ArchitectureReviewError("decision scores are missing")
    if sensitivity.get("base_winner") != scores[0].get("pattern_id"):
        raise ArchitectureReviewError(
            "sensitivity winner is not bound to decision scores"
        )

    schema = review_contract.get("schema_version")
    packet: dict[str, Any] = {
        "schema_version": (
            review_contract.get(
                "review_packet_schema_version",
                "upi-app-factory.architecture-review-packet.v1",
            )
        ),
        "decision_digest": decision["decision_digest"],
        "requirements_sha256": decision.get("requirements_sha256"),
        "driver_ir_digest": decision.get("driver_ir_digest"),
        "architecture_contract_digest": architecture_contract["contract_digest"],
        "review_contract_digest": review_contract["contract_digest"],
        "upstream_decision_status": decision.get("decision_status"),
        "upstream_selected_candidate_id": decision.get("selected_candidate_id"),
        "scores": deepcopy(scores),
        "constraints": deepcopy(decision.get("constraints")),
        "sensitivity_digest": sensitivity["digest"],
        "winner_stability": sensitivity.get("winner_stability"),
    }

    if schema == "upi-app-factory.architecture-review-adjudication-contract.v2":
        if driver_ir is None or evolution_contract is None:
            raise ArchitectureReviewError(
                "V2 review packet requires driver IR and evolution contract"
            )
        if not _valid_digest(driver_ir, "digest"):
            raise ArchitectureReviewError("driver IR digest is invalid")
        if not _valid_digest(evolution_contract, "digest"):
            raise ArchitectureReviewError("evolution contract digest is invalid")
        if driver_ir.get("digest") != decision.get("driver_ir_digest"):
            raise ArchitectureReviewError(
                "driver IR is not bound to the architecture decision"
            )
        if evolution_contract.get("decision_digest") != decision.get(
            "decision_digest"
        ):
            raise ArchitectureReviewError(
                "evolution contract is not bound to the architecture decision"
            )
        if evolution_contract.get("contract_digest") != architecture_contract.get(
            "contract_digest"
        ):
            raise ArchitectureReviewError(
                "evolution contract architecture binding is invalid"
            )
        catalog = [] if evidence_catalog is None else deepcopy(evidence_catalog)
        if not isinstance(catalog, list) or any(
            not isinstance(item, dict) for item in catalog
        ):
            raise ArchitectureReviewError("evidence catalog must be a list of objects")
        packet.update(
            {
                "driver_ir": deepcopy(driver_ir),
                "candidate_profiles": _candidate_profiles(
                    decision, architecture_contract
                ),
                "sensitivity": deepcopy(sensitivity),
                "evolution_contract": deepcopy(evolution_contract),
                "evidence_catalog": catalog,
            }
        )

    packet["packet_digest"] = canonical_sha256(packet)
    return packet


def build_review_requests(
    packet: dict[str, Any], review_contract: dict[str, Any]
) -> list[dict[str, Any]]:
    require_contract_integrity(review_contract, "review contract")
    if (
        not _valid_digest(packet, "packet_digest")
        or packet.get("review_contract_digest")
        != review_contract.get("contract_digest")
    ):
        raise ArchitectureReviewError(
            "architecture review packet binding is invalid"
        )
    requests = []
    for lane in review_contract["required_lanes"]:
        request = {
            "schema_version": "upi-app-factory.architecture-review-request.v1",
            "lane_id": lane,
            "lane_role": review_contract.get("lane_roles", {}).get(lane),
            "architecture_packet_digest": packet["packet_digest"],
            "architecture_packet": deepcopy(packet),
            "prior_reports_visible": False,
        }
        request["request_digest"] = canonical_sha256(request)
        requests.append(request)
    return requests


def freeze_review_set(
    reports: Sequence[dict[str, Any]],
    packet: dict[str, Any],
    review_contract: dict[str, Any],
    architecture_contract: dict[str, Any],
) -> dict[str, Any]:
    require_contract_integrity(review_contract, "review contract")
    require_contract_integrity(architecture_contract, "architecture contract")
    requests = {
        request["lane_id"]: request
        for request in build_review_requests(packet, review_contract)
    }
    if not isinstance(reports, (list, tuple)):
        raise ArchitectureReviewIncomplete(
            "review reports must be a finite sequence"
        )
    lanes = [
        report.get("lane_id")
        for report in reports
        if isinstance(report, dict)
    ]
    required = review_contract["required_lanes"]
    if (
        len(reports) != len(required)
        or len(lanes) != len(reports)
        or set(lanes) != set(required)
        or len(set(lanes)) != len(lanes)
    ):
        raise ArchitectureReviewIncomplete(
            "exactly one report from every required lane is required"
        )
    validated = {
        lane: validate_review_report(
            next(report for report in reports if report["lane_id"] == lane),
            requests[lane],
            packet,
            review_contract,
            architecture_contract,
        )
        for lane in required
    }
    review_set = {
        "schema_version": review_contract["review_set_schema_version"],
        "execution_mode": review_contract["execution_mode"],
        "architecture_packet_digest": packet["packet_digest"],
        "review_contract_digest": review_contract["contract_digest"],
        "architecture_contract_digest": architecture_contract["contract_digest"],
        "lane_ids": list(required),
        "reports": [validated[lane] for lane in required],
    }
    review_set["review_set_digest"] = canonical_sha256(review_set)
    return review_set
