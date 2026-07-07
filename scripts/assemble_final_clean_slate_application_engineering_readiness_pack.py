#!/usr/bin/env python3
"""Assemble final clean-slate application engineering readiness pack.

Phase 13AO is intentionally non-destructive. It produces a final readiness pack
for human review before a later separately approved destructive phase.
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


from scripts.controlled_real_clean_slate_application_engineering import (  # noqa: E402
    HARNESS_READY,
    build_controlled_harness_report,
)


APP_ID = "upi_dispute_resolution"
READY = "FINAL_READINESS_PACK_READY_FOR_HUMAN_REVIEW"
BLOCKED = "FINAL_READINESS_PACK_BLOCKED_BY_CONTROLLED_HARNESS"

READINESS_ITEMS: tuple[str, ...] = (
    "controlled_harness_ready",
    "backup_manifest_digest_present",
    "execution_package_digest_present",
    "approval_token_reference_present",
    "operator_confirmation_present",
    "post_engineering_certification_planned",
    "handoff_replay_planned",
    "human_merge_tag_release_gate_planned",
    "destructive_actions_remain_blocked",
)


@dataclass(frozen=True)
class ReadinessItem:
    """One final readiness item."""

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
class FinalReadinessPack:
    """Final non-destructive readiness pack."""

    app_id: str
    readiness_status: str
    preferred_term: str
    project_root: str
    ready_for_human_review: bool
    controlled_harness_ready: bool
    approval_token_present: bool
    operator_confirmation_present: bool
    backup_manifest_digest: str
    execution_package_digest: str
    final_readiness_digest: str
    readiness_items: tuple[ReadinessItem, ...]
    next_phase_may_be_destructive_only_if_explicitly_requested: bool
    next_phase_requires_new_human_approval: bool
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
        return self.readiness_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "approval_token_present": self.approval_token_present,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "backup_manifest_digest": self.backup_manifest_digest,
            "controlled_harness_ready": self.controlled_harness_ready,
            "destructive_execution_performed": self.destructive_execution_performed,
            "execution_package_digest": self.execution_package_digest,
            "external_system_calls_performed": self.external_system_calls_performed,
            "final_readiness_digest": self.final_readiness_digest,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "next_phase_may_be_destructive_only_if_explicitly_requested": self.next_phase_may_be_destructive_only_if_explicitly_requested,
            "next_phase_requires_new_human_approval": self.next_phase_requires_new_human_approval,
            "operator_confirmation_present": self.operator_confirmation_present,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "readiness_items": [item.to_dict() for item in self.readiness_items],
            "readiness_status": self.readiness_status,
            "ready": self.ready,
            "ready_for_human_review": self.ready_for_human_review,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "schema_version": "final-clean-slate-application-engineering-readiness-pack.v1",
        }


def _build_items(
    controlled_harness_ready: bool,
    approval_token_present: bool,
    operator_confirmation_present: bool,
    backup_digest: str,
    execution_digest: str,
) -> tuple[ReadinessItem, ...]:
    item_values: dict[str, tuple[bool, str]] = {
        "controlled_harness_ready": (
            controlled_harness_ready,
            "Phase 13AN controlled harness status.",
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
            "Human approval token path was supplied to the readiness pack assembler.",
        ),
        "operator_confirmation_present": (
            operator_confirmation_present,
            "Explicit operator confirmation flag was supplied.",
        ),
        "post_engineering_certification_planned": (
            True,
            "Phase 13AN planned full post-engineering certification.",
        ),
        "handoff_replay_planned": (
            True,
            "Phase 13AN planned handoff replay.",
        ),
        "human_merge_tag_release_gate_planned": (
            True,
            "Phase 13AN preserved human merge/tag/release gate.",
        ),
        "destructive_actions_remain_blocked": (
            True,
            "Phase 13AO performs no delete, overwrite, live provider call, external call, merge, tag, or release.",
        ),
    }
    return tuple(
        ReadinessItem(name=name, satisfied=item_values[name][0], evidence=item_values[name][1])
        for name in READINESS_ITEMS
    )


def _digest_readiness_items(items: tuple[ReadinessItem, ...]) -> str:
    payload = [item.to_dict() for item in items]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assemble_final_readiness_pack(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> FinalReadinessPack:
    """Assemble final non-destructive readiness pack."""

    root = project_root.resolve()
    harness = build_controlled_harness_report(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    harness_ready = harness.harness_status == HARNESS_READY

    items = _build_items(
        controlled_harness_ready=harness_ready,
        approval_token_present=approval_token is not None,
        operator_confirmation_present=operator_confirmation,
        backup_digest=harness.backup_manifest_digest,
        execution_digest=harness.execution_package_digest,
    )
    all_items_satisfied = all(item.satisfied for item in items)
    status = READY if harness_ready and all_items_satisfied else BLOCKED

    reasons = list(harness.reasons)
    if status == READY:
        reasons.append("Final readiness pack is ready for human review; Phase 13AO remains non-destructive.")
    else:
        reasons.append("Final readiness pack is blocked until controlled harness and review inputs are complete.")

    return FinalReadinessPack(
        app_id=APP_ID,
        readiness_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        ready_for_human_review=status == READY,
        controlled_harness_ready=harness_ready,
        approval_token_present=approval_token is not None,
        operator_confirmation_present=operator_confirmation,
        backup_manifest_digest=harness.backup_manifest_digest,
        execution_package_digest=harness.execution_package_digest,
        final_readiness_digest=_digest_readiness_items(items),
        readiness_items=items,
        next_phase_may_be_destructive_only_if_explicitly_requested=True,
        next_phase_requires_new_human_approval=True,
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


def validate_final_readiness_pack(pack: FinalReadinessPack) -> list[str]:
    """Validate final readiness pack safety properties."""

    failures: list[str] = []
    if pack.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if pack.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if pack.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if pack.destructive_execution_performed:
        failures.append("Phase 13AO must not perform destructive execution")
    if pack.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if pack.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if pack.auto_merge_performed or pack.auto_tag_performed or pack.auto_release_performed:
        failures.append("Phase 13AO must not merge, tag, or release")
    if len(pack.final_readiness_digest) != 64:
        failures.append("Final readiness digest must be SHA-256 hex")
    item_names = {item.name for item in pack.readiness_items}
    if item_names != set(READINESS_ITEMS):
        failures.append("Final readiness pack must include every required readiness item")
    if not pack.next_phase_requires_new_human_approval:
        failures.append("Next destructive phase must require new human approval")
    return failures


def write_final_readiness_pack(pack: FinalReadinessPack, audit_out: Path) -> None:
    """Write deterministic JSON audit for a final readiness pack."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble final clean-slate application engineering readiness pack.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = assemble_final_readiness_pack(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_final_readiness_pack(pack, args.audit_out)

    print(json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_final_readiness_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if pack.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
