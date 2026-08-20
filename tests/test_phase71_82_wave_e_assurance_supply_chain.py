from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
TEMPLATE_MANIFEST_PATH = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/template_manifest.v1.json"
)
EXPECTED_GENERATED_FILE_COUNT = len(
    json.loads(TEMPLATE_MANIFEST_PATH.read_text(encoding="utf-8"))["template_files"]
)


def test_wave_e_template_contains_assurance_supply_chain_evidence() -> None:
    evidence_root = TEMPLATE_ROOT / "evidence" / "assurance"
    required = [
        "asvs_5_0_l2_mapping.json",
        "owasp_api_security_checks.json",
        "samm_maturity_evidence.json",
        "threat_model_abuse_cases.json",
        "dependency_license_inventory.json",
        "cyclonedx_1_7_sbom.json",
        "spdx_3_0_sbom.json",
        "deterministic_build_manifest.json",
        "slsa_1_2_provenance_verification.json",
        "openssf_scorecard_assessment.json",
        "verification_summary.json",
    ]
    for name in required:
        assert (evidence_root / name).is_file()

    combined = "\n".join((evidence_root / name).read_text(encoding="utf-8") for name in required)
    deterministic_manifest = json.loads(
        (evidence_root / "deterministic_build_manifest.json").read_text(encoding="utf-8")
    )
    assert (
        deterministic_manifest["dependency_lock_status"]["installed_distribution_record_hash_source"]
        == "canonical_repository_virtualenv installed dist-info RECORD metadata"
    )
    assert "/home/" not in json.dumps(deterministic_manifest, sort_keys=True)
    for marker in [
        "OWASP ASVS",
        "Level 2 oriented",
        "OWASP API Security",
        "OWASP SAMM",
        "CycloneDX",
        "SPDX-3.0",
        "no SLSA level claimed",
        "OpenSSF",
        "certification_claim",
        "none",
    ]:
        assert marker in combined


def test_wave_e_validation_proves_fresh_two_build_generated_output() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase71_82_wave_e_assurance_supply_chain.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["generated_file_count"] == EXPECTED_GENERATED_FILE_COUNT
    assert payload["two_build_comparison"]["status"] == "passed"
    assert "spdx_3_0_exact_version_identity_parity" in payload["structural_checks"]
    assert payload["official_certification_claimed"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["real_payment_calls_allowed"] is False
    assert (
        "generated_application/app/tests/audit/test_assurance_supply_chain_evidence.py"
        in payload["wave_e_generated_files"]
    )
    assert (
        "generated_application/app/tests/negative/test_negative_security_and_persistence.py"
        in payload["wave_e_generated_files"]
    )
