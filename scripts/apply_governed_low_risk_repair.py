#!/usr/bin/env python3
"""Apply governed low-risk repairs in explicit local sandbox targets.

Phase 13AU is intentionally bounded. It can automatically apply only known
low-risk text repairs inside an explicit sandbox target. It never modifies the
project worktree automatically and never touches protected targets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


APP_ID = "upi_dispute_resolution"

STATUS_APPLIED = "LOW_RISK_REPAIR_APPLIED_IN_EXPLICIT_SANDBOX"
STATUS_DRY_RUN = "LOW_RISK_REPAIR_DRY_RUN_READY"
STATUS_BLOCKED = "LOW_RISK_REPAIR_BLOCKED_BY_GOVERNANCE"

ALLOWED_REPAIR_CLASSES: dict[str, tuple[str, tuple[str, ...]]] = {
    "REPAIR-DOC-001": ("low", (".md", ".txt")),
    "REPAIR-TYPE-001": ("low", (".py",)),
    "REPAIR-TERM-001": ("low", (".md", ".json", ".py", ".txt")),
}

PROTECTED_PATH_PARTS: tuple[str, ...] = (
    ".git",
    ".venv",
    "generated_application",
    "release_tags",
    "live_provider_configuration",
)

REQUIRED_RESULT_ITEMS: tuple[str, ...] = (
    "repair_class",
    "risk_tier",
    "target_path",
    "before_digest",
    "after_digest",
    "backup_snapshot",
    "rollback_plan",
    "evidence",
    "blocked_actions_checked",
    "sandbox_acknowledged",
)


@dataclass(frozen=True)
class LowRiskRepairRequest:
    """Input request for a low-risk repair."""

    target_root: Path
    relative_path: Path
    repair_class: str
    old_text: str
    new_text: str
    apply: bool
    sandbox_acknowledged: bool


@dataclass(frozen=True)
class LowRiskRepairResult:
    """Result of a low-risk repair attempt."""

    app_id: str
    repair_status: str
    repair_class: str
    risk_tier: str
    target_path: str
    before_digest: str
    after_digest: str
    backup_snapshot: str
    rollback_plan: str
    evidence: tuple[str, ...]
    blocked_actions_checked: tuple[str, ...]
    sandbox_acknowledged: bool
    applied: bool
    dry_run: bool
    project_worktree_modified: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    factory_self_modification_applied: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.repair_status in {STATUS_APPLIED, STATUS_DRY_RUN}

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "after_digest": self.after_digest,
            "app_id": self.app_id,
            "applied": self.applied,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "backup_snapshot": self.backup_snapshot,
            "before_digest": self.before_digest,
            "blocked_actions_checked": list(self.blocked_actions_checked),
            "dry_run": self.dry_run,
            "evidence": list(self.evidence),
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "project_worktree_modified": self.project_worktree_modified,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "repair_class": self.repair_class,
            "repair_status": self.repair_status,
            "risk_tier": self.risk_tier,
            "rollback_plan": self.rollback_plan,
            "sandbox_acknowledged": self.sandbox_acknowledged,
            "schema_version": "low-risk-autonomous-repair-result.v1",
            "target_path": self.target_path,
        }


def sha256_text(value: str) -> str:
    """Return SHA-256 digest for text."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _empty_digest() -> str:
    return hashlib.sha256(b"").hexdigest()


def _blocked_result(request: LowRiskRepairRequest, reasons: tuple[str, ...]) -> LowRiskRepairResult:
    target_path = str(request.target_root / request.relative_path)
    return LowRiskRepairResult(
        app_id=APP_ID,
        repair_status=STATUS_BLOCKED,
        repair_class=request.repair_class,
        risk_tier="unknown",
        target_path=target_path,
        before_digest=_empty_digest(),
        after_digest=_empty_digest(),
        backup_snapshot="",
        rollback_plan="Repair blocked before mutation.",
        evidence=("blocked_by_governance",),
        blocked_actions_checked=(
            "protected_paths",
            "repair_class_allowlist",
            "extension_allowlist",
            "sandbox_acknowledgement",
            "project_worktree_auto_repair_block",
        ),
        sandbox_acknowledged=request.sandbox_acknowledged,
        applied=False,
        dry_run=False,
        project_worktree_modified=False,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        factory_self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=reasons,
    )


def _relative_path_is_safe(relative_path: Path) -> bool:
    return not relative_path.is_absolute() and ".." not in relative_path.parts


def _contains_protected_part(path: Path) -> bool:
    parts = set(path.parts)
    return any(protected in parts for protected in PROTECTED_PATH_PARTS)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def apply_low_risk_repair(request: LowRiskRepairRequest) -> LowRiskRepairResult:
    """Apply or dry-run a low-risk repair request."""

    reasons: list[str] = []

    if request.repair_class not in ALLOWED_REPAIR_CLASSES:
        return _blocked_result(request, (f"Repair class is not allowed: {request.repair_class}",))

    risk_tier, allowed_suffixes = ALLOWED_REPAIR_CLASSES[request.repair_class]
    if risk_tier != "low":
        return _blocked_result(request, (f"Only low-risk repairs are allowed; got {risk_tier}",))

    if not _relative_path_is_safe(request.relative_path):
        return _blocked_result(request, ("Target path must be a safe relative path.",))

    target_root = request.target_root.resolve()
    target_path = (target_root / request.relative_path).resolve()
    project_root = _project_root().resolve()

    try:
        target_path.relative_to(target_root)
    except ValueError:
        return _blocked_result(request, ("Target path escapes target root.",))

    if _contains_protected_part(request.relative_path):
        return _blocked_result(request, ("Protected path is blocked.",))

    if target_path.suffix not in allowed_suffixes:
        return _blocked_result(request, (f"File extension is not allowed for {request.repair_class}.",))

    if request.apply and target_root == project_root:
        return _blocked_result(request, ("Automatic project worktree repair is blocked in Phase 13AU.",))

    if request.apply and not request.sandbox_acknowledged:
        return _blocked_result(request, ("Explicit sandbox acknowledgement is required before automatic repair.",))

    if not target_path.exists():
        return _blocked_result(request, (f"Target file does not exist: {target_path}",))

    original = target_path.read_text(encoding="utf-8")
    before_digest = sha256_text(original)

    if request.old_text not in original:
        return _blocked_result(request, ("Old text was not found; no deterministic repair can be applied.",))

    repaired = original.replace(request.old_text, request.new_text, 1)
    after_digest = sha256_text(repaired)

    backup_snapshot = original
    rollback_plan = "Restore the exact backup_snapshot content to target_path and rerun validation gates."
    evidence = (
        "repair_class_allowlisted",
        "risk_tier_low",
        "target_path_checked",
        "protected_paths_checked",
        "before_digest_recorded",
        "after_digest_recorded",
        "backup_snapshot_recorded",
        "rollback_plan_recorded",
    )

    if request.apply:
        target_path.write_text(repaired, encoding="utf-8")
        status = STATUS_APPLIED
        applied = True
        dry_run = False
        reasons.append("Known low-risk repair applied in explicit local sandbox.")
    else:
        status = STATUS_DRY_RUN
        applied = False
        dry_run = True
        reasons.append("Known low-risk repair dry-run completed without mutation.")

    return LowRiskRepairResult(
        app_id=APP_ID,
        repair_status=status,
        repair_class=request.repair_class,
        risk_tier=risk_tier,
        target_path=str(target_path),
        before_digest=before_digest,
        after_digest=after_digest,
        backup_snapshot=backup_snapshot,
        rollback_plan=rollback_plan,
        evidence=evidence,
        blocked_actions_checked=(
            "protected_paths",
            "repair_class_allowlist",
            "extension_allowlist",
            "sandbox_acknowledgement",
            "project_worktree_auto_repair_block",
        ),
        sandbox_acknowledged=request.sandbox_acknowledged,
        applied=applied,
        dry_run=dry_run,
        project_worktree_modified=False,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        factory_self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=tuple(reasons),
    )


def validate_low_risk_repair_result(result: LowRiskRepairResult) -> list[str]:
    """Validate low-risk repair safety evidence."""

    failures: list[str] = []
    if result.repair_class not in ALLOWED_REPAIR_CLASSES:
        failures.append("Repair class must be allowlisted")
    if result.risk_tier not in {"low", "unknown"}:
        failures.append("Only low or blocked unknown risk repairs are allowed")
    if result.project_worktree_modified:
        failures.append("Project worktree must not be auto-modified")
    if result.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if result.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if result.factory_self_modification_applied:
        failures.append("Factory self-modification must not be applied")
    if result.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if result.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if result.auto_merge_performed or result.auto_tag_performed or result.auto_release_performed:
        failures.append("Merge, tag, and release must not be automatic")
    if result.repair_status in {STATUS_APPLIED, STATUS_DRY_RUN}:
        if len(result.before_digest) != 64 or len(result.after_digest) != 64:
            failures.append("Before and after digests must be SHA-256 hex")
        if not result.backup_snapshot:
            failures.append("Backup snapshot is required")
        if not result.rollback_plan:
            failures.append("Rollback plan is required")
        for item in REQUIRED_RESULT_ITEMS:
            if item == "repair_class" and not result.repair_class:
                failures.append("Missing repair class")
            if item == "risk_tier" and not result.risk_tier:
                failures.append("Missing risk tier")
            if item == "target_path" and not result.target_path:
                failures.append("Missing target path")
            if item == "evidence" and not result.evidence:
                failures.append("Missing evidence")
            if item == "blocked_actions_checked" and not result.blocked_actions_checked:
                failures.append("Missing blocked action checks")
    return failures


def write_low_risk_repair_result(result: LowRiskRepairResult, audit_out: Path) -> None:
    """Write deterministic JSON audit for repair result."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(result.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply governed low-risk repair in sandbox mode.")
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--relative-path", type=Path, required=True)
    parser.add_argument("--repair-class", required=True)
    parser.add_argument("--old-text", required=True)
    parser.add_argument("--new-text", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sandbox-acknowledged", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    request = LowRiskRepairRequest(
        target_root=args.target_root,
        relative_path=args.relative_path,
        repair_class=args.repair_class,
        old_text=args.old_text,
        new_text=args.new_text,
        apply=args.apply,
        sandbox_acknowledged=args.sandbox_acknowledged,
    )
    result = apply_low_risk_repair(request)

    if args.audit_out is not None:
        write_low_risk_repair_result(result, args.audit_out)

    print(json.dumps(result.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_low_risk_repair_result(result)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
