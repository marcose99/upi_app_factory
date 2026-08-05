from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.exact_v2_traceability import (
    AUTHORITATIVE_REQUIREMENTS_PDF_PATH,
    AUTHORITATIVE_REQUIREMENTS_TEXT_PATH,
    AUTHORITATIVE_VALIDATION_SUMMARY_PATH,
    REQUIREMENTS_PDF_SHA256,
    REQUIREMENTS_TEXT_SHA256,
    VALIDATION_SUMMARY_SHA256,
)
from factory.generated_application_artifacts import (
    build_converged_generated_application_artifact_payloads,
    materialize_converged_generated_application_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_exact_input_definition_of_done_pack_is_go_and_hash_bound(
    tmp_path: Path,
) -> None:
    assert _sha256_file(AUTHORITATIVE_REQUIREMENTS_PDF_PATH) == REQUIREMENTS_PDF_SHA256
    assert _sha256_file(AUTHORITATIVE_REQUIREMENTS_TEXT_PATH) == REQUIREMENTS_TEXT_SHA256
    assert _sha256_file(AUTHORITATIVE_VALIDATION_SUMMARY_PATH) == VALIDATION_SUMMARY_SHA256

    payloads = build_converged_generated_application_artifact_payloads(ROOT)
    coverage = json.loads(payloads["evidence/coverage_report.json"])
    traceability = json.loads(payloads["evidence/requirements_traceability_matrix.json"])
    report = json.loads(payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"])
    summary = json.loads(payloads["evidence/generation_summary.json"])

    assert coverage["coverage_status"] == "TRACEABLE_GO_CANDIDATE"
    assert coverage["summary"] == {
        "obligation_count": 781,
        "supported_count": 781,
        "partial_count": 0,
        "unsupported_count": 0,
        "not_applicable_count": 0,
        "mandatory_no_go_count": 0,
    }
    assert traceability["decision"] == "GO"
    assert traceability["partial_obligation_count"] == 0
    assert traceability["unsupported_obligation_count"] == 0
    assert report["decision"] == "PROVEN_100_PERCENT_CAPABILITY"
    assert report["mandatory_gate_passed"] is True
    assert summary["status"] == "definition_of_done_ready"
    assert summary["authoritative_requirements"]["pdf_sha256"] == REQUIREMENTS_PDF_SHA256
    assert summary["authoritative_requirements"]["text_sha256"] == REQUIREMENTS_TEXT_SHA256
    assert summary["current_validation_summary"]["sha256"] == VALIDATION_SUMMARY_SHA256
    assert summary["source_hashes"]["factory/exact_v2_traceability.py"] == _sha256_file(
        ROOT / "factory" / "exact_v2_traceability.py"
    )
    assert summary["source_hashes"]["factory/token_economics/service.py"] == _sha256_file(
        ROOT / "factory" / "token_economics" / "service.py"
    )

    materialized = materialize_converged_generated_application_artifacts(
        ROOT,
        application_root=tmp_path / "current_definition_of_done",
    )
    assert materialized["decision"] == "PROVEN_100_PERCENT_CAPABILITY"
    assert (
        tmp_path
        / "current_definition_of_done"
        / "evidence"
        / "generation_summary.json"
    ).is_file()
