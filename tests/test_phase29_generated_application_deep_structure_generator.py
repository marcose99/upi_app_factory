from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from factory.generators.mock_dispute_app_generator import generate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "policies/phase29_generated_application_deep_structure_policy.json"
TEMPLATE_MANIFEST_PATH = PROJECT_ROOT / "factory/templates/mock_dispute_app/template_manifest.v1.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase29/generated_application_deep_structure_prompt.md"


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase29_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase29_generated_application_deep_structure_generator.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_factory_requires_deep_generated_application_structure() -> None:
    manifest = load_json(TEMPLATE_MANIFEST_PATH)
    template_files = set(manifest["template_files"])
    assert {
        "generated_application/app/domain/entities.py",
        "generated_application/app/domain/value_objects.py",
        "generated_application/app/application/services.py",
        "generated_application/app/application/unit_of_work.py",
        "generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
        "generated_application/app/infrastructure/persistence/idempotency_store.py",
        "generated_application/app/infrastructure/persistence/outbox.py",
        "generated_application/app/interfaces/api/schemas.py",
        "generated_application/app/interfaces/api/error_handlers.py",
        "generated_application/app/security/pii_redaction.py",
        "generated_application/app/observability/metrics.py",
    }.issubset(template_files)
    assert "generated_application/app/tests/security/" in set(manifest["deep_structure_directories"])
    assert "generated_application/app/tests/performance/" in set(manifest["deep_structure_directories"])


def test_architecture_depth_artifacts_from_phase28_are_generator_inputs() -> None:
    manifest = load_json(TEMPLATE_MANIFEST_PATH)
    policy = load_json(POLICY_PATH)
    phase28_inputs = set(manifest["phase28_architecture_depth_inputs"])
    assert {
        "factory_governance/generated_application_architecture_depth/phase28_architecture_depth_blueprint.v1.json",
        "policies/phase28_generated_application_architecture_depth_policy.json",
        "prompts/phase28/generated_application_architecture_depth_prompt.md",
    }.issubset(phase28_inputs)
    assert policy["phase28_blueprint_required_as_generator_input"] is True


def test_generator_emits_deep_structure_and_records_boundaries(tmp_path: Path) -> None:
    result = generate(run_id="phase29_test", workspace_root=tmp_path, clean=True)
    output_root = result.output_dir / "generated"
    assert (output_root / "generated_application/app/domain/entities.py").is_file()
    assert (output_root / "generated_application/app/interfaces/api/routers").is_dir()
    assert (output_root / "generated_application/app/tests/negative").is_dir()
    manifest = load_json(result.manifest_path)
    assert manifest["certification_boundary"] == "certification_ready_not_certified"
    assert manifest["live_provider_calls_allowed"] is False
    assert manifest["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert "phase28_architecture_depth_inputs" in manifest


def test_no_live_ecosystem_integrations_are_introduced() -> None:
    policy = load_json(POLICY_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert policy["live_provider_calls_allowed"] is False
    assert policy["external_ecosystem_integrations"] == "mocked_or_simulated_only"
    assert "External UPI rails, NPCI/RBI interfaces, banks, PSPs" in prompt
    assert "remain mocked or simulated" in prompt


def test_certification_ready_not_certified_wording_is_preserved() -> None:
    policy = load_json(POLICY_PATH)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    audit = load_json(
        PROJECT_ROOT
        / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_audit.json"
    )
    assert policy["certification_boundary"] == "certification_ready_not_certified"
    assert audit["certification_boundary"] == "certification_ready_not_certified"
    assert "certification_ready_not_certified" in prompt
    assert policy["official_certification_claimed"] is False


def test_risky_self_evolution_remains_human_approved() -> None:
    policy = load_json(POLICY_PATH)
    audit = load_json(
        PROJECT_ROOT
        / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase29/deep_structure_generator_audit.json"
    )
    approvals = set(policy["human_approval_required_for"])
    assert "risky self-evolution" in approvals
    assert "live provider calls" in approvals
    assert "certification-related claims" in approvals
    assert audit["risky_self_evolution_requires_human_approval"] is True
