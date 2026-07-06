from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID

AUDIT_PATH = WORKSPACE / "lifecycle_artifacts" / "phase13g" / "readonly_validation_audit.json"
PORTAL_PATH = WORKSPACE / "audit_portal" / "factory_readonly_validation_drift_guardrails_portal.html"

REQUIRED_FILES = [
    "scripts/run_phase13g_readonly_validation_audit.py",
    "scripts/generate_phase13g_readonly_validation_portal.py",
    "scripts/validate_phase13g_readonly_validation_guardrails.py",
    "tests/test_phase13g_readonly_validation_guardrails.py",
    "docs/phase13g/readonly_validation_drift_policy.json",
    "docs/phase13g/readonly_validation_architecture.json",
    "docs/phase13g/readonly_validation_drift_guardrails.md",
]

ALLOWED_LEGACY_TRACKED_DRIFT = [
    "workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_operator_handover_closure_portal.html",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13f/operator_handover_audit.json",
]


def run_git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def status_lines(paths: Iterable[str] | None = None) -> list[str]:
    args = ["status", "--porcelain=v1"]
    if paths:
        args.append("--")
        args.extend(paths)
    completed = run_git(args)
    return [line for line in completed.stdout.splitlines() if line.strip()]


def changed_tracked_paths(paths: Iterable[str] | None = None) -> list[str]:
    changed: list[str] = []
    for line in status_lines(paths):
        if line.startswith("??"):
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append(path)
    return sorted(set(changed))


def restore_allowed_legacy_drift() -> list[str]:
    restored: list[str] = []
    for path in changed_tracked_paths(ALLOWED_LEGACY_TRACKED_DRIFT):
        run_git(["restore", "--", path], check=True)
        restored.append(path)
    return restored


def unexpected_tracked_drift() -> list[str]:
    return [
        path
        for path in changed_tracked_paths()
        if path not in ALLOWED_LEGACY_TRACKED_DRIFT
    ]


def main() -> int:
    errors: list[str] = []

    restored = restore_allowed_legacy_drift()

    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).exists():
            errors.append(f"Missing required Phase 13G file: {relative_path}")

    if not AUDIT_PATH.exists():
        errors.append(f"Missing Phase 13G audit evidence: {AUDIT_PATH.relative_to(ROOT)}")
        audit = {}
    else:
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    if not PORTAL_PATH.exists():
        errors.append(f"Missing Phase 13G portal: {PORTAL_PATH.relative_to(ROOT)}")

    if audit:
        if audit.get("phase") != "Phase 13G":
            errors.append("Phase 13G audit has incorrect phase.")
        if audit.get("run_id") != RUN_ID:
            errors.append("Phase 13G audit has incorrect run_id.")
        if audit.get("passed") is not True:
            errors.append("Phase 13G audit did not pass.")

        policy = audit.get("readonly_validation_policy", {})
        if policy.get("mutation_allowed_during_validation") is not False:
            errors.append("Phase 13G policy must keep mutation_allowed_during_validation=false.")
        if policy.get("legacy_drift_handling") != "detect_restore_and_report":
            errors.append("Phase 13G policy must detect, restore, and report legacy drift.")

        result = audit.get("guardrail_result", {})
        if result.get("all_commands_succeeded") is not True:
            errors.append("Phase 13G guardrail did not execute all commands successfully.")
        if result.get("unexpected_tracked_after_restore"):
            errors.append("Phase 13G guardrail reported unexpected tracked drift after restore.")

    unexpected = unexpected_tracked_drift()
    generated_unexpected = [
        path
        for path in unexpected
        if path.startswith("workspace/factory_generated/")
        and "phase13g" not in path
        and path not in ALLOWED_LEGACY_TRACKED_DRIFT
    ]
    if generated_unexpected:
        errors.append(f"Unexpected generated workspace drift remains: {generated_unexpected}")

    output = {
        "app_id": APP_ID,
        "phase": "Phase 13G",
        "run_id": RUN_ID,
        "passed": not errors,
        "errors": errors,
        "allowed_legacy_drift_restored_during_validation": restored,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
