from __future__ import annotations

from .contracts import AgentDefinition, ToolDefinition


def default_agent_registry() -> list[AgentDefinition]:
    return [
        AgentDefinition(
            name="requirement_intake_agent",
            purpose="Convert business intent into structured requirements.",
            allowed_tools=("artifact_writer", "ledger_writer"),
            output_artifacts=("requirements_manifest.json",),
        ),
        AgentDefinition(
            name="upi_domain_policy_agent",
            purpose="Create UPI/domain-aware simulation constraints.",
            allowed_tools=("artifact_writer", "ledger_writer"),
            output_artifacts=("upi_domain_policy_matrix.json",),
        ),
        AgentDefinition(
            name="architecture_agent",
            purpose="Create architecture boundaries for local app and mock ecosystem.",
            allowed_tools=("artifact_writer", "ledger_writer"),
            output_artifacts=("architecture.md",),
        ),
        AgentDefinition(
            name="implementation_agent",
            purpose="Generate or update application artifacts under generated_application.",
            allowed_tools=("artifact_writer", "generated_app_writer", "ledger_writer"),
            output_artifacts=("generated_application",),
        ),
        AgentDefinition(
            name="test_validation_agent",
            purpose="Run deterministic validation and tests.",
            allowed_tools=("validator_runner", "ledger_writer"),
            output_artifacts=("validation_report.json",),
        ),
        AgentDefinition(
            name="audit_agent",
            purpose="Create independent post-generation audit findings.",
            allowed_tools=("artifact_writer", "ledger_writer"),
            output_artifacts=("audit_findings_register.json",),
        ),
        AgentDefinition(
            name="portal_agent",
            purpose="Update evidence-backed progress portal telemetry.",
            allowed_tools=("portal_generator", "ledger_writer"),
            output_artifacts=("factory_generation_progress_portal.html",),
        ),
        AgentDefinition(
            name="self_correction_agent",
            purpose="Triage every warning/error and apply governed remediation decisions.",
            allowed_tools=("self_correction_controller", "validator_runner", "ledger_writer"),
            output_artifacts=("self_correction_decisions.json",),
        ),
    ]


def default_tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="artifact_writer",
            purpose="Write governed docs and lifecycle artifacts.",
            destructive=False,
            requires_human_approval=False,
            allowed_paths=("docs", "workspace/factory_generated"),
        ),
        ToolDefinition(
            name="generated_app_writer",
            purpose="Write only inside resettable generated_application workspace.",
            destructive=False,
            requires_human_approval=False,
            allowed_paths=(
                "workspace/factory_generated/upi_dispute_resolution/generated_application",
            ),
        ),
        ToolDefinition(
            name="validator_runner",
            purpose="Run deterministic validators and tests.",
            destructive=False,
            requires_human_approval=False,
        ),
        ToolDefinition(
            name="portal_generator",
            purpose="Generate the local evidence-backed portal HTML.",
            destructive=False,
            requires_human_approval=False,
            allowed_paths=(
                "workspace/factory_generated/upi_dispute_resolution/audit_portal",
            ),
        ),
        ToolDefinition(
            name="git_release_tool",
            purpose="Commit, merge, tag, and push release state.",
            destructive=False,
            requires_human_approval=True,
        ),
        ToolDefinition(
            name="reset_generated_application",
            purpose="Delete and recreate generated_application with archive/manifest.",
            destructive=True,
            requires_human_approval=True,
            allowed_paths=(
                "workspace/factory_generated/upi_dispute_resolution/generated_application",
            ),
        ),
        ToolDefinition(
            name="self_correction_controller",
            purpose="Classify warnings/errors and choose governed remediation actions.",
            destructive=False,
            requires_human_approval=False,
        ),
    ]
