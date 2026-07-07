#!/usr/bin/env python3
# Build deterministic guided requirement-intake preview packages.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
READY = "GUIDED_REQUIREMENT_INTAKE_PREVIEW_READY"
BLOCKED = "GUIDED_REQUIREMENT_INTAKE_PREVIEW_BLOCKED"

REQUIRED_FIELDS: tuple[str, ...] = (
    "business_domain",
    "application_name",
    "capabilities",
    "regulatory_constraints",
    "mock_ecosystem",
    "data_sensitivity",
    "llm_mode",
    "approval_mode",
)

PREVIEW_SECTIONS: tuple[str, ...] = (
    "normalized_requirement",
    "risk_classification",
    "governance_controls",
    "mock_boundary",
    "evidence_plan",
    "blocked_actions",
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
class RequirementIntakePreview:
    app_id: str
    preview_status: str
    preferred_term: str
    preview_only: bool
    normalized_requirement: dict[str, object]
    risk_classification: dict[str, object]
    governance_controls: tuple[str, ...]
    mock_boundary: dict[str, object]
    evidence_plan: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    digest: str
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    arbitrary_shell_execution_exposed_from_ui: bool
    requirement_package_written_from_ui: bool
    application_generation_triggered_from_ui: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    factory_self_modification_applied: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.preview_status == READY

    def to_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "application_generation_triggered_from_ui": self.application_generation_triggered_from_ui,
            "arbitrary_shell_execution_exposed_from_ui": self.arbitrary_shell_execution_exposed_from_ui,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "blocked_actions": list(self.blocked_actions),
            "digest": self.digest,
            "evidence_plan": list(self.evidence_plan),
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "governance_controls": list(self.governance_controls),
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "mock_boundary": self.mock_boundary,
            "normalized_requirement": self.normalized_requirement,
            "preferred_term": self.preferred_term,
            "preview_only": self.preview_only,
            "preview_status": self.preview_status,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "requirement_package_written_from_ui": self.requirement_package_written_from_ui,
            "risk_classification": self.risk_classification,
            "schema_version": "guided-requirement-intake-preview.v1",
        }


def _clean_text(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:2000]


def _split_items(value: object) -> tuple[str, ...]:
    text = _clean_text(value)
    if not text:
        return ()
    return tuple(item.strip() for item in re.split(r"[,;\n]+", text) if item.strip())


def _classify_risk(data_sensitivity: str, llm_mode: str, approval_mode: str) -> dict[str, object]:
    sensitivity = data_sensitivity.lower()
    llm = llm_mode.lower()
    approval = approval_mode.lower()
    score = 1
    reasons: list[str] = ["local preview only"]
    if any(term in sensitivity for term in ["pii", "sensitive", "financial", "payment", "regulated"]):
        score += 2
        reasons.append("sensitive or regulated data indicated")
    if "live" in llm:
        score += 2
        reasons.append("live LLM mode requested")
    if "auto" in approval and "human" not in approval:
        score += 1
        reasons.append("automatic approval preference indicated")
    tier = "high" if score >= 5 else "medium" if score >= 3 else "low"
    return {
        "risk_score": score,
        "risk_tier": tier,
        "reasons": reasons,
        "human_approval_required": True,
    }


def _digest_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_requirement_intake_preview(raw_payload: dict[str, Any]) -> RequirementIntakePreview:
    normalized: dict[str, object] = {
        "business_domain": _clean_text(raw_payload.get("business_domain")),
        "application_name": _clean_text(raw_payload.get("application_name")),
        "capabilities": list(_split_items(raw_payload.get("capabilities"))),
        "regulatory_constraints": list(_split_items(raw_payload.get("regulatory_constraints"))),
        "mock_ecosystem": list(_split_items(raw_payload.get("mock_ecosystem"))),
        "data_sensitivity": _clean_text(raw_payload.get("data_sensitivity")),
        "llm_mode": _clean_text(raw_payload.get("llm_mode")),
        "approval_mode": _clean_text(raw_payload.get("approval_mode")),
    }
    missing = tuple(field for field in REQUIRED_FIELDS if not normalized[field])
    risk = _classify_risk(
        str(normalized["data_sensitivity"]),
        str(normalized["llm_mode"]),
        str(normalized["approval_mode"]),
    )
    controls = (
        "human_approval_required",
        "local_preview_only",
        "policy_validation_required",
        "evidence_plan_required",
        "mock_ecosystem_boundary_required",
        "generated_application_write_blocked_from_ui",
        "live_provider_call_blocked_from_ui",
        "external_system_call_blocked_from_ui",
    )
    mock_boundary = {
        "primary_generated_application_should_be_real_local_runnable": True,
        "external_ecosystem_integrations_should_remain_mocked": True,
        "mocked_systems": normalized["mock_ecosystem"],
    }
    evidence_plan = (
        "requirement_intake_preview_json",
        "policy_validation_result",
        "risk_classification_result",
        "mock_boundary_record",
        "human_approval_record_before_generation",
    )
    preview_payload: dict[str, object] = {
        "blocked_actions": list(BLOCKED_ACTIONS),
        "evidence_plan": list(evidence_plan),
        "governance_controls": list(controls),
        "mock_boundary": mock_boundary,
        "normalized_requirement": normalized,
        "risk_classification": risk,
    }
    status = READY if not missing else BLOCKED
    reasons = (
        ("Requirement intake preview is ready; no project mutation performed.",)
        if not missing
        else (f"Missing required fields: {', '.join(missing)}",)
    )
    return RequirementIntakePreview(
        app_id=APP_ID,
        preview_status=status,
        preferred_term="application engineering",
        preview_only=True,
        normalized_requirement=normalized,
        risk_classification=risk,
        governance_controls=controls,
        mock_boundary=mock_boundary,
        evidence_plan=evidence_plan,
        blocked_actions=BLOCKED_ACTIONS,
        digest=_digest_payload(preview_payload),
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        arbitrary_shell_execution_exposed_from_ui=False,
        requirement_package_written_from_ui=False,
        application_generation_triggered_from_ui=False,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        factory_self_modification_applied=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=reasons,
    )


def validate_requirement_intake_preview(preview: RequirementIntakePreview) -> list[str]:
    failures: list[str] = []
    if preview.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if not preview.preview_only:
        failures.append("Requirement intake UI must be preview-only in Phase 13AX")
    if preview.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if preview.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if preview.arbitrary_shell_execution_exposed_from_ui:
        failures.append("Arbitrary shell execution must not be exposed from UI")
    if preview.requirement_package_written_from_ui:
        failures.append("Requirement package must not be written from UI")
    if preview.application_generation_triggered_from_ui:
        failures.append("Generation must not be triggered from UI")
    if preview.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if preview.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if preview.factory_self_modification_applied:
        failures.append("Factory self-modification must not be applied")
    if preview.auto_merge_performed or preview.auto_tag_performed or preview.auto_release_performed:
        failures.append("Merge, tag, and release must not be automatic")
    if len(preview.digest) != 64:
        failures.append("Preview digest must be SHA-256 hex")
    preview_keys = set(preview.to_dict().keys())
    for section in PREVIEW_SECTIONS:
        if section not in preview_keys:
            failures.append(f"Missing preview section: {section}")
    for action in BLOCKED_ACTIONS:
        if action not in preview.blocked_actions:
            failures.append(f"Missing blocked action: {action}")
    return failures


def write_requirement_intake_preview(preview: RequirementIntakePreview, audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(preview.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_json:
        value = json.loads(args.payload_json)
        if not isinstance(value, dict):
            raise ValueError("--payload-json must be a JSON object")
        return dict(value)
    if args.payload_file:
        value = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("--payload-file must contain a JSON object")
        return dict(value)
    return {
        "business_domain": args.business_domain,
        "application_name": args.application_name,
        "capabilities": args.capabilities,
        "regulatory_constraints": args.regulatory_constraints,
        "mock_ecosystem": args.mock_ecosystem,
        "data_sensitivity": args.data_sensitivity,
        "llm_mode": args.llm_mode,
        "approval_mode": args.approval_mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build guided requirement intake preview.")
    parser.add_argument("--payload-json")
    parser.add_argument("--payload-file")
    parser.add_argument("--business-domain", default="")
    parser.add_argument("--application-name", default="")
    parser.add_argument("--capabilities", default="")
    parser.add_argument("--regulatory-constraints", default="")
    parser.add_argument("--mock-ecosystem", default="")
    parser.add_argument("--data-sensitivity", default="")
    parser.add_argument("--llm-mode", default="")
    parser.add_argument("--approval-mode", default="")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()
    preview = build_requirement_intake_preview(_load_payload(args))
    if args.audit_out is not None:
        write_requirement_intake_preview(preview, args.audit_out)
    print(json.dumps(preview.to_dict(), indent=2, sort_keys=True))
    failures = validate_requirement_intake_preview(preview)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0 if preview.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
