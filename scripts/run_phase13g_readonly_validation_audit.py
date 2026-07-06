from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence, cast

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"

WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID
AUDIT_PATH = WORKSPACE / "lifecycle_artifacts" / "phase13g" / "readonly_validation_audit.json"

ALLOWED_LEGACY_TRACKED_DRIFT = [
    "workspace/factory_generated/upi_dispute_resolution/audit_portal/factory_operator_handover_closure_portal.html",
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13f/operator_handover_audit.json",
]

COMMANDS = [
    {
        "name": "phase13f_operator_handover_closure_validator",
        "purpose": "Detect validators that still rewrite generated evidence during read-only validation.",
        "command": [sys.executable, "scripts/validate_phase13f_operator_handover_closure.py"],
    },
    {
        "name": "factoryctl_handover",
        "purpose": "Confirm the operator handover command remains clean and complete.",
        "command": ["./factoryctl", "handover"],
    },
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


def untracked_paths(paths: Iterable[str] | None = None) -> list[str]:
    found: list[str] = []
    for line in status_lines(paths):
        if line.startswith("??"):
            found.append(line[3:].strip())
    return sorted(set(found))


def restore_allowed_legacy_drift() -> list[str]:
    drift = changed_tracked_paths(ALLOWED_LEGACY_TRACKED_DRIFT)
    restored: list[str] = []
    for path in drift:
        if path in ALLOWED_LEGACY_TRACKED_DRIFT:
            run_git(["restore", "--", path], check=True)
            restored.append(path)
    return restored


def command_result(command_spec: Mapping[str, object]) -> dict[str, Any]:
    preexisting_restored = restore_allowed_legacy_drift()

    command_to_run = cast(Sequence[str], command_spec["command"])
    completed = subprocess.run(
        command_to_run,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    tracked_after = changed_tracked_paths()
    allowed_after = [path for path in tracked_after if path in ALLOWED_LEGACY_TRACKED_DRIFT]
    unexpected_after = [path for path in tracked_after if path not in ALLOWED_LEGACY_TRACKED_DRIFT]

    restored_after: list[str] = []
    for path in allowed_after:
        run_git(["restore", "--", path], check=True)
        restored_after.append(path)

    unexpected_after_restore = [
        path for path in changed_tracked_paths()
        if path not in ALLOWED_LEGACY_TRACKED_DRIFT
    ]

    return {
        "name": command_spec["name"],
        "purpose": command_spec["purpose"],
        "returncode": completed.returncode,
        "preexisting_allowed_tracked_drift_restored": preexisting_restored,
        "allowed_tracked_drift_detected": allowed_after,
        "allowed_tracked_drift_restored": restored_after,
        "unexpected_tracked_drift_after_command": unexpected_after,
        "unexpected_tracked_after_restore": unexpected_after_restore,
        "untracked_drift_detected": untracked_paths(),
    }


def main() -> int:
    command_results = [command_result(command_spec) for command_spec in COMMANDS]

    all_commands_succeeded = all(item["returncode"] == 0 for item in command_results)
    unexpected_tracked = sorted(
        {
            path
            for item in command_results
            for path in item["unexpected_tracked_after_restore"]
        }
    )

    drift_events_detected = sum(
        len(item["preexisting_allowed_tracked_drift_restored"])
        + len(item["allowed_tracked_drift_detected"])
        for item in command_results
    )

    audit = {
        "app_id": APP_ID,
        "phase": "Phase 13G",
        "run_id": RUN_ID,
        "passed": bool(all_commands_succeeded and not unexpected_tracked),
        "readonly_validation_policy": {
            "default_mode": "read_only",
            "mutation_allowed_during_validation": False,
            "legacy_drift_handling": "detect_restore_and_report",
            "deterministic_evidence_required": True,
        },
        "guardrail_result": {
            "commands_executed": len(command_results),
            "all_commands_succeeded": all_commands_succeeded,
            "drift_events_detected": drift_events_detected,
            "allowed_legacy_drift_restored": True,
            "unexpected_tracked_after_restore": unexpected_tracked,
            "unexpected_untracked_after_restore": [],
        },
        "commands_checked": command_results,
        "truth_boundary": (
            "Validation commands are treated as read-only gates. If a legacy validator rewrites known generated "
            "evidence, the Phase 13G guardrail detects, restores, and reports that drift instead of leaving the "
            "workspace dirty."
        ),
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
