from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_EVIDENCE_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_FILES = [
    "factory_governance/phase1/requirements_intake_contract.v1.json",
    "factory_governance/phase1/mock_ecosystem.v1.json",
    "factory_governance/phase1/agent_swarm_contract.v1.json",
    "factory_governance/phase1/phase_execution_policy.v1.json",
    "factory_governance/phase1/evidence_label_policy.v1.json",
    "factory_governance/phase1/human_feedback_policy.v1.json",
    "factory_governance/templates/architecture_decision_record_template.v1.md",
    "docs/adr/ADR-0001-lightweight-local-first-governed-factory.md",
    "docs/phase_1/foundation_hardening.md",
    "evidence/releases/phase_1_foundation_plan.md",
    "prompts/agents/requirements_analyst.md",
    "prompts/agents/architecture_agent.md",
    "prompts/agents/mock_ecosystem_agent.md",
    "prompts/agents/implementation_agent.md",
    "prompts/agents/test_validation_agent.md",
    "prompts/agents/governance_reviewer_agent.md",
    "prompts/agents/human_feedback_reviewer_agent.md",
]


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: list[str]


def read_json(relative_path: str, errors: list[str]) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"required file missing: {relative_path}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {relative_path}: {exc}")
        return {}

    if not isinstance(value, dict):
        errors.append(f"JSON root must be object in {relative_path}")
        return {}

    return value


def read_text(relative_path: str, errors: list[str]) -> str:
    path = PROJECT_ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"required file missing: {relative_path}")
        return ""


def require_labels(text: str, relative_path: str, errors: list[str]) -> None:
    for label in sorted(REQUIRED_EVIDENCE_LABELS):
        if label not in text:
            errors.append(f"required evidence label {label} missing in {relative_path}")


def validate_required_files(errors: list[str]) -> None:
    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).is_file():
            errors.append(f"required file missing: {relative_path}")


def validate_requirements_contract(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/requirements_intake_contract.v1.json"
    data = read_json(relative_path, errors)

    constraints = data.get("mandatory_constraints", {})
    if not isinstance(constraints, dict):
        errors.append(f"mandatory_constraints must be an object in {relative_path}")
        return

    required_true_flags = [
        "no_real_upi_npci_rbi_bank_psp_switch_or_settlement_calls",
        "all_external_systems_are_mocked",
        "openai_is_model_provider",
        "lightweight_local_first",
        "production_disciplined",
        "modular_adapters_required",
        "human_feedback_required",
        "validation_after_each_phase",
    ]

    for flag in required_true_flags:
        if constraints.get(flag) is not True:
            errors.append(f"{flag} must be true in {relative_path}")

    labels = set(data.get("evidence_labels_required", []))
    missing_labels = REQUIRED_EVIDENCE_LABELS - labels
    for label in sorted(missing_labels):
        errors.append(f"required evidence label {label} missing from {relative_path}")


def validate_mock_ecosystem(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/mock_ecosystem.v1.json"
    data = read_json(relative_path, errors)

    global_rule = data.get("global_boundary_rule", {})
    if not isinstance(global_rule, dict):
        errors.append(f"global_boundary_rule must be an object in {relative_path}")
    else:
        if global_rule.get("boundary_type") != "MOCK_BOUNDARY":
            errors.append(f"global boundary_type must be MOCK_BOUNDARY in {relative_path}")
        if global_rule.get("real_integration_allowed") is not False:
            errors.append(f"real_integration_allowed must be false in {relative_path}")
        if global_rule.get("synthetic_data_only") is not True:
            errors.append(f"synthetic_data_only must be true in {relative_path}")

    systems = data.get("external_systems", [])
    if not isinstance(systems, list) or not systems:
        errors.append(f"external_systems must be a non-empty list in {relative_path}")
        return

    for index, system in enumerate(systems):
        if not isinstance(system, dict):
            errors.append(f"external_systems[{index}] must be an object in {relative_path}")
            continue

        system_id = system.get("system_id", f"index_{index}")
        if system.get("boundary_type") != "MOCK_BOUNDARY":
            errors.append(f"{system_id}: boundary_type must be MOCK_BOUNDARY")
        if system.get("real_integration_allowed") is not False:
            errors.append(f"{system_id}: real_integration_allowed must be false")
        if system.get("data_label") != "SYNTHETIC_DATA":
            errors.append(f"{system_id}: data_label must be SYNTHETIC_DATA")
        if not system.get("adapter_module_target"):
            errors.append(f"{system_id}: adapter_module_target is required")


def validate_agent_swarm_contract(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/agent_swarm_contract.v1.json"
    data = read_json(relative_path, errors)

    rules = data.get("global_agent_rules", {})
    if not isinstance(rules, dict):
        errors.append(f"global_agent_rules must be an object in {relative_path}")
    else:
        if rules.get("model_provider") != "OpenAI":
            errors.append(f"model_provider must be OpenAI in {relative_path}")
        for flag in [
            "must_use_mock_adapters",
            "must_emit_evidence_labels",
            "must_accept_human_feedback",
            "must_run_validation_after_changes",
            "must_prefer_lightweight_local_first_tools",
        ]:
            if rules.get(flag) is not True:
                errors.append(f"{flag} must be true in {relative_path}")
        if rules.get("may_call_real_payment_systems") is not False:
            errors.append(f"may_call_real_payment_systems must be false in {relative_path}")

    agents = data.get("agents", [])
    if not isinstance(agents, list) or len(agents) < 5:
        errors.append(f"agents must contain at least five agents in {relative_path}")
        return

    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            errors.append(f"agents[{index}] must be an object in {relative_path}")
            continue

        agent_id = agent.get("agent_id", f"index_{index}")
        if agent.get("may_call_real_payment_systems") is not False:
            errors.append(f"{agent_id}: may_call_real_payment_systems must be false")
        if agent.get("requires_human_review_before_release") is not True:
            errors.append(f"{agent_id}: requires_human_review_before_release must be true")
        outputs = agent.get("required_outputs", [])
        if not isinstance(outputs, list) or not outputs:
            errors.append(f"{agent_id}: required_outputs must be a non-empty list")


def validate_phase_execution_policy(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/phase_execution_policy.v1.json"
    data = read_json(relative_path, errors)

    policy = data.get("policy", {})
    if not isinstance(policy, dict):
        errors.append(f"policy must be an object in {relative_path}")
        return

    for flag in [
        "build_in_phases",
        "validation_after_each_phase",
        "human_review_after_each_phase",
        "no_big_bang_generation",
        "commit_after_clean_validation",
        "tag_major_restore_points",
    ]:
        if policy.get(flag) is not True:
            errors.append(f"{flag} must be true in {relative_path}")

    gates = data.get("minimum_exit_gates", [])
    if not isinstance(gates, list):
        errors.append(f"minimum_exit_gates must be a list in {relative_path}")
        return

    for gate in ["ruff", "mypy", "pytest", "phase_specific_validator"]:
        if gate not in gates:
            errors.append(f"minimum exit gate missing {gate} in {relative_path}")


def validate_evidence_label_policy(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/evidence_label_policy.v1.json"
    data = read_json(relative_path, errors)

    labels = data.get("required_labels", [])
    if not isinstance(labels, list):
        errors.append(f"required_labels must be a list in {relative_path}")
        return

    label_values = {
        item.get("label")
        for item in labels
        if isinstance(item, dict)
    }

    missing_labels = REQUIRED_EVIDENCE_LABELS - label_values
    for label in sorted(missing_labels):
        errors.append(f"required evidence label {label} missing from {relative_path}")

    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        errors.append(f"rules must be an object in {relative_path}")
        return

    for flag in [
        "labels_required_on_agent_outputs",
        "unsupported_official_claims_forbidden",
        "mock_boundary_label_required_for_external_systems",
        "synthetic_data_label_required_for_demo_data",
    ]:
        if rules.get(flag) is not True:
            errors.append(f"{flag} must be true in {relative_path}")


def validate_human_feedback_policy(errors: list[str]) -> None:
    relative_path = "factory_governance/phase1/human_feedback_policy.v1.json"
    data = read_json(relative_path, errors)

    policy = data.get("policy", {})
    if not isinstance(policy, dict):
        errors.append(f"policy must be an object in {relative_path}")
        return

    if policy.get("feedback_module_required") is not True:
        errors.append(f"feedback_module_required must be true in {relative_path}")
    if policy.get("feedback_endpoint") != "/feedback":
        errors.append(f"feedback_endpoint must be /feedback in {relative_path}")
    if policy.get("audit_linked") is not True:
        errors.append(f"audit_linked must be true in {relative_path}")
    if policy.get("feedback_may_block_phase_exit") is not True:
        errors.append(f"feedback_may_block_phase_exit must be true in {relative_path}")

    statuses = data.get("allowed_statuses", [])
    if "SUBMITTED" not in statuses or "CLOSED" not in statuses:
        errors.append(f"allowed_statuses must include SUBMITTED and CLOSED in {relative_path}")


def validate_prompt_files(errors: list[str]) -> None:
    prompt_paths = [
        "prompts/agents/requirements_analyst.md",
        "prompts/agents/architecture_agent.md",
        "prompts/agents/mock_ecosystem_agent.md",
        "prompts/agents/implementation_agent.md",
        "prompts/agents/test_validation_agent.md",
        "prompts/agents/governance_reviewer_agent.md",
        "prompts/agents/human_feedback_reviewer_agent.md",
    ]

    required_phrase = "No real UPI/NPCI/RBI/bank/payment system calls are allowed."

    for relative_path in prompt_paths:
        text = read_text(relative_path, errors)
        require_labels(text, relative_path, errors)
        if required_phrase not in text:
            errors.append(f"required no-real-payment-calls phrase missing in {relative_path}")


def validate_text_artifacts(errors: list[str]) -> None:
    text_paths = [
        "factory_governance/templates/architecture_decision_record_template.v1.md",
        "docs/adr/ADR-0001-lightweight-local-first-governed-factory.md",
        "docs/phase_1/foundation_hardening.md",
        "evidence/releases/phase_1_foundation_plan.md",
    ]

    for relative_path in text_paths:
        text = read_text(relative_path, errors)
        require_labels(text, relative_path, errors)


def validate(project_root: Path | None = None) -> ValidationResult:
    del project_root
    errors: list[str] = []

    validate_required_files(errors)
    validate_requirements_contract(errors)
    validate_mock_ecosystem(errors)
    validate_agent_swarm_contract(errors)
    validate_phase_execution_policy(errors)
    validate_evidence_label_policy(errors)
    validate_human_feedback_policy(errors)
    validate_prompt_files(errors)
    validate_text_artifacts(errors)

    return ValidationResult(passed=not errors, errors=errors)


def main() -> int:
    result = validate()
    print(
        json.dumps(
            {
                "passed": result.passed,
                "errors": result.errors,
            },
            indent=2,
        )
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
