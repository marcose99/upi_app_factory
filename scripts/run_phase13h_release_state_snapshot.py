#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PHASE = "Phase 13H"
BASELINE_TAG = "v0.13.6-readonly-validation-drift-guardrails"
OUT = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13h" / "release_state_snapshot.json"

LINEAGE = [
    {"phase": "Phase 13C", "tag": "v0.13.2-real-governed-agent-runtime-foundation", "capability": "real local governed agent-runtime foundation"},
    {"phase": "Phase 13D", "tag": "v0.13.3-governed-agent-adapter-execution-layer", "capability": "governed adapter execution layer"},
    {"phase": "Phase 13E", "tag": "v0.13.4-factory-cli-operator-command-surface", "capability": "factoryctl operator command surface"},
    {"phase": "Phase 13F", "tag": "v0.13.5-operator-handover-closure", "capability": "operator handover closure"},
    {"phase": "Phase 13G", "tag": BASELINE_TAG, "capability": "read-only validation drift guardrails"},
]

REQUIRED_FILES = [
    "factoryctl",
    "docs/phase13g/readonly_validation_drift_guardrails.md",
    "docs/phase13f/operator_handover_closure.md",
    "docs/phase13e/factory_cli_operator_surface.md",
    "docs/phase13d/agent_adapter_execution_layer.md",
    "scripts/validate_phase13g_readonly_validation_guardrails.py",
    "scripts/validate_phase13f_operator_handover_closure.py",
    "scripts/validate_phase13e_factory_cli_operator_surface.py",
]


def git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    existing_tags = set(git_lines(["tag", "--list"]))
    file_status = {path: (ROOT / path).exists() for path in REQUIRED_FILES}
    lineage_status = [
        {**item, "tag_present": item["tag"] in existing_tags}
        for item in LINEAGE
    ]
    payload = {
        "phase": PHASE,
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "baseline_tag": BASELINE_TAG,
        "baseline_tag_present": BASELINE_TAG in existing_tags,
        "release_lineage": lineage_status,
        "operator_commands": [
            "./factoryctl status",
            "./factoryctl adapters",
            "./factoryctl validate --quick",
            "./factoryctl validate",
            "./factoryctl portals",
            "./factoryctl handover",
            "./factoryctl logs",
        ],
        "required_files": file_status,
        "truth_boundary": "Local deterministic execution remains the default; LangGraph/OpenAI execution remains detected and policy-gated, not falsely claimed as active.",
        "evidence_determinism": {
            "uses_wall_clock_timestamp": False,
            "uses_current_commit_hash": False,
            "reason": "Avoids post-commit and post-validation drift for release-state evidence.",
        },
        "passed": BASELINE_TAG in existing_tags and all(file_status.values()) and all(item["tag_present"] for item in lineage_status),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
