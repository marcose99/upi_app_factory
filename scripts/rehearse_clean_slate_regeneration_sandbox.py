#!/usr/bin/env python3
"""Rehearse clean-slate regeneration in a sandbox.

Phase 13AK may materialize rehearsal files only under the Phase 13AK sandbox
inside lifecycle artifacts. It must not delete or overwrite the real generated
application.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.plan_clean_slate_regeneration_dry_run import (  # noqa: E402
    DRY_RUN_READY,
    build_clean_slate_dry_run_plan,
)
from scripts.validate_clean_slate_human_approval import approval_template  # noqa: E402


APP_ID = "upi_dispute_resolution"
SANDBOX_RELATIVE_ROOT = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ak/sandbox"
)
REAL_GENERATED_APPLICATION = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
REHEARSAL_FILES: tuple[tuple[str, str], ...] = (
    (
        "README.md",
        "# Clean-Slate Sandbox Rehearsal\n\n"
        "This is a sandbox-only rehearsal artifact. It is not the real generated application.\n",
    ),
    (
        "manifest/rehearsal_scope.json",
        '{\n'
        '  "scope": "SANDBOX_ONLY",\n'
        '  "real_generated_application_untouched": true,\n'
        '  "live_provider_calls_performed": false,\n'
        '  "external_system_calls_performed": false\n'
        '}\n',
    ),
)


@dataclass(frozen=True)
class SandboxFile:
    """One planned or materialized sandbox file."""

    relative_path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class SandboxRehearsalReport:
    """Sandbox-only clean-slate regeneration rehearsal report."""

    app_id: str
    sandbox_status: str
    project_root: str
    sandbox_root: str
    real_generated_application_path: str
    dry_run_ready: bool
    materialized_sandbox: bool
    sandbox_only: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    manifest_digest: str
    files: tuple[SandboxFile, ...]
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.sandbox_status == "SANDBOX_REHEARSAL_READY"

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "dry_run_ready": self.dry_run_ready,
            "external_system_calls_performed": self.external_system_calls_performed,
            "files": [item.to_dict() for item in self.files],
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "manifest_digest": self.manifest_digest,
            "materialized_sandbox": self.materialized_sandbox,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "real_generated_application_path": self.real_generated_application_path,
            "reasons": list(self.reasons),
            "sandbox_only": self.sandbox_only,
            "sandbox_root": self.sandbox_root,
            "sandbox_status": self.sandbox_status,
            "schema_version": "clean-slate-sandbox-rehearsal-report.v1",
        }


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _planned_files() -> tuple[SandboxFile, ...]:
    return tuple(
        SandboxFile(
            relative_path=relative_path,
            size_bytes=len(content.encode("utf-8")),
            sha256=_sha256_text(content),
        )
        for relative_path, content in REHEARSAL_FILES
    )


def _manifest_digest(files: Iterable[SandboxFile]) -> str:
    payload = [item.to_dict() for item in files]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_rehearsal_files(sandbox_root: Path) -> None:
    for relative_path, content in REHEARSAL_FILES:
        target = sandbox_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def sample_approval_token_payload() -> dict[str, object]:
    """Return a valid sample approval token for sandbox rehearsal tests."""

    token = approval_template()
    token["approved_by"] = "local-human-operator"
    token["approval_reason"] = "Controlled sandbox rehearsal sample for Phase 13AK."
    token["approved_at_utc"] = "2099-01-01T00:00:00Z"
    return token


def build_sandbox_rehearsal_report(
    project_root: Path,
    approval_token: Path | None = None,
    sandbox_root: Path = SANDBOX_RELATIVE_ROOT,
    materialize_sandbox: bool = False,
) -> SandboxRehearsalReport:
    """Build a sandbox-only clean-slate rehearsal report."""

    root = project_root.resolve()
    resolved_sandbox = _resolve_project_path(root, sandbox_root)
    approved_sandbox = _resolve_project_path(root, SANDBOX_RELATIVE_ROOT)
    real_generated_application = _resolve_project_path(root, REAL_GENERATED_APPLICATION)

    reasons: list[str] = []

    sandbox_only = resolved_sandbox == approved_sandbox and _is_relative_to(resolved_sandbox, root)
    if not sandbox_only:
        reasons.append("Sandbox path is not the approved Phase 13AK sandbox boundary.")

    dry_run_plan = build_clean_slate_dry_run_plan(root, approval_token)
    dry_run_ready = dry_run_plan.dry_run_status == DRY_RUN_READY

    if not dry_run_ready:
        reasons.append("Phase 13AJ dry-run plan is not ready; sandbox rehearsal remains blocked.")
    else:
        reasons.append("Phase 13AJ dry-run plan is ready for sandbox-only rehearsal.")

    files = _planned_files()
    digest = _manifest_digest(files)

    if materialize_sandbox and sandbox_only and dry_run_ready:
        _write_rehearsal_files(resolved_sandbox)
        reasons.append("Sandbox rehearsal files materialized under Phase 13AK sandbox only.")
    elif materialize_sandbox:
        reasons.append("Sandbox materialization skipped because safety preconditions were not met.")

    status = "SANDBOX_REHEARSAL_READY" if sandbox_only and dry_run_ready else "SANDBOX_REHEARSAL_BLOCKED"

    return SandboxRehearsalReport(
        app_id=APP_ID,
        sandbox_status=status,
        project_root=str(root),
        sandbox_root=str(resolved_sandbox),
        real_generated_application_path=str(real_generated_application),
        dry_run_ready=dry_run_ready,
        materialized_sandbox=materialize_sandbox and sandbox_only and dry_run_ready,
        sandbox_only=sandbox_only,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        manifest_digest=digest,
        files=files,
        reasons=tuple(reasons),
    )


def validate_sandbox_rehearsal_report(report: SandboxRehearsalReport) -> list[str]:
    """Validate sandbox rehearsal safety properties."""

    failures: list[str] = []
    if not report.sandbox_only:
        failures.append("Sandbox rehearsal must be confined to the approved sandbox root")
    if report.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if report.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if report.live_provider_calls_performed:
        failures.append("Sandbox rehearsal must not call live providers")
    if report.external_system_calls_performed:
        failures.append("Sandbox rehearsal must not call external systems")
    if report.auto_merge_performed or report.auto_tag_performed or report.auto_release_performed:
        failures.append("Sandbox rehearsal must not merge, tag, or release")
    if len(report.manifest_digest) != 64:
        failures.append("Sandbox manifest digest must be SHA-256 hex")
    if not report.files:
        failures.append("Sandbox rehearsal must define planned files")
    return failures


def write_sandbox_rehearsal_report(report: SandboxRehearsalReport, audit_out: Path) -> None:
    """Write deterministic JSON audit for a sandbox rehearsal report."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(report.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run clean-slate sandbox rehearsal.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--sandbox-root", type=Path, default=SANDBOX_RELATIVE_ROOT)
    parser.add_argument("--materialize-sandbox", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_sandbox_rehearsal_report(
        project_root=args.project_root,
        approval_token=args.approval_token,
        sandbox_root=args.sandbox_root,
        materialize_sandbox=args.materialize_sandbox,
    )

    if args.audit_out is not None:
        write_sandbox_rehearsal_report(report, args.audit_out)

    print(json.dumps(report.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_sandbox_rehearsal_report(report)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
