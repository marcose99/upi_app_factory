#!/usr/bin/env python3
"""Build the human-approved clean-slate application engineering command pack.

Phase 13AP is non-destructive. It prepares a command pack for a later separate
human-approved phase. It does not delete or overwrite the real generated
application and does not apply factory self-modifications.
"""

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


from scripts.assemble_final_clean_slate_application_engineering_readiness_pack import (  # noqa: E402
    READY as READINESS_READY,
    assemble_final_readiness_pack,
)
from scripts.propose_factory_self_engineering_improvements import (  # noqa: E402
    build_factory_self_engineering_proposal_pack,
    validate_factory_self_engineering_proposal_pack,
)


APP_ID = "upi_dispute_resolution"
READY = "COMMAND_PACK_READY_FOR_SEPARATE_HUMAN_APPROVED_EXECUTION"
BLOCKED = "COMMAND_PACK_BLOCKED_BY_FINAL_READINESS"

COMMAND_ITEMS: tuple[str, ...] = (
    "final_readiness_pack_ready",
    "backup_manifest_digest_present",
    "execution_package_digest_present",
    "approval_token_reference_present",
    "operator_confirmation_present",
    "future_real_execution_command_documented",
    "post_engineering_certification_required",
    "handoff_replay_required",
    "factory_self_engineering_proposals_validated",
    "destructive_actions_remain_blocked",
)


@dataclass(frozen=True)
class CommandPackItem:
    """One command pack item."""

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
class HumanApprovedCommandPack:
    """Human-approved clean-slate application engineering command pack."""

    app_id: str
    command_pack_status: str
    preferred_term: str
    project_root: str
    final_readiness_pack_ready: bool
    approval_token_present: bool
    operator_confirmation_present: bool
    backup_manifest_digest: str
    execution_package_digest: str
    self_engineering_proposal_digest: str
    command_pack_digest: str
    command_items: tuple[CommandPackItem, ...]
    future_real_execution_command: str
    destructive_actions_blocked_in_this_phase: bool
    factory_self_modification_applied: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    destructive_execution_performed: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.command_pack_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "approval_token_present": self.approval_token_present,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "backup_manifest_digest": self.backup_manifest_digest,
            "command_items": [item.to_dict() for item in self.command_items],
            "command_pack_digest": self.command_pack_digest,
            "command_pack_status": self.command_pack_status,
            "destructive_actions_blocked_in_this_phase": self.destructive_actions_blocked_in_this_phase,
            "destructive_execution_performed": self.destructive_execution_performed,
            "execution_package_digest": self.execution_package_digest,
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "final_readiness_pack_ready": self.final_readiness_pack_ready,
            "future_real_execution_command": self.future_real_execution_command,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "operator_confirmation_present": self.operator_confirmation_present,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "schema_version": "human-approved-application-engineering-command-pack.v1",
            "self_engineering_proposal_digest": self.self_engineering_proposal_digest,
        }


def _build_command_items(
    final_readiness_ready: bool,
    approval_token_present: bool,
    operator_confirmation_present: bool,
    backup_digest: str,
    execution_digest: str,
    self_proposal_validated: bool,
) -> tuple[CommandPackItem, ...]:
    values: dict[str, tuple[bool, str]] = {
        "final_readiness_pack_ready": (
            final_readiness_ready,
            "Phase 13AO final readiness pack status.",
        ),
        "backup_manifest_digest_present": (
            len(backup_digest) == 64,
            backup_digest,
        ),
        "execution_package_digest_present": (
            len(execution_digest) == 64,
            execution_digest,
        ),
        "approval_token_reference_present": (
            approval_token_present,
            "Approval token path supplied to command pack builder.",
        ),
        "operator_confirmation_present": (
            operator_confirmation_present,
            "Operator confirmation flag supplied to command pack builder.",
        ),
        "future_real_execution_command_documented": (
            True,
            "Future command is documented but not executed in Phase 13AP.",
        ),
        "post_engineering_certification_required": (
            True,
            "Post-engineering certification remains mandatory.",
        ),
        "handoff_replay_required": (
            True,
            "Handoff replay remains mandatory.",
        ),
        "factory_self_engineering_proposals_validated": (
            self_proposal_validated,
            "Factory self-engineering proposal pack validation status.",
        ),
        "destructive_actions_remain_blocked": (
            True,
            "Phase 13AP performs no delete, overwrite, live provider call, external call, merge, tag, release, or self-modification.",
        ),
    }
    return tuple(
        CommandPackItem(name=name, satisfied=values[name][0], evidence=values[name][1])
        for name in COMMAND_ITEMS
    )


def _digest_command_items(items: tuple[CommandPackItem, ...]) -> str:
    payload = [item.to_dict() for item in items]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_human_approved_command_pack(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> HumanApprovedCommandPack:
    """Build a non-destructive human-approved command pack."""

    root = project_root.resolve()
    readiness_pack = assemble_final_readiness_pack(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    self_engineering_pack = build_factory_self_engineering_proposal_pack(root)
    self_engineering_valid = not validate_factory_self_engineering_proposal_pack(self_engineering_pack)

    final_ready = readiness_pack.readiness_status == READINESS_READY
    command_items = _build_command_items(
        final_readiness_ready=final_ready,
        approval_token_present=approval_token is not None,
        operator_confirmation_present=operator_confirmation,
        backup_digest=readiness_pack.backup_manifest_digest,
        execution_digest=readiness_pack.execution_package_digest,
        self_proposal_validated=self_engineering_valid,
    )
    all_items_ready = all(item.satisfied for item in command_items)
    status = READY if final_ready and all_items_ready else BLOCKED

    future_command = (
        "A later separate phase may run the real clean-slate application engineering command "
        "only after fresh human approval, backup evidence, certification plan, and explicit operator confirmation."
    )

    reasons = list(readiness_pack.reasons)
    if status == READY:
        reasons.append("Command pack is ready for separate human-approved execution review; Phase 13AP remains non-destructive.")
    else:
        reasons.append("Command pack is blocked until final readiness and review inputs are complete.")

    return HumanApprovedCommandPack(
        app_id=APP_ID,
        command_pack_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        final_readiness_pack_ready=final_ready,
        approval_token_present=approval_token is not None,
        operator_confirmation_present=operator_confirmation,
        backup_manifest_digest=readiness_pack.backup_manifest_digest,
        execution_package_digest=readiness_pack.execution_package_digest,
        self_engineering_proposal_digest=self_engineering_pack.proposal_digest,
        command_pack_digest=_digest_command_items(command_items),
        command_items=command_items,
        future_real_execution_command=future_command,
        destructive_actions_blocked_in_this_phase=True,
        factory_self_modification_applied=False,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        destructive_execution_performed=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=tuple(reasons),
    )


def validate_human_approved_command_pack(pack: HumanApprovedCommandPack) -> list[str]:
    """Validate the command pack safety properties."""

    failures: list[str] = []
    if pack.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if pack.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if pack.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if pack.destructive_execution_performed:
        failures.append("Phase 13AP must not perform destructive execution")
    if pack.factory_self_modification_applied:
        failures.append("Phase 13AP must not apply factory self-modification")
    if pack.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if pack.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if pack.auto_merge_performed or pack.auto_tag_performed or pack.auto_release_performed:
        failures.append("Phase 13AP must not merge, tag, or release")
    if len(pack.command_pack_digest) != 64:
        failures.append("Command pack digest must be SHA-256 hex")
    if len(pack.self_engineering_proposal_digest) != 64:
        failures.append("Self-engineering proposal digest must be SHA-256 hex")
    item_names = {item.name for item in pack.command_items}
    if item_names != set(COMMAND_ITEMS):
        failures.append("Command pack must include every command item")
    if not pack.destructive_actions_blocked_in_this_phase:
        failures.append("Destructive actions must remain blocked in Phase 13AP")
    return failures


def write_human_approved_command_pack(pack: HumanApprovedCommandPack, audit_out: Path) -> None:
    """Write deterministic JSON audit for a human-approved command pack."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human-approved application engineering command pack.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = build_human_approved_command_pack(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_human_approved_command_pack(pack, args.audit_out)

    print(json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_human_approved_command_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if pack.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
