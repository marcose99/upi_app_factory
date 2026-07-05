"""Governed agentic code-generation harness for Phase 11A.

Phase 11A prepares the agent runtime contract and deterministic shadow run.
It does not generate the application implementation yet.

The design is LangGraph/LangChain-ready, but dependency-light by default:
- deterministic_shadow mode works without network calls and without LLM keys
- optional runtime candidates are declared as source candidates
- no agent can commit, push, or bypass validators
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upi_factory.phase10_3_pre_generation_readiness import (
    validate_pre_generation_readiness_artifacts,
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "agentic_generation_harness_manifest.json",
    "agent_role_catalog.json",
    "agent_tool_contracts.json",
    "agent_state_schema.json",
    "agent_execution_policy.md",
    "agent_prompt_registry.json",
    "agent_deterministic_shadow_run.json",
    "proposed_generation_plan.json",
    "phase11b_entry_criteria.md",
    "phase11a_validation_report.json",
)

AGENT_ROLE_IDS: tuple[str, ...] = (
    "implementation_planner_agent",
    "contract_model_agent",
    "mock_adapter_agent",
    "service_logic_agent",
    "test_generation_agent",
    "security_review_agent",
    "observability_agent",
    "documentation_agent",
    "validation_agent",
    "release_readiness_agent",
)

TOOL_IDS: tuple[str, ...] = (
    "read_governance_artifact",
    "read_prompt",
    "propose_file_plan",
    "propose_patch",
    "run_deterministic_validator",
    "record_decision",
    "request_human_approval",
    "write_workspace_draft",
)

REQUIRED_LABELS: tuple[str, ...] = (
    "MOCK_BOUNDARY",
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_DATA",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED",
    "VERSION_SPECIFIC_REVIEW_REQUIRED",
    "HUMAN_APPROVAL_REQUIRED",
    "DETERMINISTIC_VALIDATION_REQUIRED",
)

FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "RBI certified",
    "NPCI certified",
    "officially certified",
    "guaranteed compliant",
    "100% compliant",
    "production compliant",
    "production ready",
    "legal advice",
    "real UPI integration",
    "live NPCI integration",
    "live bank integration",
    "real customer-dispute processing",
)

PROMPT_FILES: tuple[str, ...] = (
    "implementation_planner_agent.md",
    "contract_model_agent.md",
    "mock_adapter_agent.md",
    "service_logic_agent.md",
    "test_generation_agent.md",
    "security_review_agent.md",
    "observability_agent.md",
    "documentation_agent.md",
    "validation_agent.md",
    "release_readiness_agent.md",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing JSON artifact: {path.name}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return {}

    if not isinstance(loaded, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}

    return loaded


def _phase10_3_ready(phase10_3_dir: Path) -> tuple[bool, dict[str, Any]]:
    """Return current Phase 10.3 readiness.

    Prefer recomputation when sibling Phase 10, 10.1, and 10.2 artifact
    directories are available. This avoids stale or missing report problems in
    clean tmp_path tests while still allowing the real repository report to be
    used as an artifact.
    """

    phase_parent = phase10_3_dir.parent
    phase10_dir = phase_parent / "phase10"
    phase10_1_dir = phase_parent / "phase10_1"
    phase10_2_dir = phase_parent / "phase10_2"

    if phase10_dir.exists() and phase10_1_dir.exists() and phase10_2_dir.exists():
        report = validate_pre_generation_readiness_artifacts(
            phase10_3_dir,
            phase10_dir=phase10_dir,
            phase10_1_dir=phase10_1_dir,
            phase10_2_dir=phase10_2_dir,
        )
        return bool(report.get("passed")), report

    errors: list[str] = []
    report = _load_json(phase10_3_dir / "pre_generation_validation_report.json", errors)
    if errors:
        return False, {"passed": False, "errors": errors}

    return bool(report.get("passed")), report

def _agent_roles() -> list[dict[str, Any]]:
    role_descriptions = {
        "implementation_planner_agent": "Converts WBS and readiness manifest into ordered implementation steps.",
        "contract_model_agent": "Designs explicit request, response, domain, and validation contracts.",
        "mock_adapter_agent": "Creates mock-only external participant adapters and prevents live integrations.",
        "service_logic_agent": "Implements deterministic workflow logic from architecture and module design.",
        "test_generation_agent": "Generates happy-path, negative-path, boundary, and governance tests.",
        "security_review_agent": "Reviews secrets, unsafe inputs, privacy boundaries, and false claims.",
        "observability_agent": "Adds request/evidence correlation and structured debug visibility.",
        "documentation_agent": "Produces beginner-readable README, debug guide, and mock-boundary docs.",
        "validation_agent": "Runs deterministic validators and summarizes failures.",
        "release_readiness_agent": "Checks gates, traceability, restore point readiness, and human approval.",
    }

    roles: list[dict[str, Any]] = []
    for role_id in AGENT_ROLE_IDS:
        roles.append(
            {
                "role_id": role_id,
                "description": role_descriptions[role_id],
                "runtime_mode": "deterministic_shadow_first",
                "allowed_tools": list(TOOL_IDS),
                "must_read": [
                    "phase10_3/generation_input_manifest.json",
                    "phase10_3/code_generation_readiness_gate.json",
                    "phase10_3/agent_execution_contract.md",
                    "phase10_3/implementation_guardrails.md",
                    "phase10_2/sdlc_best_practice_policy.md",
                    "phase10_1/source_usage_policy.md",
                ],
                "must_output": [
                    "agent_decision",
                    "proposed_actions",
                    "validation_expectations",
                    "honesty_labels",
                ],
                "required_labels": [
                    "MOCK_BOUNDARY",
                    "DETERMINISTIC_VALIDATION_REQUIRED",
                    "HUMAN_APPROVAL_REQUIRED",
                ],
            }
        )
    return roles


def _tool_contracts() -> list[dict[str, Any]]:
    return [
        {
            "tool_id": "read_governance_artifact",
            "purpose": "Read approved lifecycle and governance artifacts.",
            "side_effect_level": "read_only",
            "human_approval_required": False,
            "allowed": True,
        },
        {
            "tool_id": "read_prompt",
            "purpose": "Read the role-specific agent prompt.",
            "side_effect_level": "read_only",
            "human_approval_required": False,
            "allowed": True,
        },
        {
            "tool_id": "propose_file_plan",
            "purpose": "Propose files to create or modify before writing patches.",
            "side_effect_level": "proposal_only",
            "human_approval_required": False,
            "allowed": True,
        },
        {
            "tool_id": "propose_patch",
            "purpose": "Propose code or documentation patch content for deterministic review.",
            "side_effect_level": "proposal_only",
            "human_approval_required": True,
            "allowed": True,
        },
        {
            "tool_id": "run_deterministic_validator",
            "purpose": "Run validators, tests, lint, and type checks.",
            "side_effect_level": "read_and_execute_validation",
            "human_approval_required": False,
            "allowed": True,
        },
        {
            "tool_id": "record_decision",
            "purpose": "Append an auditable agent decision to the run manifest.",
            "side_effect_level": "workspace_write",
            "human_approval_required": False,
            "allowed": True,
        },
        {
            "tool_id": "request_human_approval",
            "purpose": "Pause before protected writes, merge, tag, or release actions.",
            "side_effect_level": "approval_gate",
            "human_approval_required": True,
            "allowed": True,
        },
        {
            "tool_id": "write_workspace_draft",
            "purpose": "Write draft files only under controlled generated workspace.",
            "side_effect_level": "workspace_write",
            "human_approval_required": True,
            "allowed": True,
            "forbidden_paths": [
                ".git",
                "main branch",
                "production configuration",
                "secret files",
                "live integration credentials",
            ],
        },
    ]


def _state_schema(app_id: str) -> dict[str, Any]:
    return {
        "artifact": "agent_state_schema.json",
        "app_id": app_id,
        "phase": "Phase 11A",
        "schema_name": "GovernedAgenticGenerationState",
        "required_fields": [
            "run_id",
            "app_id",
            "current_role",
            "readiness_gate_passed",
            "input_artifacts",
            "proposed_files",
            "decisions",
            "validation_results",
            "human_approval_status",
            "honesty_labels",
        ],
        "field_rules": {
            "readiness_gate_passed": "Must be true before Phase 11B generation.",
            "proposed_files": "Must remain proposals until deterministic validation and human approval.",
            "human_approval_status": "Required for protected writes, merges, tags, pushes, and release milestones.",
            "honesty_labels": "Must preserve required source, mock, synthetic, and validation labels.",
        },
        "required_labels": list(REQUIRED_LABELS),
    }


def _execution_policy(app_id: str) -> str:
    return f"""
# Phase 11A Agent Execution Policy — {app_id}

## Purpose

Phase 11A creates the governed agentic code-generation harness. It does not yet
generate the final application implementation.

## Runtime policy

- Agents may read approved governance artifacts.
- Agents may propose file plans and patches.
- Agents may write only draft workspace artifacts after approval.
- Agents may not commit, merge, tag, push, or alter protected branches.
- Agents may not bypass deterministic validators.
- Agents may not introduce live bank, NPCI, RBI, PSP, customer, payment,
  ledger, notification, reconciliation, or ODR integrations.
- Agents may not use real customer data.
- Agents may not make certification, production-compliance, or legal-advice claims.

## Required labels

- MOCK_BOUNDARY
- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_DATA
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED
- VERSION_SPECIFIC_REVIEW_REQUIRED
- HUMAN_APPROVAL_REQUIRED
- DETERMINISTIC_VALIDATION_REQUIRED

## Agentic principle

Agents generate proposals. Deterministic validators judge. Humans approve
protected changes. Git stores restore points.
"""


def _prompt_registry(app_id: str) -> dict[str, Any]:
    return {
        "artifact": "agent_prompt_registry.json",
        "app_id": app_id,
        "phase": "Phase 11A",
        "prompt_dir": "prompts/phase11a",
        "prompts": [
            {
                "role_id": role_id,
                "prompt_file": f"prompts/phase11a/{prompt_file}",
                "must_follow_execution_policy": True,
                "must_preserve_mock_boundary": True,
                "must_use_deterministic_validation": True,
            }
            for role_id, prompt_file in zip(AGENT_ROLE_IDS, PROMPT_FILES, strict=True)
        ],
    }


def _shadow_run(app_id: str) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for step_number, role_id in enumerate(AGENT_ROLE_IDS, start=1):
        decisions.append(
            {
                "step": step_number,
                "role_id": role_id,
                "mode": "deterministic_shadow",
                "decision": "Prepared governed proposal contract; no implementation files written.",
                "tools_used": [
                    "read_governance_artifact",
                    "read_prompt",
                    "record_decision",
                ],
                "blocked_tools": [
                    "git_commit",
                    "git_push",
                    "live_payment_call",
                    "secret_read",
                ],
                "honesty_labels": [
                    "MOCK_BOUNDARY",
                    "DETERMINISTIC_VALIDATION_REQUIRED",
                    "HUMAN_APPROVAL_REQUIRED",
                ],
            }
        )

    return {
        "artifact": "agent_deterministic_shadow_run.json",
        "app_id": app_id,
        "phase": "Phase 11A",
        "run_mode": "deterministic_shadow",
        "llm_calls_made": 0,
        "network_calls_made": 0,
        "implementation_files_written": 0,
        "decisions": decisions,
    }


def _generation_plan(app_id: str) -> dict[str, Any]:
    return {
        "artifact": "proposed_generation_plan.json",
        "app_id": app_id,
        "phase": "Phase 11A",
        "phase11b_goal": "Use governed agents to generate the first mock application skeleton.",
        "planned_output_root": (
            f"workspace/factory_generated/{app_id}/generated_application/phase11b"
        ),
        "planned_sequence": [
            "implementation_planner_agent",
            "contract_model_agent",
            "mock_adapter_agent",
            "service_logic_agent",
            "test_generation_agent",
            "security_review_agent",
            "observability_agent",
            "documentation_agent",
            "validation_agent",
            "release_readiness_agent",
        ],
        "phase11b_file_plan": [
            "README.md",
            "generated_app_manifest.json",
            "traceability_to_phase10.json",
            "src/upi_dispute_resolution_app/models.py",
            "src/upi_dispute_resolution_app/mock_adapters.py",
            "src/upi_dispute_resolution_app/service.py",
            "src/upi_dispute_resolution_app/api.py",
            "tests/test_service.py",
            "docs/debug_guide.md",
            "docs/mock_boundary.md",
            "phase11b_validation_report.json",
        ],
        "approval_required_before_write": True,
        "approval_required_before_commit": True,
        "deterministic_validation_required": True,
    }


def _phase11b_entry_criteria(app_id: str) -> str:
    return f"""
# Phase 11B Entry Criteria — {app_id}

Phase 11B may start only when:

- Phase 10.3 readiness passed.
- Phase 11A validation passed.
- Agent role catalog contains all required roles.
- Tool contracts are explicit and fail closed.
- Human approval is required for protected writes.
- Deterministic validation is required before commit or release.
- Mock boundary is preserved.
- No live payment integration is present.
- No certification, production-compliance, or legal-advice claim is present.
- The agentic run can be replayed or audited from manifests.

Phase 11B should be the first agent-generated mock application skeleton.
"""


def _manifest(app_id: str, phase10_3_dir: Path) -> dict[str, Any]:
    ready, readiness_report = _phase10_3_ready(phase10_3_dir)
    return {
        "artifact": "agentic_generation_harness_manifest.json",
        "app_id": app_id,
        "phase": "Phase 11A",
        "purpose": "Prepare governed agentic code-generation harness before implementation generation.",
        "phase10_3_readiness_passed": ready,
        "phase10_3_dir": str(phase10_3_dir),
        "phase10_3_report_summary": {
            "passed": readiness_report.get("passed"),
            "errors": readiness_report.get("errors", []),
            "warnings": readiness_report.get("warnings", []),
        },
        "runtime_modes": [
            {
                "mode": "deterministic_shadow",
                "default": True,
                "requires_llm": False,
                "requires_network": False,
            },
            {
                "mode": "langgraph_agentic",
                "default": False,
                "requires_llm": True,
                "requires_network": True,
                "status": "future_enabled_after_configuration",
            },
        ],
        "runtime_candidates": [
            {
                "name": "LangGraph",
                "source_status": "OFFICIAL_DOC_REFERENCE_CANDIDATE",
                "usage": "Stateful multi-agent orchestration candidate.",
            },
            {
                "name": "LangChain",
                "source_status": "OFFICIAL_DOC_REFERENCE_CANDIDATE",
                "usage": "Agent/tool abstraction candidate.",
            },
            {
                "name": "OpenAI API",
                "source_status": "OFFICIAL_DOC_REFERENCE_CANDIDATE",
                "usage": "Preferred LLM provider candidate when configured.",
            },
        ],
        "required_labels": list(REQUIRED_LABELS),
        "no_direct_commit_by_agents": True,
        "human_approval_required": True,
        "deterministic_validation_required": True,
    }


def generate_phase11a_artifacts(
    output_dir: Path,
    app_id: str = "upi_dispute_resolution",
    phase10_3_dir: Path | None = None,
) -> list[Path]:
    if phase10_3_dir is None:
        phase10_3_dir = Path(
            f"workspace/factory_generated/{app_id}/lifecycle_artifacts/phase10_3"
        )

    ready, readiness_report = _phase10_3_ready(phase10_3_dir)
    if not ready:
        raise ValueError(
            "Phase 11A generation blocked because Phase 10.3 readiness failed: "
            f"{readiness_report.get('errors', [])}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    payloads: dict[str, dict[str, Any] | str] = {
        "agentic_generation_harness_manifest.json": _manifest(app_id, phase10_3_dir),
        "agent_role_catalog.json": {
            "artifact": "agent_role_catalog.json",
            "app_id": app_id,
            "phase": "Phase 11A",
            "roles": _agent_roles(),
        },
        "agent_tool_contracts.json": {
            "artifact": "agent_tool_contracts.json",
            "app_id": app_id,
            "phase": "Phase 11A",
            "tools": _tool_contracts(),
        },
        "agent_state_schema.json": _state_schema(app_id),
        "agent_execution_policy.md": _execution_policy(app_id),
        "agent_prompt_registry.json": _prompt_registry(app_id),
        "agent_deterministic_shadow_run.json": _shadow_run(app_id),
        "proposed_generation_plan.json": _generation_plan(app_id),
        "phase11b_entry_criteria.md": _phase11b_entry_criteria(app_id),
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "phase11a_validation_report.json":
            continue
        target = output_dir / filename
        payload = payloads[filename]
        if isinstance(payload, dict):
            _write_json(target, payload)
        else:
            _write_markdown(target, payload)
        written.append(target)

    report = validate_phase11a_artifacts(output_dir, phase10_3_dir=phase10_3_dir)
    report_path = output_dir / "phase11a_validation_report.json"
    _write_json(report_path, report)
    written.append(report_path)

    return written


def _safe_claim_line(line: str) -> bool:
    normalized = f" {line.strip().lower()} "
    safe_markers = (
        " not ",
        " no ",
        " never ",
        " may not ",
        " must not ",
        " do not ",
        " forbidden ",
        " prohibited ",
        " entry criteria ",
        " no_",
        "legal-advice",
    )
    return any(marker in normalized for marker in safe_markers)


def validate_phase11a_artifacts(
    output_dir: Path,
    phase10_3_dir: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_artifacts: list[str] = []

    if phase10_3_dir is None:
        phase10_3_dir = Path(
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10_3"
        )

    ready, readiness_report = _phase10_3_ready(phase10_3_dir)
    if not ready:
        errors.append(
            "Phase 10.3 readiness validation failed: "
            f"{readiness_report.get('errors', [])}"
        )

    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"Missing Phase 11A artifact: {filename}")
        else:
            checked_artifacts.append(filename)

    manifest = _load_json(output_dir / "agentic_generation_harness_manifest.json", errors)
    role_catalog = _load_json(output_dir / "agent_role_catalog.json", errors)
    tool_contracts = _load_json(output_dir / "agent_tool_contracts.json", errors)
    state_schema = _load_json(output_dir / "agent_state_schema.json", errors)
    prompt_registry = _load_json(output_dir / "agent_prompt_registry.json", errors)
    shadow_run = _load_json(output_dir / "agent_deterministic_shadow_run.json", errors)
    generation_plan = _load_json(output_dir / "proposed_generation_plan.json", errors)

    text_parts: list[str] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "phase11a_validation_report.json":
            continue
        path = output_dir / filename
        if path.exists():
            text_parts.append(path.read_text(encoding="utf-8"))
    combined_text = "\n".join(text_parts)

    for label in REQUIRED_LABELS:
        if label not in combined_text:
            errors.append(f"Missing required Phase 11A label: {label}")

    for line_number, line in enumerate(combined_text.splitlines(), start=1):
        for claim in FORBIDDEN_CLAIMS:
            if claim.lower() in line.lower() and not _safe_claim_line(line):
                errors.append(
                    "Forbidden Phase 11A false claim found: "
                    f"{claim} near combined line {line_number}: {line.strip()}"
                )

    if manifest:
        if manifest.get("phase10_3_readiness_passed") is not True:
            errors.append("Harness manifest does not confirm Phase 10.3 readiness.")
        if manifest.get("no_direct_commit_by_agents") is not True:
            errors.append("Harness manifest must prohibit direct commits by agents.")
        if manifest.get("human_approval_required") is not True:
            errors.append("Harness manifest must require human approval.")
        if manifest.get("deterministic_validation_required") is not True:
            errors.append("Harness manifest must require deterministic validation.")

    if role_catalog:
        roles = role_catalog.get("roles", [])
        role_ids = [
            role.get("role_id")
            for role in roles
            if isinstance(role, dict) and isinstance(role.get("role_id"), str)
        ]
        for role_id in AGENT_ROLE_IDS:
            if role_id not in role_ids:
                errors.append(f"Missing agent role: {role_id}")

    if tool_contracts:
        tools = tool_contracts.get("tools", [])
        tool_ids = [
            tool.get("tool_id")
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("tool_id"), str)
        ]
        for tool_id in TOOL_IDS:
            if tool_id not in tool_ids:
                errors.append(f"Missing tool contract: {tool_id}")

        for tool in tools if isinstance(tools, list) else []:
            if not isinstance(tool, dict):
                errors.append("Each tool contract must be an object.")
                continue
            if tool.get("tool_id") in {"propose_patch", "write_workspace_draft"}:
                if tool.get("human_approval_required") is not True:
                    errors.append(
                        f"Protected tool must require human approval: {tool.get('tool_id')}"
                    )

    if state_schema:
        required_fields = state_schema.get("required_fields", [])
        for field in ("run_id", "current_role", "human_approval_status"):
            if field not in required_fields:
                errors.append(f"State schema missing required field: {field}")

    if prompt_registry:
        prompts = prompt_registry.get("prompts", [])
        if not isinstance(prompts, list) or len(prompts) != len(AGENT_ROLE_IDS):
            errors.append("Prompt registry must contain one prompt per role.")

    if shadow_run:
        if shadow_run.get("llm_calls_made") != 0:
            errors.append("Deterministic shadow run must not make LLM calls.")
        if shadow_run.get("network_calls_made") != 0:
            errors.append("Deterministic shadow run must not make network calls.")
        if shadow_run.get("implementation_files_written") != 0:
            errors.append("Phase 11A must not write implementation files.")

    if generation_plan:
        if generation_plan.get("approval_required_before_write") is not True:
            errors.append("Generation plan must require approval before write.")
        if generation_plan.get("deterministic_validation_required") is not True:
            errors.append("Generation plan must require deterministic validation.")

    if "MISSING_OFFICIAL_SOURCE" in combined_text:
        warnings.append(
            "Phase 11A is ready for governed agentic generation harness use. "
            "Unsupported live regulatory, economic, and technology values remain labelled."
        )

    return {
        "artifact": "phase11a_validation_report.json",
        "phase": "Phase 11A",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_agent_roles": list(AGENT_ROLE_IDS),
        "checked_tool_contracts": list(TOOL_IDS),
        "checked_required_labels": list(REQUIRED_LABELS),
    }
