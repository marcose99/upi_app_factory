from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.exact_v2_traceability import (
    AUTHORITATIVE_REQUIREMENTS_PDF_PATH,
    AUTHORITATIVE_REQUIREMENTS_TEXT_PATH,
    AUTHORITATIVE_VALIDATION_SUMMARY_PATH,
    REQUIREMENTS_PDF_SHA256,
    REQUIREMENTS_TEXT_SHA256,
    VALIDATION_SUMMARY_SOURCE_SHA256,
    VALIDATION_SUMMARY_SHA256,
)
from factory.generated_application_artifacts import (
    EVIDENCE_AUTHORITY,
    NO_GO_EVIDENCE_DECISION,
    QUARANTINED_APPLICATION_SUBTREE,
    QUARANTINED_ARTIFACT_RELATIVE_PATHS,
    REQUIRED_ARTIFACT_RELATIVE_PATHS,
    build_generated_application_artifact_payloads,
    is_quarantined_application_path,
    materialize_generated_application_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_exact_input_definition_of_done_pack_is_no_go_and_hash_bound(
    tmp_path: Path,
) -> None:
    for path in (
        AUTHORITATIVE_REQUIREMENTS_PDF_PATH,
        AUTHORITATIVE_REQUIREMENTS_TEXT_PATH,
        AUTHORITATIVE_VALIDATION_SUMMARY_PATH,
    ):
        assert ROOT in path.resolve().parents
    assert _sha256_file(AUTHORITATIVE_REQUIREMENTS_PDF_PATH) == REQUIREMENTS_PDF_SHA256
    assert _sha256_file(AUTHORITATIVE_REQUIREMENTS_TEXT_PATH) == REQUIREMENTS_TEXT_SHA256
    assert _sha256_file(AUTHORITATIVE_VALIDATION_SUMMARY_PATH) == VALIDATION_SUMMARY_SHA256

    payloads = build_generated_application_artifact_payloads(ROOT)
    coverage = json.loads(payloads["evidence/coverage_report.json"])
    traceability = json.loads(payloads["evidence/requirements_traceability_matrix.json"])
    report = json.loads(payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"])
    summary = json.loads(payloads["evidence/generation_summary.json"])
    inventory = json.loads(payloads["evidence/atomic_obligation_inventory.json"])

    assert "evidence/generation_summary.json" in REQUIRED_ARTIFACT_RELATIVE_PATHS
    assert coverage["coverage_status"] == "NO_GO_UNSUPPORTED_MANDATORY_OBLIGATIONS"
    coverage_summary = coverage["summary"]
    assert coverage_summary["obligation_count"] == len(inventory["items"])
    assert coverage_summary["obligation_count"] == sum(
        coverage_summary[key]
        for key in (
            "supported_count",
            "partial_count",
            "unsupported_count",
            "not_applicable_count",
        )
    )
    assert coverage_summary["partial_count"] > 0
    assert coverage_summary["mandatory_no_go_count"] == sum(
        item["mandatory"]
        and item["support_status"] in {"PARTIAL", "UNSUPPORTED"}
        for item in inventory["items"]
    )
    assert traceability["decision"] == "NO_GO"
    assert traceability["supported_obligation_count"] == coverage_summary["supported_count"]
    assert traceability["partial_obligation_count"] == coverage_summary["partial_count"]
    assert (
        traceability["unsupported_obligation_count"]
        == coverage_summary["unsupported_count"]
    )
    assert report["decision"] == NO_GO_EVIDENCE_DECISION
    assert report["mandatory_gate_passed"] is False
    assert summary["status"] == "definition_of_done_blocked"
    assert summary["decision"] == NO_GO_EVIDENCE_DECISION
    assert summary["mandatory_gate_passed"] is False
    for surface in (coverage, traceability, report, summary):
        assert surface["evidence_authority"] == EVIDENCE_AUTHORITY
        assert surface["publication_authority"] is True
        assert surface["diagnostic_projection_used"] is False
    assert summary["authoritative_requirements"]["pdf_sha256"] == REQUIREMENTS_PDF_SHA256
    assert summary["authoritative_requirements"]["text_sha256"] == REQUIREMENTS_TEXT_SHA256
    assert summary["current_validation_summary"]["sha256"] == VALIDATION_SUMMARY_SHA256
    assert (
        summary["current_validation_summary"]["source_sha256"]
        == VALIDATION_SUMMARY_SOURCE_SHA256
    )
    assert summary["source_hashes"]["factory/exact_v2_traceability.py"] == _sha256_file(
        ROOT / "factory" / "exact_v2_traceability.py"
    )
    assert summary["source_hashes"]["factory/token_economics/service.py"] == _sha256_file(
        ROOT / "factory" / "token_economics" / "service.py"
    )

    materialized = materialize_generated_application_artifacts(
        ROOT,
        application_root=tmp_path / "authoritative_exact_v2",
    )
    assert materialized["decision"] == NO_GO_EVIDENCE_DECISION
    assert materialized["mandatory_gate_passed"] is False
    assert materialized["definition_of_done_status"] == "definition_of_done_blocked"
    assert materialized["exact_v2_evidence_authority"] == EVIDENCE_AUTHORITY
    assert (
        tmp_path
        / "authoritative_exact_v2"
        / "evidence"
        / "generation_summary.json"
    ).is_file()


def test_tracked_current_definition_of_done_is_exactly_quarantined() -> None:
    expected = {
        (
            "workspace/factory_generated/upi_dispute_resolution/"
            "generated_application/current_definition_of_done/"
            "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md"
        ),
        (
            "workspace/factory_generated/upi_dispute_resolution/"
            "generated_application/current_definition_of_done/"
            "docs/persistence_reset_policy.md"
        ),
        *{
            (
                "workspace/factory_generated/upi_dispute_resolution/"
                "generated_application/current_definition_of_done/evidence/"
                + filename
            )
            for filename in (
                "CAPABILITY_PRE_RUN_REPORT.json",
                "PRE_RUN_MANIFEST.json",
                "REQUIREMENT_CAPABILITY_MATRIX.json",
                "atomic_obligation_inventory.json",
                "classification_decision_table.json",
                "coverage_report.json",
                "evidence_manifest_description.json",
                "generation_summary.json",
                "openapi_inventory.json",
                "requirements_traceability_matrix.json",
                "residual_risk_register.json",
                "unsupported_obligation_report.json",
            )
        },
        (
            "workspace/factory_generated/upi_dispute_resolution/"
            "generated_application/current_definition_of_done/generation_metadata.json"
        ),
    }
    assert set(QUARANTINED_ARTIFACT_RELATIVE_PATHS) == expected
    assert len(QUARANTINED_ARTIFACT_RELATIVE_PATHS) == 15
    assert all((ROOT / relative_path).is_file() for relative_path in expected)

    quarantined_root = (
        ROOT
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "generated_application"
        / QUARANTINED_APPLICATION_SUBTREE
    )
    assert is_quarantined_application_path(quarantined_root, project_root=ROOT)
    assert is_quarantined_application_path(
        quarantined_root / "evidence",
        project_root=ROOT,
    )
    assert not is_quarantined_application_path(
        quarantined_root.parent,
        project_root=ROOT,
    )
    with pytest.raises(ValueError, match="quarantined"):
        build_generated_application_artifact_payloads(
            ROOT,
            application_root=quarantined_root,
        )
    with pytest.raises(ValueError, match="quarantined"):
        materialize_generated_application_artifacts(
            ROOT,
            application_root=quarantined_root,
        )
