from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.generators.mock_dispute_app_generator import generate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase30_deep_generated_application_regeneration_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase30/deep_generated_application_regeneration_prompt.md"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase30"
)

TEST_OBLIGATIONS = {
    "unit",
    "integration",
    "contract",
    "negative",
    "resilience",
    "security",
    "performance_smoke",
    "replay",
    "audit",
}

HUMAN_APPROVAL_ACTIONS = {
    "risky self-evolution",
    "destructive actions",
    "merge",
    "tag",
    "release",
    "promotion",
    "live provider calls",
    "certification-related claims",
}


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase30_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase30_deep_generated_application_regeneration.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_regeneration_uses_phase29_generator_output_not_only_docs(tmp_path: Path) -> None:
    result = generate(
        run_id="phase30_generator_output_test",
        workspace_root=tmp_path,
        clean=True,
    )
    manifest = load_json(result.manifest_path)
    emitted_files = {item.relative_path for item in result.generated_files}
    assert manifest["generation_mode"] == "deterministic_template_regeneration"
    assert manifest["phase29_deep_structure_policy"] == (
        "policies/phase29_generated_application_deep_structure_policy.json"
    )
    assert manifest["phase29_deep_structure_policy_recorded"] is True
    assert "generated_application/app/domain/entities.py" in emitted_files
    assert result.manifest_path.is_file()


def test_non_clean_regeneration_is_idempotent_for_existing_output(tmp_path: Path) -> None:
    result = generate(
        run_id="phase30_generator_idempotent_output",
        workspace_root=tmp_path,
        clean=True,
    )
    before = result.manifest_path.read_bytes()

    rerun = generate(
        run_id="phase30_generator_idempotent_output",
        workspace_root=tmp_path,
        clean=False,
    )

    assert rerun.manifest_path == result.manifest_path
    assert rerun.manifest_path.read_bytes() == before


def test_regeneration_workspace_is_not_root_pytest_collection_surface(tmp_path: Path) -> None:
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    result = generate(
        run_id="phase30_pytest_collection_boundary",
        workspace_root=tmp_path,
        clean=True,
    )
    manifest = load_json(result.manifest_path)

    assert "workspace/regeneration_runs" in pyproject_text
    assert "workspace/regeneration_runs" in manifest["pytest_collection_policy"]
    assert "generated tests are preserved" in manifest["pytest_collection_policy"]


def test_deep_generated_application_files_and_directories_are_emitted(tmp_path: Path) -> None:
    result = generate(run_id="phase30_deep_structure_test", workspace_root=tmp_path, clean=True)
    output_root = result.output_dir / "generated"
    emitted_files = {item.relative_path for item in result.generated_files}
    assert {
        "generated_application/app/domain/entities.py",
        "generated_application/app/application/services.py",
        "generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
        "generated_application/app/interfaces/api/main.py",
        "generated_application/app/observability/metrics.py",
        "generated_application/app/security/input_validation.py",
    }.issubset(emitted_files)
    for relative_dir in [
        "generated_application/app/domain",
        "generated_application/app/application",
        "generated_application/app/infrastructure",
        "generated_application/app/interfaces",
        "generated_application/app/observability",
        "generated_application/app/security",
        "generated_application/app/tests",
    ]:
        assert (output_root / relative_dir).is_dir()


def test_required_test_obligation_categories_are_represented(tmp_path: Path) -> None:
    policy = load_json(POLICY_PATH)
    matrix = load_json(ARTIFACT_DIR / "certification_readiness_test_obligation_matrix.json")
    result = generate(run_id="phase30_test_obligations", workspace_root=tmp_path, clean=True)
    manifest = load_json(result.manifest_path)
    output_root = result.output_dir / "generated"

    assert TEST_OBLIGATIONS.issubset(policy["certification_readiness_test_obligations"])
    assert TEST_OBLIGATIONS.issubset(matrix)
    assert TEST_OBLIGATIONS.issubset(manifest["certification_readiness_test_obligations"])
    for relative_dir in [
        "generated_application/app/tests/unit",
        "generated_application/app/tests/integration",
        "generated_application/app/tests/contract",
        "generated_application/app/tests/negative",
        "generated_application/app/tests/resilience",
        "generated_application/app/tests/security",
        "generated_application/app/tests/performance",
        "generated_application/app/tests/replay",
        "generated_application/app/tests/audit",
    ]:
        assert (output_root / relative_dir).is_dir()


def test_no_live_ecosystem_integration_is_introduced(tmp_path: Path) -> None:
    policy = load_json(POLICY_PATH)
    result = generate(run_id="phase30_no_live_integration", workspace_root=tmp_path, clean=True)
    manifest = load_json(result.manifest_path)
    generated_text = "\n".join(
        (result.output_dir / "generated" / item.relative_path).read_text(encoding="utf-8")
        for item in result.generated_files
    )

    assert policy["live_provider_calls_allowed"] is False
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert manifest["live_provider_calls_allowed"] is False
    assert manifest["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert "requests." not in generated_text
    assert "httpx." not in generated_text
    assert "razorpay" not in generated_text.lower()


def test_certification_ready_not_certified_boundary_is_preserved(tmp_path: Path) -> None:
    policy = load_json(POLICY_PATH)
    audit = load_json(ARTIFACT_DIR / "deep_generated_application_regeneration_audit.json")
    result = generate(run_id="phase30_certification_boundary", workspace_root=tmp_path, clean=True)
    manifest = load_json(result.manifest_path)

    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert audit["certification_boundary"] == "certification_ready_not_certified"
    assert manifest["certification_boundary"] == "certification_ready_not_certified"
    assert policy["official_certification_claimed"] is False
    assert audit["official_certification_claimed"] is False
    assert manifest["official_certification_claimed"] is False
    assert manifest["official_certification_granted"] is False


def test_official_certification_is_not_claimed(tmp_path: Path) -> None:
    result = generate(run_id="phase30_no_certification_claim", workspace_root=tmp_path, clean=True)
    generated_text = "\n".join(
        (result.output_dir / "generated" / item.relative_path).read_text(encoding="utf-8")
        for item in result.generated_files
    ).lower()
    prohibited = [
        "officially certified",
        "official certification granted",
        "npci certified",
        "rbi approved",
        "bank approved",
        "production ready",
        "live payment capability",
    ]
    assert all(phrase not in generated_text for phrase in prohibited)


def test_human_approval_is_required_for_risky_actions(tmp_path: Path) -> None:
    policy = load_json(POLICY_PATH)
    audit = load_json(ARTIFACT_DIR / "deep_generated_application_regeneration_audit.json")
    result = generate(run_id="phase30_human_approval", workspace_root=tmp_path, clean=True)
    manifest = load_json(result.manifest_path)

    assert HUMAN_APPROVAL_ACTIONS.issubset(policy["human_approval_required_for"])
    assert HUMAN_APPROVAL_ACTIONS.issubset(manifest["risky_actions_require_human_approval"])
    assert audit["risky_self_evolution_requires_human_approval"] is True
    assert audit["destructive_actions_require_human_approval"] is True
    assert audit["merge_tag_release_promotion_require_human_approval"] is True
    assert audit["live_provider_calls_require_human_approval"] is True
    assert audit["certification_related_claims_require_human_approval"] is True


def test_phase11c_prompt_contracts_remain_inherited() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt
