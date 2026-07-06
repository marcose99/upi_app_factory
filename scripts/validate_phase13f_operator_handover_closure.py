#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13f" / "operator_handover_audit.json"
PORTAL_FILE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_operator_handover_closure_portal.html"

REQUIRED_FILES = [
    "docs/phase13c/agent_runtime_handover.md",
    "docs/phase13f/operator_handover_closure.md",
    "docs/phase13f/operator_handover_closure_policy.json",
    "docs/phase13f/operator_handover_closure_architecture.json",
    "scripts/run_phase13f_operator_handover_audit.py",
    "scripts/generate_phase13f_operator_handover_portal.py",
    "scripts/validate_phase13f_operator_handover_closure.py",
    "tests/test_phase13f_operator_handover_closure.py",
]


def run_handover() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [str(PROJECT_ROOT / "factoryctl"), "handover"],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (PROJECT_ROOT / relative_path).exists():
            errors.append(f"Missing required Phase 13F file: {relative_path}")

    if not AUDIT_FILE.exists():
        errors.append(f"Missing Phase 13F audit file: {AUDIT_FILE.relative_to(PROJECT_ROOT)}")
    else:
        audit = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
        if audit.get("phase") != "Phase 13F":
            errors.append("Audit phase is not Phase 13F")
        if audit.get("app_id") != APP_ID:
            errors.append("Audit app_id mismatch")
        if audit.get("run_id") != RUN_ID:
            errors.append("Audit run_id mismatch")
        if not audit.get("passed"):
            errors.append("Phase 13F audit did not pass")
        if audit.get("missing_output_lines"):
            errors.append("factoryctl handover still reports missing output lines")
        if audit.get("missing_documents"):
            errors.append("Required handover documents are still missing")

    if not PORTAL_FILE.exists():
        errors.append(f"Missing Phase 13F portal: {PORTAL_FILE.relative_to(PROJECT_ROOT)}")

    handover = run_handover()
    if handover.returncode != 0:
        errors.append(f"factoryctl handover exited with {handover.returncode}")
    if "[MISSING]" in handover.stdout:
        errors.append("factoryctl handover contains [MISSING]")

    result = {
        "phase": "Phase 13F",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "passed": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
