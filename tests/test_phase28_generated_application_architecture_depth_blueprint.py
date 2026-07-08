from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = (
    PROJECT_ROOT
    / "factory_governance/generated_application_architecture_depth"
    / "phase28_architecture_depth_blueprint.v1.json"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase28"
)


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_phase28_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase28_generated_application_architecture_depth_blueprint.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_required_architecture_depth_artifact_names_are_defined() -> None:
    blueprint = load_json(BLUEPRINT_PATH)
    required = set(blueprint["required_architecture_depth_artifacts"])
    assert {
        "architecture_blueprint.md",
        "domain_model.md",
        "bounded_contexts.md",
        "dispute_state_machine.md",
        "api_contracts.md",
        "data_contracts.md",
        "security_model.md",
        "observability_model.md",
        "test_obligation_matrix.md",
        "certification_readiness_boundary.md",
    }.issubset(required)
    assert {"self_evolution_backlog.json", "self_evolution_backlog.md"} & required


def test_architecture_depth_gate_exists() -> None:
    blueprint = load_json(BLUEPRINT_PATH)
    gate = blueprint["architecture_depth_gate"]
    assert gate["gate_id"] == "PHASE28-GA-ARCHITECTURE-DEPTH-GATE"
    assert gate["required_before_application_generation_success"] is True
    assert gate["failure_mode"] == "BLOCK_GENERATION_SUCCESS_CLAIM"


def test_generator_prompt_requires_architecture_first_generation() -> None:
    prompt = (PROJECT_ROOT / "prompts/phase28/generated_application_architecture_depth_prompt.md").read_text(
        encoding="utf-8"
    )
    assert "Generate architecture first" in prompt
    assert "before expanding business logic" in prompt
    assert "dispute_state_machine.md" in prompt


def test_generated_application_must_not_claim_certification() -> None:
    boundary = load_json(ARTIFACT_DIR / "certification_boundary.json")
    audit = load_json(ARTIFACT_DIR / "phase28_architecture_depth_audit.json")
    assert boundary["certification_boundary"] == "certification_ready_not_certified"
    assert boundary["official_certification_claimed"] is False
    assert audit["official_certification_claimed"] is False
    assert audit["official_certification_granted"] is False


def test_external_ecosystem_integrations_remain_mocked_or_simulated() -> None:
    blueprint = load_json(BLUEPRINT_PATH)
    boundary = blueprint["boundary_rules"]
    assert boundary["live_provider_calls_allowed"] is False
    assert boundary["external_ecosystem_integrations"] == "mocked_or_simulated_only"


def test_self_evolution_proposes_but_risky_changes_are_human_approved() -> None:
    controls = load_json(ARTIFACT_DIR / "self_evolution_backlog_policy.json")
    assert controls["may_propose_improvements"] is True
    assert controls["risky_changes_require_human_approval"] is True
    assert "live provider integration" in controls["risky_change_classes"]
    assert "official certification claim" in controls["risky_change_classes"]


def test_test_obligation_matrix_includes_required_categories() -> None:
    matrix = load_json(ARTIFACT_DIR / "test_obligation_matrix.json")
    assert {
        "positive",
        "negative",
        "contract",
        "security",
        "resilience",
        "replay",
        "audit",
        "performance_smoke",
    }.issubset(matrix)
    assert all(matrix[key] for key in matrix)


def test_architecture_conformance_expectations_include_boundaries_and_state_machine() -> None:
    conformance = load_json(ARTIFACT_DIR / "architecture_conformance_expectations.json")
    import_boundaries = " ".join(conformance["import_boundary_expectations"])
    state_machine = " ".join(conformance["state_machine_expectations"])
    assert "domain layer" in import_boundaries
    assert "interfaces layer" in import_boundaries
    assert "invalid transitions" in state_machine
    assert "idempotent replay" in state_machine
