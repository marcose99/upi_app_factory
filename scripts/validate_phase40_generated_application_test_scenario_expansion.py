#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "phase40_generated_application_test_scenario_expansion"
POLICY_PATH = Path("policies/phase40_generated_application_test_scenario_expansion_policy.json")
PROMPT_PATH = Path("prompts/phase40/generated_application_test_scenario_expansion_prompt.md")
VALIDATOR_PATH = Path("scripts/validate_phase40_generated_application_test_scenario_expansion.py")
RUNNER_PATH = Path("scripts/run_phase40_generated_application_scenario_report.py")
TEST_PATH = Path("tests/test_phase40_generated_application_test_scenario_expansion.py")
CATALOG_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/"
    "scenario_catalog/phase40_scenario_catalog.json"
)
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase40"
)
REPORT_PATH = ARTIFACT_DIR / "generated_application_scenario_report.json"

REQUIRED_CATEGORIES = {
    "positive",
    "negative",
    "edge",
    "contract",
    "replay",
    "audit",
    "resilience",
    "security",
    "performance-smoke",
}

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    VALIDATOR_PATH,
    RUNNER_PATH,
    TEST_PATH,
    CATALOG_PATH,
    ARTIFACT_DIR / "generated_application_scenario_manifest.json",
    ARTIFACT_DIR / "generated_application_scenario_gate.json",
    ARTIFACT_DIR / "generated_application_scenario_audit.json",
    ARTIFACT_DIR / "generated_application_scenario_expected_outputs.json",
    REPORT_PATH,
]

REQUIRED_BOUNDARY_FIELDS = [
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
]

FORBIDDEN_SOURCE_TERMS = [
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "BEGIN PRIVATE KEY",
    "client_secret",
    "api_key",
    "npm publish",
    "git push",
    "git tag",
    "git merge",
    "/deploy",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_boundary_artifact(
    artifact: dict[str, Any],
    errors: list[str],
    context: str,
) -> None:
    if artifact.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"{context} changed certification boundary")
    for field in REQUIRED_BOUNDARY_FIELDS:
        if artifact.get(field) is not False:
            errors.append(f"{context} has invalid boundary field: {field}")
    if artifact.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"{context} does not keep ecosystem integrations mocked")
    readiness_scope = artifact.get("local_readiness_scope")
    if readiness_scope != "local_generated_application_scenario_validation_only":
        errors.append(f"{context} does not scope readiness to local scenario validation only")


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not (PROJECT_ROOT / path).exists():
            errors.append(f"Missing required Phase 40 file: {path}")


def validate_policy_prompt_and_artifacts(errors: list[str]) -> None:
    policy = load_json(PROJECT_ROOT / POLICY_PATH)
    manifest = load_json(PROJECT_ROOT / ARTIFACT_DIR / "generated_application_scenario_manifest.json")
    gate = load_json(PROJECT_ROOT / ARTIFACT_DIR / "generated_application_scenario_gate.json")
    audit = load_json(PROJECT_ROOT / ARTIFACT_DIR / "generated_application_scenario_audit.json")
    expected = load_json(
        PROJECT_ROOT / ARTIFACT_DIR / "generated_application_scenario_expected_outputs.json"
    )
    report = load_json(PROJECT_ROOT / REPORT_PATH)
    prompt = (PROJECT_ROOT / PROMPT_PATH).read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE40-GENERATED-APPLICATION-TEST-SCENARIO-EXPANSION-GATE":
        errors.append("Phase 40 policy missing mandatory gate")
    if policy.get("scenario_catalog") != str(CATALOG_PATH):
        errors.append("Phase 40 policy does not identify scenario catalog")
    if policy.get("scenario_runner") != str(RUNNER_PATH):
        errors.append("Phase 40 policy does not identify scenario runner")
    if policy.get("validation_entrypoint") != str(VALIDATOR_PATH):
        errors.append("Phase 40 policy does not identify validator")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "gate"),
        (audit, "audit"),
        (expected, "expected outputs"),
    ]:
        validate_boundary_artifact(artifact, errors, f"Phase 40 {name}")

    validate_report_boundaries(report, errors, context="Phase 40 persisted scenario report")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        include = "{{ include: " + contract_path + " }}"
        if include not in prompt:
            errors.append(f"Phase 40 prompt does not inherit contract: {contract_path}")

    for phrase in [
        "certification_ready_not_certified",
        "Do not fake success",
        "mocked or simulated",
        "No live provider calls",
        "No real credentials",
        "No deployment, merge, tag, or push",
        "Local-readiness only",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 40 prompt missing required phrase: {phrase}")


def validate_scenario_catalog(errors: list[str]) -> None:
    catalog = load_json(PROJECT_ROOT / CATALOG_PATH)
    validate_boundary_artifact(catalog, errors, "Phase 40 scenario catalog")
    scenarios = catalog.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("Phase 40 scenario catalog does not contain scenarios")
        return
    categories = {
        str(entry.get("category")) for entry in scenarios if isinstance(entry, dict)
    }
    if categories != REQUIRED_CATEGORIES:
        errors.append(f"Phase 40 scenario categories mismatch: {sorted(categories)}")
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            errors.append("Phase 40 scenario catalog includes a non-object scenario")
            continue
        scenario_id = scenario.get("id")
        if not scenario.get("expected_outputs"):
            errors.append(f"Scenario missing expected outputs: {scenario_id}")
        traceability = scenario.get("traceability")
        if not isinstance(traceability, list) or len(traceability) < 2:
            errors.append(f"Scenario missing traceability: {scenario_id}")
        if not any(str(item).startswith(("GET ", "POST ")) for item in traceability or []):
            errors.append(f"Scenario does not trace to an endpoint: {scenario_id}")


def validate_report_boundaries(
    report: dict[str, Any],
    errors: list[str],
    *,
    context: str,
) -> None:
    boundaries = report.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append(f"{context} does not expose safety boundaries")
        return
    validate_boundary_artifact(cast(dict[str, Any], boundaries), errors, context)


def validate_runner_report(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmp:
        report_path = Path(tmp) / "phase40_scenario_report.json"
        result = subprocess.run(
            [sys.executable, str(RUNNER_PATH), "--report-path", str(report_path)],
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            errors.append(f"Phase 40 scenario runner failed: {result.stdout}{result.stderr}")
            return
        if not report_path.is_file():
            errors.append("Phase 40 scenario runner did not write report")
            return
        report = load_json(report_path)

    if report.get("status") != "passed":
        errors.append("Phase 40 scenario report did not pass")
    if report.get("scenario_count") != 9:
        errors.append("Phase 40 scenario report did not run 9 scenarios")
    if set(report.get("categories_covered", [])) != REQUIRED_CATEGORIES:
        errors.append("Phase 40 scenario report does not cover required categories")
    if report.get("failed_count") != 0:
        errors.append("Phase 40 scenario report contains failed scenarios")
    validate_report_boundaries(report, errors, context="Phase 40 generated scenario report")

    results = report.get("scenario_results")
    if not isinstance(results, list) or len(results) != 9:
        errors.append("Phase 40 scenario report does not contain 9 scenario results")
        return
    for result in results:
        if not isinstance(result, dict):
            errors.append("Phase 40 scenario report includes a non-object result")
            continue
        if result.get("status") != "passed":
            errors.append(f"Phase 40 scenario failed: {result.get('scenario_id')}")
        if not result.get("expected_outputs"):
            errors.append(f"Phase 40 result missing expected outputs: {result.get('scenario_id')}")
        if not result.get("observed_outputs"):
            errors.append(f"Phase 40 result missing observed outputs: {result.get('scenario_id')}")
        if not result.get("traceability"):
            errors.append(f"Phase 40 result missing traceability: {result.get('scenario_id')}")


def validate_static_source_boundaries(errors: list[str]) -> None:
    source_paths = [
        PROJECT_ROOT / RUNNER_PATH,
        PROJECT_ROOT / TEST_PATH,
        PROJECT_ROOT / POLICY_PATH,
        PROJECT_ROOT / PROMPT_PATH,
        PROJECT_ROOT / CATALOG_PATH,
    ]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source_text:
            errors.append(f"Phase 40 source includes forbidden term: {term}")
    external_urls = [
        url
        for url in re.findall(r"https?://[^\"'\s]+", source_text)
        if not url.startswith("http://local-generated-upi-dispute-app")
    ]
    if external_urls:
        errors.append(f"Phase 40 source includes external URL dependencies: {external_urls}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if not errors:
        validate_policy_prompt_and_artifacts(errors)
        validate_scenario_catalog(errors)
        validate_static_source_boundaries(errors)
        validate_runner_report(errors)

    if errors:
        print("Phase 40 generated application test scenario expansion validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 40 generated application test scenario expansion validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
