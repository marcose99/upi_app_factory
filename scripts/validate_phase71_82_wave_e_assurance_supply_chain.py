#!/usr/bin/env python3
from __future__ import annotations

import atexit
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_STARTUP_PYCACHE = tempfile.TemporaryDirectory(
    prefix="phase71_82_wave_e_startup_pycache_"
)
sys.pycache_prefix = _STARTUP_PYCACHE.name
atexit.register(_STARTUP_PYCACHE.cleanup)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.generators.mock_dispute_app_generator import generate  # noqa: E402


RUN_ID_A = "phase71_82_wave_e_assurance_supply_chain_a"
RUN_ID_B = "phase71_82_wave_e_assurance_supply_chain_b"
TEMPLATE_GENERATED_ROOT = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
)
ASSURANCE_ROOT = "generated_application/evidence/assurance"
EXPECTED_GENERATED_FILE_COUNT = 78
REQUIRED_WAVE_E_FILES = {
    f"{ASSURANCE_ROOT}/asvs_5_0_l2_mapping.json",
    f"{ASSURANCE_ROOT}/owasp_api_security_checks.json",
    f"{ASSURANCE_ROOT}/samm_maturity_evidence.json",
    f"{ASSURANCE_ROOT}/threat_model_abuse_cases.json",
    f"{ASSURANCE_ROOT}/dependency_license_inventory.json",
    f"{ASSURANCE_ROOT}/cyclonedx_1_7_sbom.json",
    f"{ASSURANCE_ROOT}/spdx_3_0_sbom.json",
    f"{ASSURANCE_ROOT}/deterministic_build_manifest.json",
    f"{ASSURANCE_ROOT}/slsa_1_2_provenance_verification.json",
    f"{ASSURANCE_ROOT}/openssf_scorecard_assessment.json",
    f"{ASSURANCE_ROOT}/verification_summary.json",
    "generated_application/docs/security_design.md",
    "generated_application/app/tests/audit/test_assurance_supply_chain_evidence.py",
    "generated_application/app/tests/negative/test_negative_security_and_persistence.py",
    "generated_application/scripts/start_local.sh",
}
EXPECTED_DEPENDENCIES = {
    "fastapi",
    "uvicorn",
    "pydantic",
    "python-dotenv",
    "PyYAML",
    "httpx",
    "sqlite3",
}
USER_HOME_ABSOLUTE_PATH = re.compile(r"/home/[^/\\\s\"']+")


def bytecode_artifacts(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    artifacts: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}:
            relative_path = path.relative_to(root).as_posix()
            artifacts[relative_path] = "file" if path.is_file() else "dir"
    return artifacts


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def declared_dependencies() -> set[str]:
    names: set[str] = set()
    in_dependencies = False
    for line in (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_dependencies = True
            continue
        if in_dependencies and stripped == "]":
            break
        if not in_dependencies or not stripped.startswith('"'):
            continue
        dependency = stripped.strip(",").strip('"')
        names.add(dependency.split(">=", 1)[0])
    names.add("sqlite3")
    return names


def generated_file_fingerprints(manifest_path: Path) -> dict[str, tuple[str, int]]:
    manifest = read_json(manifest_path)
    files = manifest.get("generated_files", [])
    if not isinstance(files, list):
        raise RuntimeError("generated_files must be a list")
    return {
        str(item["relative_path"]): (str(item["sha256"]), int(item["size_bytes"]))
        for item in files
        if isinstance(item, dict)
    }


def validate_json_shapes(generated_root: Path) -> list[str]:
    evidence_root = generated_root / ASSURANCE_ROOT
    checks: list[str] = []

    asvs = read_json(evidence_root / "asvs_5_0_l2_mapping.json")
    if asvs.get("standard") != "OWASP ASVS" or asvs.get("version") != "5.0":
        raise RuntimeError("ASVS 5.0 mapping is required")
    if asvs.get("level_orientation") != "Level 2 oriented":
        raise RuntimeError("ASVS Level 2 orientation is required")
    if asvs.get("certification_claim") != "none":
        raise RuntimeError("ASVS evidence must not claim certification")
    if not asvs.get("unresolved_risks") or not asvs["unresolved_risks"][0].get("owner"):
        raise RuntimeError("ASVS unresolved risk owner is required")
    checks.append("asvs_5_0_level_2_oriented_mapping")

    api = read_json(evidence_root / "owasp_api_security_checks.json")
    api_ids = {str(item.get("id")) for item in api.get("checks", []) if isinstance(item, dict)}
    if not {"API1", "API4", "API7", "API10"}.issubset(api_ids):
        raise RuntimeError("OWASP API Security checks are incomplete")
    checks.append("owasp_api_security_abuse_checks")

    samm = read_json(evidence_root / "samm_maturity_evidence.json")
    if not samm.get("unresolved_risk_ownership"):
        raise RuntimeError("SAMM unresolved risk ownership is required")
    if set(samm.get("maturity_model", {})) != {
        "governance",
        "design",
        "implementation",
        "verification",
        "operations",
    }:
        raise RuntimeError("SAMM maturity evidence must cover five business functions")
    checks.append("samm_maturity_evidence_with_risk_ownership")

    threat = read_json(evidence_root / "threat_model_abuse_cases.json")
    if len(threat.get("abuse_cases", [])) < 5:
        raise RuntimeError("Threat model must include at least five abuse cases")
    if not threat.get("unresolved_risks") or not threat["unresolved_risks"][0].get("owner"):
        raise RuntimeError("Threat model unresolved risk owner is required")
    checks.append("threat_model_and_abuse_cases")

    inventory = read_json(evidence_root / "dependency_license_inventory.json")
    if inventory.get("new_dependencies_added") != []:
        raise RuntimeError("Wave E must not add dependencies")
    lock_evidence = inventory.get("offline_lock_evidence", {})
    if not isinstance(lock_evidence, dict):
        raise RuntimeError("Dependency inventory must include offline lock evidence")
    if lock_evidence.get("lockfile") != "requirements/ci-lock.txt":
        raise RuntimeError("Offline lock evidence must reference requirements/ci-lock.txt")
    if lock_evidence.get("exact_runtime_versions_present") is not True:
        raise RuntimeError("Offline lock evidence must record exact runtime versions")
    if lock_evidence.get("installed_distribution_metadata_inspected") is not True:
        raise RuntimeError("Offline lock evidence must record installed distribution metadata inspection")
    inventory_names = {
        str(item.get("name")) for item in inventory.get("components", []) if isinstance(item, dict)
    }
    if inventory_names != declared_dependencies() or inventory_names != EXPECTED_DEPENDENCIES:
        raise RuntimeError("Dependency inventory must match the existing pyproject dependency set")
    if not all(
        isinstance(item, dict) and item.get("resolved_version")
        for item in inventory.get("components", [])
        if item.get("name") != "sqlite3"
    ):
        raise RuntimeError("Dependency inventory must include exact resolved runtime pins")
    transitive = inventory.get("transitive_dependency_license_evidence", [])
    if not isinstance(transitive, list) or len(transitive) < 8:
        raise RuntimeError("Dependency inventory must include transitive license evidence")
    installed_integrity = inventory.get("installed_file_integrity_evidence", [])
    if not isinstance(installed_integrity, list) or len(installed_integrity) < 6:
        raise RuntimeError("Dependency inventory must include installed-file integrity evidence")
    if not all(
        isinstance(item, dict)
        and int(item.get("record_sha256_entries", 0)) > 0
        and "sha256=" in str(item.get("sample_record_entry", ""))
        for item in installed_integrity
    ):
        raise RuntimeError("Installed-file integrity evidence must include RECORD sha256 samples")
    if inventory.get("license_evidence", {}).get("project_license") != "Apache-2.0":
        raise RuntimeError("Project license evidence must be Apache-2.0")
    checks.append("license_dependency_inventory_existing_set")

    cyclonedx = read_json(evidence_root / "cyclonedx_1_7_sbom.json")
    if cyclonedx.get("bomFormat") != "CycloneDX" or cyclonedx.get("specVersion") != "1.7":
        raise RuntimeError("CycloneDX 1.7 SBOM is required")
    cyclonedx_names = {
        str(item.get("name")) for item in cyclonedx.get("components", []) if isinstance(item, dict)
    }
    if cyclonedx_names != EXPECTED_DEPENDENCIES:
        raise RuntimeError("CycloneDX components must match expected dependencies")
    if not all(
        isinstance(item, dict)
        and item.get("version")
        and not str(item.get("version", "")).startswith(">=")
        and item.get("bom-ref")
        and isinstance(item.get("properties"), list)
        for item in cyclonedx.get("components", [])
    ):
        raise RuntimeError("CycloneDX components must include deterministic identity properties")
    checks.append("cyclonedx_1_7_local_shape_validation")

    spdx = read_json(evidence_root / "spdx_3_0_sbom.json")
    if spdx.get("spdxVersion") != "SPDX-3.0" or spdx.get("dataLicense") != "CC0-1.0":
        raise RuntimeError("SPDX 3.0 SBOM conversion evidence is required")
    if "no external registry" not in str(spdx.get("claim", "")):
        raise RuntimeError("SPDX evidence must disclose local-only limitations")
    if any(
        isinstance(item, dict) and item.get("licenseConcluded") == "NOASSERTION"
        for item in spdx.get("elements", [])
    ):
        raise RuntimeError("SPDX package licenses must not be NOASSERTION in local evidence")
    spdx_components = {
        str(item.get("name")): item
        for item in spdx.get("elements", [])
        if isinstance(item, dict) and item.get("type") == "Package"
    }
    cyclonedx_components = {
        str(item.get("name")): item
        for item in cyclonedx.get("components", [])
        if isinstance(item, dict)
    }
    for name in EXPECTED_DEPENDENCIES:
        if name not in spdx_components or name not in cyclonedx_components:
            raise RuntimeError(f"SBOM component missing from parity check: {name}")
        if spdx_components[name].get("version") != cyclonedx_components[name].get("version"):
            raise RuntimeError(f"SPDX/CycloneDX version mismatch for {name}")
        refs = spdx_components[name].get("externalRefs", [])
        if name != "sqlite3" and f"@{cyclonedx_components[name].get('version')}" not in json.dumps(refs):
            raise RuntimeError(f"SPDX purl does not preserve exact resolved version for {name}")
    checks.append("spdx_3_0_exact_version_identity_parity")

    build = read_json(evidence_root / "deterministic_build_manifest.json")
    if build.get("network_access_required") is not False:
        raise RuntimeError("Deterministic build manifest must require no network")
    if not build.get("variance_explanation"):
        raise RuntimeError("Deterministic build manifest must explain variance")
    lock_status = build.get("dependency_lock_status", {})
    if not isinstance(lock_status, dict) or lock_status.get("resolved_lockfile_present") is not True:
        raise RuntimeError("Deterministic build manifest must record offline lock presence")
    if lock_status.get("installed_distribution_record_hashes_present") is not True:
        raise RuntimeError("Deterministic build manifest must record installed RECORD hashes")
    record_hash_source = str(lock_status.get("installed_distribution_record_hash_source", ""))
    if record_hash_source != "canonical_repository_virtualenv installed dist-info RECORD metadata":
        raise RuntimeError("Installed RECORD hash source must use a symbolic virtualenv source")
    if USER_HOME_ABSOLUTE_PATH.search(json.dumps(build, sort_keys=True)):
        raise RuntimeError("Deterministic build manifest must not contain user-home absolute paths")
    if lock_status.get("wheel_hashes_present") is not False:
        raise RuntimeError("Wheel hash absence must remain truthful without a wheelhouse")
    checks.append("deterministic_build_manifest")

    slsa = read_json(evidence_root / "slsa_1_2_provenance_verification.json")
    if "no SLSA level claimed" not in str(slsa.get("claim", "")):
        raise RuntimeError("SLSA-style provenance must not claim an attained level")
    external = slsa.get("buildDefinition", {}).get("externalParameters", {})
    if external.get("network") != "disabled" or external.get("package_registry_publish") != "disabled":
        raise RuntimeError("SLSA-style provenance must remain local and unpublished")
    verification_scope = slsa.get("verification_without_attained_level", {})
    if not isinstance(verification_scope, dict):
        raise RuntimeError("SLSA-style provenance verification scope must be an object")
    if verification_scope.get("installed_file_record_hashes_checked") is not True:
        raise RuntimeError("SLSA-style provenance must record installed file hash checks")
    if verification_scope.get("upstream_artifact_hashes_checked") is not False:
        raise RuntimeError("SLSA-style provenance must not claim upstream artifact hash checks")
    checks.append("slsa_1_2_style_provenance_without_level_claim")

    openssf = read_json(evidence_root / "openssf_scorecard_assessment.json")
    if openssf.get("scorecard_claim") != "no numeric OpenSSF Scorecard score claimed":
        raise RuntimeError("OpenSSF assessment must not claim a numeric Scorecard result")
    if not any(
        isinstance(item, dict) and item.get("status") == "unresolved" and item.get("owner")
        for item in openssf.get("checks", [])
    ):
        raise RuntimeError("OpenSSF unresolved findings must have owners")
    checks.append("openssf_baseline_scorecard_oriented_assessment")

    summary = read_json(evidence_root / "verification_summary.json")
    if summary.get("certification_claim") != "none":
        raise RuntimeError("Verification summary must not claim certification")
    if any(summary.get("live_integrations", {}).values()):
        raise RuntimeError("Verification summary must keep all live integrations disabled")
    resolved = summary.get("resolved_repair_evidence", [])
    if not any(
        isinstance(item, dict)
        and item.get("id") == "OFFLINE-LOCK-001"
        and item.get("source") == "requirements/ci-lock.txt"
        for item in resolved
    ):
        raise RuntimeError("Verification summary must record offline lock repair evidence")
    checks.append("non_claim_summary_and_live_boundary")

    security_design = (generated_root / "generated_application/docs/security_design.md").read_text(
        encoding="utf-8"
    )
    for marker in [
        "extra=\"forbid\"",
        "signed local bearer token",
        "Approval nonces are consumed",
        "Upstream wheel/archive reproducibility remains unattained",
    ]:
        if marker not in security_design:
            raise RuntimeError(f"Security design is missing marker: {marker}")
    checks.append("security_design_matches_current_controls")

    return checks


def validate() -> dict[str, Any]:
    before_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)

    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_e_generation_") as workspace:
        workspace_root = Path(workspace)
        first = generate(run_id=RUN_ID_A, workspace_root=workspace_root, clean=True)
        second = generate(run_id=RUN_ID_B, workspace_root=workspace_root, clean=True)

        emitted_files = {item.relative_path for item in first.generated_files}
        missing = sorted(REQUIRED_WAVE_E_FILES - emitted_files)
        if missing:
            raise RuntimeError(f"Fresh generated output missing Wave E files: {missing}")
        if len(first.generated_files) != EXPECTED_GENERATED_FILE_COUNT:
            raise RuntimeError(
                f"Expected {EXPECTED_GENERATED_FILE_COUNT} generated files, got {len(first.generated_files)}"
            )

        first_fingerprints = generated_file_fingerprints(first.manifest_path)
        second_fingerprints = generated_file_fingerprints(second.manifest_path)
        if first_fingerprints != second_fingerprints:
            variance = sorted(
                set(first_fingerprints) ^ set(second_fingerprints)
                | {
                    path
                    for path in set(first_fingerprints) & set(second_fingerprints)
                    if first_fingerprints[path] != second_fingerprints[path]
                }
            )
            raise RuntimeError(f"Two-build generated file comparison failed: {variance}")

        shape_checks = validate_json_shapes(first.output_dir / "generated")

        first_manifest = read_json(first.manifest_path)
        second_manifest = read_json(second.manifest_path)
        if first_manifest["run_id"] == second_manifest["run_id"]:
            raise RuntimeError("Two-build comparison requires distinct run ids")
        if first_manifest["generation_mode"] != second_manifest["generation_mode"]:
            raise RuntimeError("Generation modes differ across builds")

        proof: dict[str, Any] = {
            "passed": True,
            "run_ids": [first.run_id, second.run_id],
            "generation_mode": first_manifest["generation_mode"],
            "generated_file_count": len(first.generated_files),
            "wave_e_generated_files": sorted(REQUIRED_WAVE_E_FILES),
            "structural_checks": shape_checks,
            "two_build_comparison": {
                "status": "passed",
                "compared_generated_template_files": len(first_fingerprints),
                "variance_explanation": [
                    "generation_manifest.run_id varies by design",
                    "generation_manifest.generated_at_utc varies by design",
                    "copied generated template file hashes and sizes are identical",
                ],
            },
            "live_provider_calls_allowed": first_manifest["live_provider_calls_allowed"],
            "real_payment_calls_allowed": first_manifest["real_payment_calls_allowed"],
            "official_certification_claimed": first_manifest["official_certification_claimed"],
        }

    after_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)
    if after_template_bytecode != before_template_bytecode:
        raise RuntimeError("Validation mutated template bytecode artifacts")

    return proof


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2) + "\n")
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
