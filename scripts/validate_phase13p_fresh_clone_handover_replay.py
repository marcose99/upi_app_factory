#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import os
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
BASELINE_TAG = "v0.13.14-local-runnable-operator-demo-pack"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13p"
)
AUDIT_PATH = ARTIFACT_DIR / "fresh_clone_handover_replay_audit.json"
# Replay clone is intentionally outside the repository tree to avoid
# repository-level full pytest collecting nested clone tests.
DEFAULT_REPLAY_ROOT = (
    pathlib.Path(tempfile.gettempdir())
    / "upi_app_factory_phase13p_replay_workspace"
    / "fresh_clone_replay_workspace"
)


def configured_replay_root() -> pathlib.Path:
    configured = os.environ.get("PHASE13P_REPLAY_ROOT", "").strip()
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    return DEFAULT_REPLAY_ROOT


REPLAY_ROOT = configured_replay_root()
CLONE_DIR = REPLAY_ROOT / "repo_clone"


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != "Phase 13P":
        raise AssertionError("Audit phase is not Phase 13P.")
    if audit.get("baseline_tag") != BASELINE_TAG:
        raise AssertionError("Audit baseline tag is not the finalized Phase 13O tag.")
    if audit.get("passed") is not True:
        raise AssertionError("Fresh clone replay did not pass.")
    if audit.get("health_status") != "ok":
        raise AssertionError("Fresh clone health check did not pass.")
    if audit.get("demo_status") != "RESOLVED":
        raise AssertionError("Fresh clone demo did not resolve the dispute lifecycle.")
    if audit.get("verifier_passed") is not True:
        raise AssertionError("Fresh clone operator verifier did not pass.")
    replay_mode = str(audit.get("replay_mode", ""))
    if "fresh_clone" not in replay_mode:
        raise AssertionError("Audit does not record fresh clone replay mode.")
    boundary = str(audit.get("truth_boundary", ""))
    if "local and runnable" not in boundary or "simulated mocks only" not in boundary:
        raise AssertionError("Audit truth boundary is incomplete.")
    commands = audit.get("commands", [])
    if not isinstance(commands, list) or len(commands) < 8:
        raise AssertionError("Audit does not contain enough replay command evidence.")
    for result in commands:
        if not isinstance(result, dict) or result.get("return_code") != 0:
            raise AssertionError("One or more replay commands failed.")
    steps = audit.get("steps", [])
    step_names = [str(step.get("name")) for step in steps if isinstance(step, dict)]
    for required in [
        "resolve_clone_source",
        "fresh_clone_checkout",
        "regenerate_operator_pack_from_clone",
        "operator_handover_replay",
    ]:
        if required not in step_names:
            raise AssertionError(f"Missing replay step: {required}")


def validate_clone_workspace() -> None:
    if not CLONE_DIR.is_dir():
        raise AssertionError(f"Missing fresh clone directory: {CLONE_DIR}")
    pack_dir = (
        CLONE_DIR
        / "workspace"
        / "factory_generated"
        / APP_ID
        / "operator_handoff"
        / "phase13o_local_runnable_pack"
    )
    for relative_path in [
        "README.md",
        "HANDOVER.md",
        "health_check.py",
        "run_local_demo.py",
        "verify_operator_pack.py",
        "run_operator_demo.sh",
        "local_runtime_manifest.json",
    ]:
        if not (pack_dir / relative_path).is_file():
            raise AssertionError(f"Missing replayed operator pack file: {relative_path}")


def main() -> None:
    audit = load_audit()
    validate_audit(audit)
    validate_clone_workspace()
    result = {
        "passed": True,
        "phase": "Phase 13P",
        "baseline_tag": audit.get("baseline_tag"),
        "clone_head": audit.get("clone_head"),
        "replay_mode": audit.get("replay_mode"),
        "health_status": audit.get("health_status"),
        "demo_status": audit.get("demo_status"),
        "verifier_passed": audit.get("verifier_passed"),
        "audit_path": str(AUDIT_PATH),
        "fresh_clone_dir": str(CLONE_DIR),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
