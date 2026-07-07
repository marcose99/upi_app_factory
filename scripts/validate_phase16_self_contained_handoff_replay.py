#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase16"
REQUIRED = [
    ROOT / "docs" / "phase16" / "self_contained_handoff_replay_hardening.md",
    ROOT / "policies" / "phase16_self_contained_handoff_replay_policy.json",
    ROOT / "scripts" / "run_phase16_self_contained_handoff_replay.py",
    ROOT / "scripts" / "validate_phase16_self_contained_handoff_replay.py",
    ROOT / "tests" / "test_phase16_self_contained_handoff_replay.py",
    PHASE_DIR / "self_contained_handoff_replay_hardening_audit.json",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"Expected JSON object: {path.relative_to(ROOT)}")
    return cast(dict[str, Any], data)


def main() -> int:
    for path in REQUIRED:
        require(path.exists(), f"Missing Phase 16 artifact: {path.relative_to(ROOT)}")

    doc = (ROOT / "docs" / "phase16" / "self_contained_handoff_replay_hardening.md").read_text(encoding="utf-8")
    require("certification-ready-not-certified" in doc, "Certification boundary phrase missing from Phase 16 doc")
    require("fresh clone" in doc.lower(), "Fresh-clone replay scope missing from Phase 16 doc")

    policy = load_json(ROOT / "policies" / "phase16_self_contained_handoff_replay_policy.json")
    require(policy.get("certification_ready_not_certified_boundary_preserved") is True, "Policy must preserve certification boundary")
    require(policy.get("full_fresh_clone_replay_required") is True, "Policy must require full fresh-clone replay")

    audit = load_json(PHASE_DIR / "self_contained_handoff_replay_hardening_audit.json")
    require(audit.get("phase") == "16", "Audit phase mismatch")
    require(audit.get("factory_does_not_self_certify") is True, "Factory must not self-certify")
    require(audit.get("self_contained_full_fresh_clone_gate_enabled") is True, "Self-contained replay gate missing")

    replay = PHASE_DIR / "self_contained_full_fresh_clone_replay_result.json"
    if replay.exists():
        replay_data = load_json(replay)
        require(replay_data.get("status") == "PASS", "Committed fresh-clone replay result must be PASS")
        require(replay_data.get("full_pytest_returncode") == 0, "Fresh-clone full pytest return code must be 0")
        require(replay_data.get("certification_claimed") is False, "Replay evidence must not claim certification")

    print("Phase 16 self-contained handoff replay hardening artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
