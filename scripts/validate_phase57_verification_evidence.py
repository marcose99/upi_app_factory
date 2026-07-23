#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REQUIRED_FILES = [
    "factory/application_engineering/verification_evidence.py",
    "tests/test_phase57_verification_evidence.py",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/requirements_traceability.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/adr_index.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/threat_abuse_catalogue.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/owasp_asvs_5_0_0_matrix.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/nist_ssdf_1_1_mapping.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/ssdf_1_2_draft_delta.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/dependency_inventory.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/cyclonedx_1_7_sbom.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/slsa_1_2_provenance_shaped.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/manifest_sha256.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/depth_score.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/residual_risks.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/test_catalogue.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/test_results.json",
    "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification/generated_app_archive.tar.gz",
    "workspace/deep_engineering_campaign/phase57_report.json",
    "workspace/deep_engineering_campaign/phase57_report.md",
]

REQUIRED_LAYERS = {
    "domain",
    "application",
    "sqlite_persistence_migrations",
    "api",
    "security_privacy",
    "architecture",
    "invariant_property_style",
    "health_readiness_metrics",
    "end_to_end_lifecycle",
    "packaging_replay",
}


def read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def canonical_python(root: Path) -> Path:
    for candidate in [root / ".venv" / "bin" / "python3", root / ".venv" / "bin" / "python", Path(sys.executable)]:
        if candidate.is_file():
            return candidate
    raise AssertionError("No canonical Python interpreter found")


def run(command: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def validate_artifacts(root: Path) -> None:
    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        raise AssertionError(f"Missing Phase 57 artifacts: {missing}")

    report = read_json(root / "workspace/deep_engineering_campaign/phase57_report.json")
    if report.get("stage") != "Phase 57":
        raise AssertionError("Phase 57 report JSON has the wrong stage")
    if report.get("product_name") != "UPI App Factory":
        raise AssertionError("Phase 57 report must preserve the product name")
    if report.get("repository_id") != "upi_app_factory":
        raise AssertionError("Phase 57 report must preserve the repository id")
    if report.get("llm_runtime_calls") != 0 or report.get("real_payment_calls") != "disabled":
        raise AssertionError("Phase 57 report violates runtime safety controls")

    evidence = root / "workspace/deep_engineering_campaign/generated_app/upi_failed_debit_dispute/evidence/phase57_verification"
    catalogue = read_json(evidence / "test_catalogue.json")
    if int(catalogue.get("total", 0)) < 120:
        raise AssertionError("Golden application verification catalogue is below 120 tests")
    if set(catalogue.get("counts_by_layer", {})) != REQUIRED_LAYERS:
        raise AssertionError("Verification catalogue does not cover every required layer")
    tests = catalogue.get("tests", [])
    if not isinstance(tests, list) or len(tests) != catalogue.get("total"):
        raise AssertionError("Verification test catalogue is malformed")
    if any(not item.get("objective") or not item.get("non_triviality") for item in tests if isinstance(item, dict)):
        raise AssertionError("Verification test catalogue contains trivial or malformed tests")

    results = read_json(evidence / "test_results.json")
    if results.get("failed") != 0 or results.get("passed") != catalogue.get("total"):
        raise AssertionError("Layered verification test results must be fully passing")
    if not results.get("tamper_tests"):
        raise AssertionError("Evidence tampering tests are required")

    depth = read_json(evidence / "depth_score.json")
    if int(depth.get("overall", 0)) < 80:
        raise AssertionError("Depth score is below the campaign gate")
    if int(depth.get("domain_fidelity", 0)) < 16:
        raise AssertionError("Domain fidelity score is below the campaign gate")
    if int(depth.get("security_privacy", 0)) < 12:
        raise AssertionError("Security/privacy score is below the campaign gate")
    if int(depth.get("testing_depth", 0)) < 12:
        raise AssertionError("Testing depth score is below the campaign gate")
    if int(depth.get("critical_findings", 1)) != 0 or int(depth.get("high_findings", 1)) != 0:
        raise AssertionError("Unresolved critical or high findings are not allowed")
    if not depth.get("cited_evidence"):
        raise AssertionError("Depth score must cite evidence")

    asvs = read_json(evidence / "owasp_asvs_5_0_0_matrix.json")
    if asvs.get("version") != "5.0.0" or asvs.get("certification_claim") != "none":
        raise AssertionError("ASVS matrix must be version-qualified and non-certifying")
    ssdf = read_json(evidence / "nist_ssdf_1_1_mapping.json")
    if ssdf.get("version") != "SSDF 1.1 final":
        raise AssertionError("SSDF 1.1 mapping is required as the normative baseline")
    draft = read_json(evidence / "ssdf_1_2_draft_delta.json")
    if "draft" not in str(draft.get("version", "")).lower():
        raise AssertionError("SSDF 1.2 must be tracked only as draft/informative")
    sbom = read_json(evidence / "cyclonedx_1_7_sbom.json")
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.7":
        raise AssertionError("CycloneDX 1.7 SBOM JSON is required")
    provenance = read_json(evidence / "slsa_1_2_provenance_shaped.json")
    if "no SLSA level claimed" not in provenance.get("claim", ""):
        raise AssertionError("SLSA provenance must not claim a SLSA level")


def validate_manifest(root: Path) -> None:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from factory.application_engineering.verification_evidence import (
        generated_app_root,
        validate_manifest_records,
    )

    app_root = generated_app_root(root)
    manifest = app_root / "evidence" / "phase57_verification" / "manifest_sha256.json"
    validate_manifest_records(app_root, manifest)


def validate_tests(root: Path, python: Path) -> None:
    result = run([str(python), "-m", "pytest", "tests/test_phase57_verification_evidence.py", "-q"], root)
    if result.returncode != 0:
        raise AssertionError(result.stdout)
    if "4 passed" not in result.stdout:
        raise AssertionError(f"Unexpected Phase 57 test count/output:\n{result.stdout}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parsed = parser.parse_args()
    root = parsed.project_root.resolve()
    python = canonical_python(root)

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from factory.application_engineering.verification_evidence import run_phase57_verification

    run_phase57_verification(root)
    validate_artifacts(root)
    validate_manifest(root)
    validate_tests(root, python)
    print(
        "Phase 57 verification evidence validation passed: layered verification, traceability, ADRs, "
        "threat catalogue, ASVS 5.0.0 matrix, SSDF mappings, dependency inventory, CycloneDX 1.7 SBOM, "
        "SLSA 1.2 provenance-shaped evidence, manifests, archive, depth score, residual risks, "
        "and tamper tests are present and fail closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
