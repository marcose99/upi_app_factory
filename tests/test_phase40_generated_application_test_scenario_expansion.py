from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase40_generated_application_test_scenario_expansion_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase40/generated_application_test_scenario_expansion_prompt.md"
CATALOG_PATH = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/"
    / "scenario_catalog/phase40_scenario_catalog.json"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase40"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase40_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase40_generated_application_test_scenario_expansion.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scenario_catalog_covers_required_categories_with_expected_outputs() -> None:
    catalog = load_json(CATALOG_PATH)
    scenarios = catalog["scenarios"]
    categories = {scenario["category"] for scenario in scenarios}
    assert categories == {
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
    assert len(scenarios) == 9
    for scenario in scenarios:
        assert scenario["expected_outputs"]
        assert len(scenario["traceability"]) >= 2
        assert any(item.startswith(("GET ", "POST ")) for item in scenario["traceability"])


def test_local_scenario_runner_reports_all_scenarios_passed(tmp_path: Path) -> None:
    report_path = tmp_path / "phase40_report.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase40_generated_application_scenario_report.py",
            "--report-path",
            str(report_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = load_json(report_path)
    assert report["status"] == "passed"
    assert report["scenario_count"] == 9
    assert report["passed_count"] == 9
    assert report["failed_count"] == 0
    assert all(entry["status"] == "passed" for entry in report["scenario_results"])


def test_report_preserves_expected_outputs_and_traceability() -> None:
    report = load_json(ARTIFACT_DIR / "generated_application_scenario_report.json")
    for result in report["scenario_results"]:
        assert result["expected_outputs"]
        assert result["observed_outputs"]
        assert result["traceability"]
    replay = next(
        result
        for result in report["scenario_results"]
        if result["scenario_id"] == "replay_idempotent_duplicate_submission"
    )
    assert replay["observed_outputs"]["same_dispute_id"] is True
    assert replay["observed_outputs"]["idempotency_replays"] == 1


def test_policy_prompt_and_lifecycle_artifacts_keep_boundaries_closed() -> None:
    artifacts = [
        load_json(POLICY_PATH),
        load_json(CATALOG_PATH),
        load_json(ARTIFACT_DIR / "generated_application_scenario_manifest.json"),
        load_json(ARTIFACT_DIR / "generated_application_scenario_gate.json"),
        load_json(ARTIFACT_DIR / "generated_application_scenario_audit.json"),
        load_json(ARTIFACT_DIR / "generated_application_scenario_expected_outputs.json"),
        load_json(ARTIFACT_DIR / "generated_application_scenario_report.json")[
            "safety_boundaries"
        ],
    ]
    for artifact in artifacts:
        assert artifact["certification_boundary"] == "certification_ready_not_certified"
        assert artifact["official_certification_claimed"] is False
        assert artifact["official_certification_granted"] is False
        assert artifact["production_readiness_claimed"] is False
        assert artifact["live_provider_calls_allowed"] is False
        assert artifact["real_secrets_allowed"] is False
        assert artifact["deployment_allowed"] is False
        assert artifact["merge_allowed"] is False
        assert artifact["tag_allowed"] is False
        assert artifact["push_allowed"] is False
        assert artifact["external_ecosystem_integrations"] == "mocked_or_simulated_only"

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt


def test_governance_boundaries_prohibit_live_calls_secrets_and_release_actions() -> None:
    policy = load_json(POLICY_PATH)
    assert policy["local_readiness_scope"] == "local_generated_application_scenario_validation_only"
    assert policy["live_provider_calls_allowed"] is False
    assert policy["real_secrets_allowed"] is False
    assert policy["deployment_allowed"] is False
    assert policy["merge_allowed"] is False
    assert policy["tag_allowed"] is False
    assert policy["push_allowed"] is False
    assert "official certification claim" in policy["prohibited_actions"]
    assert "broad production readiness claim" in policy["prohibited_actions"]
