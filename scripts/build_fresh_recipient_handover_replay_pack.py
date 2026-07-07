#!/usr/bin/env python3
"""Build a fresh-recipient handover replay and safe self-healing pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.build_human_approved_application_engineering_command_pack import (  # noqa: E402
    READY as COMMAND_READY,
    build_human_approved_command_pack,
)
from scripts.propose_factory_self_engineering_improvements import (  # noqa: E402
    build_factory_self_engineering_proposal_pack,
    validate_factory_self_engineering_proposal_pack,
)


APP_ID = "upi_dispute_resolution"
READY = "FRESH_RECIPIENT_REPLAY_PACK_READY"
BLOCKED = "FRESH_RECIPIENT_REPLAY_PACK_BLOCKED_BY_COMMAND_PACK"

REPLAY_ITEMS: tuple[str, ...] = (
    "command_pack_ready",
    "fresh_clone_bootstrap_steps_documented",
    "recipient_validation_commands_documented",
    "evidence_locations_documented",
    "self_healing_diagnostics_present",
    "self_engineering_proposals_present",
    "rollback_guidance_documented",
    "human_approval_boundaries_documented",
    "destructive_actions_remain_blocked",
)


@dataclass(frozen=True)
class ReplayItem:
    """One fresh-recipient replay item."""

    name: str
    satisfied: bool
    evidence: str

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence": self.evidence,
            "name": self.name,
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True)
class SelfHealingDiagnostic:
    """One safe self-healing diagnostic."""

    diagnostic_id: str
    category: str
    status: str
    auto_apply_allowed: bool
    human_approval_required: bool
    rollback_required: bool
    evidence: str

    def to_dict(self) -> dict[str, object]:
        return {
            "auto_apply_allowed": self.auto_apply_allowed,
            "category": self.category,
            "diagnostic_id": self.diagnostic_id,
            "evidence": self.evidence,
            "human_approval_required": self.human_approval_required,
            "rollback_required": self.rollback_required,
            "status": self.status,
        }


@dataclass(frozen=True)
class FreshRecipientReplayPack:
    """Fresh-recipient handover replay pack."""

    app_id: str
    replay_status: str
    preferred_term: str
    project_root: str
    command_pack_ready: bool
    self_engineering_proposals_valid: bool
    replay_digest: str
    self_engineering_proposal_digest: str
    replay_items: tuple[ReplayItem, ...]
    self_healing_diagnostics: tuple[SelfHealingDiagnostic, ...]
    recommended_recipient_commands: tuple[str, ...]
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    destructive_execution_performed: bool
    factory_self_healing_repair_applied: bool
    factory_self_modification_applied: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.replay_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "command_pack_ready": self.command_pack_ready,
            "destructive_execution_performed": self.destructive_execution_performed,
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_healing_repair_applied": self.factory_self_healing_repair_applied,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "recommended_recipient_commands": list(self.recommended_recipient_commands),
            "replay_digest": self.replay_digest,
            "replay_items": [item.to_dict() for item in self.replay_items],
            "replay_status": self.replay_status,
            "schema_version": "fresh-recipient-handover-replay-pack.v1",
            "self_engineering_proposal_digest": self.self_engineering_proposal_digest,
            "self_engineering_proposals_valid": self.self_engineering_proposals_valid,
            "self_healing_diagnostics": [
                diagnostic.to_dict() for diagnostic in self.self_healing_diagnostics
            ],
        }


def _build_diagnostics(project_root: Path) -> tuple[SelfHealingDiagnostic, ...]:
    checks: tuple[tuple[str, str, Path], ...] = (
        ("DIAG-001", "docs", Path("docs")),
        ("DIAG-002", "policies", Path("policies")),
        ("DIAG-003", "tests", Path("tests")),
        ("DIAG-004", "scripts", Path("scripts")),
        (
            "DIAG-005",
            "phase13ap_audit",
            Path(
                "workspace/factory_generated/upi_dispute_resolution/"
                "lifecycle_artifacts/phase13ap/"
                "human_approved_application_engineering_command_pack_audit.json"
            ),
        ),
    )

    diagnostics: list[SelfHealingDiagnostic] = []
    for diagnostic_id, category, relative_path in checks:
        exists = (project_root / relative_path).exists()
        diagnostics.append(
            SelfHealingDiagnostic(
                diagnostic_id=diagnostic_id,
                category=category,
                status="PRESENT" if exists else "MISSING_REPAIR_PROPOSAL_REQUIRED",
                auto_apply_allowed=False,
                human_approval_required=True,
                rollback_required=True,
                evidence=str(relative_path),
            )
        )
    return tuple(diagnostics)


def _build_replay_items(
    command_ready: bool,
    proposals_valid: bool,
    diagnostics: tuple[SelfHealingDiagnostic, ...],
) -> tuple[ReplayItem, ...]:
    diagnostics_present = len(diagnostics) >= 5
    values: dict[str, tuple[bool, str]] = {
        "command_pack_ready": (
            command_ready,
            "Phase 13AP human-approved command pack status.",
        ),
        "fresh_clone_bootstrap_steps_documented": (
            True,
            "Recipient commands include clone, venv, dependency, validation, and pytest steps.",
        ),
        "recipient_validation_commands_documented": (
            True,
            "Recipient commands include validator, targeted tests, Ruff, MyPy, and full pytest.",
        ),
        "evidence_locations_documented": (
            True,
            "Lifecycle artifact locations are included in the replay pack.",
        ),
        "self_healing_diagnostics_present": (
            diagnostics_present,
            "Diagnostic checks are proposal-only and do not apply repairs.",
        ),
        "self_engineering_proposals_present": (
            proposals_valid,
            "Phase 13AP self-engineering proposals are valid and proposal-only.",
        ),
        "rollback_guidance_documented": (
            True,
            "Rollback remains git-backed and human-controlled.",
        ),
        "human_approval_boundaries_documented": (
            True,
            "Human approval boundaries are preserved for delete, overwrite, self-modification, merge, tag, and release.",
        ),
        "destructive_actions_remain_blocked": (
            True,
            "No destructive actions are performed in Phase 13AQ.",
        ),
    }
    return tuple(
        ReplayItem(name=name, satisfied=values[name][0], evidence=values[name][1])
        for name in REPLAY_ITEMS
    )


def _digest_payload(items: tuple[ReplayItem, ...], diagnostics: tuple[SelfHealingDiagnostic, ...]) -> str:
    payload = {
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
        "items": [item.to_dict() for item in items],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_fresh_recipient_replay_pack(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> FreshRecipientReplayPack:
    """Build a fresh-recipient handover replay pack."""

    root = project_root.resolve()
    command_pack = build_human_approved_command_pack(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    self_engineering_pack = build_factory_self_engineering_proposal_pack(root)
    self_engineering_valid = not validate_factory_self_engineering_proposal_pack(self_engineering_pack)
    command_ready = command_pack.command_pack_status == COMMAND_READY

    diagnostics = _build_diagnostics(root)
    items = _build_replay_items(command_ready, self_engineering_valid, diagnostics)
    all_items_ready = all(item.satisfied for item in items)
    status = READY if command_ready and all_items_ready else BLOCKED

    commands = (
        "git clone <repo-url>",
        "cd upi_dispute_resolution_factory",
        "python3.10 -m venv .venv",
        "source .venv/bin/activate",
        "python -m pip install -U pip",
        "python -m pip install -e '.[dev]'",
        "python scripts/validate_phase13ap_command_pack.py",
        "python scripts/validate_phase13aq_fresh_recipient_replay.py",
        "python -m pytest tests/test_phase13ap_command_pack.py tests/test_phase13aq_fresh_recipient_replay.py",
        "python -m ruff check .",
        "python -m mypy .",
        "python -m pytest",
    )

    reasons: list[str] = list(command_pack.reasons)
    if status == READY:
        reasons.append("Fresh-recipient replay pack is ready in local non-destructive mode.")
    else:
        reasons.append("Fresh-recipient replay pack is blocked until command pack readiness is satisfied.")

    return FreshRecipientReplayPack(
        app_id=APP_ID,
        replay_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        command_pack_ready=command_ready,
        self_engineering_proposals_valid=self_engineering_valid,
        replay_digest=_digest_payload(items, diagnostics),
        self_engineering_proposal_digest=self_engineering_pack.proposal_digest,
        replay_items=items,
        self_healing_diagnostics=diagnostics,
        recommended_recipient_commands=commands,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        destructive_execution_performed=False,
        factory_self_healing_repair_applied=False,
        factory_self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=tuple(reasons),
    )


def validate_fresh_recipient_replay_pack(pack: FreshRecipientReplayPack) -> list[str]:
    """Validate fresh-recipient replay pack safety properties."""

    failures: list[str] = []
    if pack.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if pack.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if pack.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if pack.destructive_execution_performed:
        failures.append("Phase 13AQ must not perform destructive execution")
    if pack.factory_self_healing_repair_applied:
        failures.append("Phase 13AQ must not apply self-healing repairs")
    if pack.factory_self_modification_applied:
        failures.append("Phase 13AQ must not apply factory self-modification")
    if pack.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if pack.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if pack.auto_merge_performed or pack.auto_tag_performed or pack.auto_release_performed:
        failures.append("Phase 13AQ must not merge, tag, or release")
    if len(pack.replay_digest) != 64:
        failures.append("Replay digest must be SHA-256 hex")
    if len(pack.self_engineering_proposal_digest) != 64:
        failures.append("Self-engineering proposal digest must be SHA-256 hex")
    item_names = {item.name for item in pack.replay_items}
    if item_names != set(REPLAY_ITEMS):
        failures.append("Replay pack must include every replay item")
    if not pack.self_healing_diagnostics:
        failures.append("Self-healing diagnostics are required")
    for diagnostic in pack.self_healing_diagnostics:
        if diagnostic.auto_apply_allowed:
            failures.append(f"{diagnostic.diagnostic_id} must not be auto-applied")
        if not diagnostic.human_approval_required:
            failures.append(f"{diagnostic.diagnostic_id} must require human approval")
        if not diagnostic.rollback_required:
            failures.append(f"{diagnostic.diagnostic_id} must require rollback planning")
    return failures


def write_fresh_recipient_replay_pack(pack: FreshRecipientReplayPack, audit_out: Path) -> None:
    """Write deterministic JSON audit for a fresh-recipient replay pack."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fresh-recipient handover replay pack.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = build_fresh_recipient_replay_pack(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_fresh_recipient_replay_pack(pack, args.audit_out)

    print(json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_fresh_recipient_replay_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if pack.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
