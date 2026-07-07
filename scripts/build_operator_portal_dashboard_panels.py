#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


APP_ID = "upi_dispute_resolution"
READY = "OPERATOR_PORTAL_DASHBOARDS_READY"

PANEL_IDS: tuple[str, ...] = (
    "evidence_audit",
    "standards_controls",
    "self_healing",
    "agentic_threats",
    "requirement_intake",
    "handover_replay",
    "generated_application",
)

BLOCKED_ACTIONS: tuple[str, ...] = (
    "delete_real_generated_application",
    "overwrite_real_generated_application",
    "execute_arbitrary_shell_command",
    "write_requirement_package_without_human_terminal_command",
    "run_application_generation",
    "apply_factory_self_modification",
    "call_live_llm_provider",
    "call_external_system",
    "auto_merge",
    "auto_tag",
    "auto_release",
)


@dataclass(frozen=True)
class DashboardPanel:
    panel_id: str
    title: str
    status: str
    summary: str
    evidence_paths: tuple[str, ...]
    validator_paths: tuple[str, ...]
    read_only: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_paths": list(self.evidence_paths),
            "panel_id": self.panel_id,
            "read_only": self.read_only,
            "status": self.status,
            "summary": self.summary,
            "title": self.title,
            "validator_paths": list(self.validator_paths),
        }


def _present(root: Path, relative_path: str) -> bool:
    return (root / relative_path).exists()


def _status_for(root: Path, evidence_paths: tuple[str, ...], validator_paths: tuple[str, ...]) -> str:
    evidence_present = all(_present(root, path) for path in evidence_paths)
    validators_present = all(_present(root, path) for path in validator_paths)
    if evidence_present and validators_present:
        return "READY"
    if evidence_present or validators_present:
        return "PARTIAL"
    return "MISSING"


def _panel(
    root: Path,
    panel_id: str,
    title: str,
    summary: str,
    evidence_paths: tuple[str, ...],
    validator_paths: tuple[str, ...],
) -> DashboardPanel:
    return DashboardPanel(
        panel_id=panel_id,
        title=title,
        status=_status_for(root, evidence_paths, validator_paths),
        summary=summary,
        evidence_paths=evidence_paths,
        validator_paths=validator_paths,
        read_only=True,
    )


def build_operator_portal_dashboard_panels(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    panels = (
        _panel(
            root,
            "evidence_audit",
            "Evidence and Audit",
            "Lifecycle artifacts and audit JSON availability.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13aq/fresh_recipient_handover_replay_audit.json",
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13aw/local_operator_portal_audit.json",
            ),
            (
                "scripts/validate_phase13aq_fresh_recipient_replay.py",
                "scripts/validate_phase13aw_operator_portal.py",
            ),
        ),
        _panel(
            root,
            "standards_controls",
            "Standards Controls",
            "Local industry standards control matrix and validator status.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            ),
            ("scripts/validate_phase13as_standards_control_matrix.py",),
        ),
        _panel(
            root,
            "self_healing",
            "Self-Healing",
            "Governed self-healing repair catalog and low-risk sandbox repair status.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ar/governed_self_healing_repair_catalog_audit.json",
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13au/low_risk_autonomous_repair_audit.json",
            ),
            (
                "scripts/validate_phase13ar_self_healing_repair_catalog.py",
                "scripts/validate_phase13au_low_risk_repair_applier.py",
            ),
        ),
        _panel(
            root,
            "agentic_threats",
            "Agentic AI Threats",
            "Local deterministic LLM, tool, RAG, and agency threat-test status.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13av/local_agentic_ai_threat_test_audit.json",
            ),
            ("scripts/validate_phase13av_agentic_ai_threat_tests.py",),
        ),
        _panel(
            root,
            "requirement_intake",
            "Requirement Intake",
            "Guided requirement intake preview UI and validator status.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ax/guided_requirement_intake_ui_audit.json",
            ),
            ("scripts/validate_phase13ax_requirement_intake_ui.py",),
        ),
        _panel(
            root,
            "handover_replay",
            "Handover Replay",
            "Fresh-recipient handover replay and local recipient usability evidence.",
            (
                "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13aq/fresh_recipient_handover_replay_audit.json",
            ),
            ("scripts/validate_phase13aq_fresh_recipient_replay.py",),
        ),
        _panel(
            root,
            "generated_application",
            "Generated Application",
            "Primary generated app presence and generated tests status.",
            (
                "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py",
                "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_workflow.py",
            ),
            (
                "tests/test_phase13b_generated_application.py",
                "tests/test_phase13w_governed_multi_capability_application_assembly.py",
            ),
        ),
    )
    ready = all(panel.read_only for panel in panels)
    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_exposed_from_ui": False,
        "auto_merge_enabled_from_ui": False,
        "auto_release_enabled_from_ui": False,
        "auto_tag_enabled_from_ui": False,
        "blocked_actions": list(BLOCKED_ACTIONS),
        "external_system_calls_enabled": False,
        "live_provider_calls_enabled": False,
        "panels": [panel.to_dict() for panel in panels],
        "read_only_dashboards": True,
        "ready": ready,
        "schema_version": "operator-portal-dashboard-panels.v1",
        "status": READY if ready else "OPERATOR_PORTAL_DASHBOARDS_BLOCKED",
    }


def validate_operator_portal_dashboard_panels(status: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if status.get("schema_version") != "operator-portal-dashboard-panels.v1":
        failures.append("Invalid dashboard panel schema")
    if status.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if status.get("read_only_dashboards") is not True:
        failures.append("Dashboards must be read-only")
    for key in [
        "arbitrary_shell_execution_exposed_from_ui",
        "auto_merge_enabled_from_ui",
        "auto_tag_enabled_from_ui",
        "auto_release_enabled_from_ui",
        "external_system_calls_enabled",
        "live_provider_calls_enabled",
    ]:
        if status.get(key) is not False:
            failures.append(f"{key} must be false")
    panel_values = status.get("panels")
    if not isinstance(panel_values, list):
        failures.append("Dashboard panels must be a list")
        return failures
    panel_ids: set[str] = set()
    for item in panel_values:
        if not isinstance(item, dict):
            failures.append("Each panel must be an object")
            continue
        panel_id = item.get("panel_id")
        if isinstance(panel_id, str):
            panel_ids.add(panel_id)
        if item.get("read_only") is not True:
            failures.append(f"Panel {panel_id} must be read-only")
    if panel_ids != set(PANEL_IDS):
        failures.append("Dashboard panels must cover all required panel IDs")
    blocked = status.get("blocked_actions")
    if not isinstance(blocked, list):
        failures.append("Blocked actions must be listed")
    else:
        for action in BLOCKED_ACTIONS:
            if action not in blocked:
                failures.append(f"Missing blocked action: {action}")
    return failures


def write_operator_portal_dashboard_panels(status: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operator portal dashboard panels.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()
    status = build_operator_portal_dashboard_panels(args.project_root)
    if args.audit_out is not None:
        write_operator_portal_dashboard_panels(status, args.audit_out)
    print(json.dumps(status, indent=2, sort_keys=True))
    failures = validate_operator_portal_dashboard_panels(status)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
