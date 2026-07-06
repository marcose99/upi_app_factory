#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13f"
AUDIT_FILE = ARTIFACT_DIR / "operator_handover_audit.json"

REQUIRED_HANDOVER_DOCUMENTS = [
    "docs/phase13c/agent_runtime_handover.md",
    "docs/phase13f/operator_handover_closure.md",
    "docs/phase13f/operator_handover_closure_policy.json",
    "docs/phase13f/operator_handover_closure_architecture.json",
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
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    handover = run_handover()
    output_lines = handover.stdout.splitlines()
    missing_output_lines = [line for line in output_lines if "[MISSING]" in line]
    ok_output_lines = [line for line in output_lines if "[OK]" in line]
    missing_documents = [path for path in REQUIRED_HANDOVER_DOCUMENTS if not (PROJECT_ROOT / path).exists()]

    passed = handover.returncode == 0 and not missing_output_lines and not missing_documents
    audit = {
        "phase": "Phase 13F",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "factoryctl_handover_returncode": handover.returncode,
        "missing_output_lines": missing_output_lines,
        "ok_output_lines": ok_output_lines,
        "missing_documents": missing_documents,
        "required_handover_documents": REQUIRED_HANDOVER_DOCUMENTS,
        "truth_boundary": "Phase 13F closes operator handover documentation only; it does not activate LangGraph/OpenAI execution.",
    }
    AUDIT_FILE.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
