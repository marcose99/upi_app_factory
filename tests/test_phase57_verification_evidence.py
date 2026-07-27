from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from factory.application_engineering.verification_evidence import (
    APP_ID,
    LAYER_COUNTS,
    VerificationEvidenceError,
    build_test_catalogue,
    evidence_root,
    generated_app_root,
    run_phase57_verification,
    validate_manifest_records,
)


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase57_generates_required_layered_evidence() -> None:
    result = run_phase57_verification(ROOT)

    assert result.app_id == APP_ID
    assert result.status == "completed"
    assert result.test_count == 120
    assert result.layer_counts == LAYER_COUNTS
    assert result.depth_score["overall"] >= 80
    assert result.depth_score["critical_findings"] == 0
    assert result.depth_score["high_findings"] == 0

    verification_root = evidence_root(generated_app_root(ROOT))
    for artifact in [
        "requirements_traceability.json",
        "adr_index.json",
        "threat_abuse_catalogue.json",
        "owasp_asvs_5_0_0_matrix.json",
        "nist_ssdf_1_1_mapping.json",
        "ssdf_1_2_draft_delta.json",
        "dependency_inventory.json",
        "cyclonedx_1_7_sbom.json",
        "slsa_1_2_provenance_shaped.json",
        "manifest_sha256.json",
        "generated_app_archive.tar.gz",
    ]:
        assert (verification_root / artifact).is_file()


def test_phase57_archive_is_stable_across_second_run() -> None:
    run_phase57_verification(ROOT)
    archive = evidence_root(generated_app_root(ROOT)) / "generated_app_archive.tar.gz"
    before = sha256_file(archive)

    run_phase57_verification(ROOT)

    assert sha256_file(archive) == before


def test_test_catalogue_has_meaningful_distribution() -> None:
    catalogue = build_test_catalogue()

    assert catalogue["total"] == 120
    assert catalogue["counts_by_layer"] == LAYER_COUNTS
    layers = {item["layer"] for item in catalogue["tests"]}
    assert layers == set(LAYER_COUNTS)
    assert all(item["objective"] for item in catalogue["tests"])
    assert all("distinct behavior" in item["non_triviality"] for item in catalogue["tests"])


def test_manifest_validation_fails_closed_when_evidence_is_tampered(tmp_path: Path) -> None:
    run_phase57_verification(ROOT)
    app_root = generated_app_root(ROOT)
    manifest_path = evidence_root(app_root) / "manifest_sha256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    copied_app = tmp_path / APP_ID
    shutil.copytree(app_root, copied_app)
    tampered = copied_app / manifest["files"][0]["path"]
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")

    with pytest.raises(VerificationEvidenceError, match="hash mismatch"):
        validate_manifest_records(copied_app, copied_app / "evidence" / "phase57_verification" / "manifest_sha256.json")


def test_manifest_validation_fails_closed_when_file_is_missing(tmp_path: Path) -> None:
    run_phase57_verification(ROOT)
    app_root = generated_app_root(ROOT)
    copied_app = tmp_path / APP_ID
    shutil.copytree(app_root, copied_app)
    manifest_path = copied_app / "evidence" / "phase57_verification" / "manifest_sha256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    missing = copied_app / manifest["files"][0]["path"]
    missing.unlink()

    with pytest.raises(VerificationEvidenceError, match="manifest file missing"):
        validate_manifest_records(copied_app, manifest_path)
