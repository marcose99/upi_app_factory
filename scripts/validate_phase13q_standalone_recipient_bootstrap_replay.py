#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
BASELINE_TAG = "v0.13.15-fresh-clone-handover-replay"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13q"
)
AUDIT_PATH = ARTIFACT_DIR / "standalone_recipient_bootstrap_replay_audit.json"
DEFAULT_REPLAY_ROOT = (
    PROJECT_ROOT.parent
    / "upi_app_factory_phase13q_recipient_bootstrap_workspace"
    / "fresh_clone_bootstrap_workspace"
)


def configured_replay_root() -> pathlib.Path:
    configured = os.environ.get("PHASE13Q_REPLAY_ROOT", "").strip()
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    return DEFAULT_REPLAY_ROOT


REPLAY_ROOT = configured_replay_root()
CLONE_DIR = REPLAY_ROOT / "repo_clone"
RECIPIENT_VENV_DIR = CLONE_DIR / ".venv_recipient"


def venv_python() -> pathlib.Path:
    if RECIPIENT_VENV_DIR.joinpath("Scripts", "python.exe").exists():
        return RECIPIENT_VENV_DIR / "Scripts" / "python.exe"
    return RECIPIENT_VENV_DIR / "bin" / "python"


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != "Phase 13Q":
        raise AssertionError("Audit phase is not Phase 13Q.")
    if audit.get("baseline_tag") != BASELINE_TAG:
        raise AssertionError("Audit baseline tag is not the finalized Phase 13P tag.")
    if audit.get("passed") is not True:
        raise AssertionError("Standalone recipient bootstrap replay did not pass.")
    if audit.get("replay_mode") != "fresh_clone_new_recipient_venv":
        raise AssertionError("Replay mode must use a new recipient venv.")
    if audit.get("health_status") != "ok":
        raise AssertionError("Recipient health check did not pass.")
    if audit.get("demo_status") != "RESOLVED":
        raise AssertionError("Recipient demo did not resolve the dispute lifecycle.")
    if audit.get("verifier_passed") is not True:
        raise AssertionError("Recipient operator verifier did not pass.")
    if audit.get("orchestration_framework") != "langgraph":
        raise AssertionError("Audit does not record LangGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit does not record StateGraph graph type.")
    boundary = str(audit.get("truth_boundary", ""))
    if "virtual environment" not in boundary or "simulated mocks only" not in boundary:
        raise AssertionError("Audit truth boundary is incomplete.")
    commands = audit.get("commands", [])
    if not isinstance(commands, list) or len(commands) < 10:
        raise AssertionError("Audit does not contain enough bootstrap command evidence.")
    for result in commands:
        if not isinstance(result, dict) or result.get("return_code") != 0:
            raise AssertionError("One or more bootstrap commands failed.")
    steps = audit.get("steps", [])
    step_names = [str(step.get("name")) for step in steps if isinstance(step, dict)]
    for required in [
        "clone_checkout_agent",
        "dependency_bootstrap_agent",
        "operator_pack_replay_agent",
        "operator_demo_replay_agent",
        "governance_evidence_agent",
    ]:
        if required not in step_names:
            raise AssertionError(f"Missing bootstrap step: {required}")


def validate_clone_workspace() -> None:
    if not CLONE_DIR.is_dir():
        raise AssertionError(f"Missing fresh clone directory: {CLONE_DIR}")
    py = venv_python()
    if not py.is_file():
        raise AssertionError(f"Missing recipient Python executable: {py}")
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
            raise AssertionError(f"Missing recipient operator pack file: {relative_path}")


def main() -> None:
    audit = load_audit()
    validate_audit(audit)
    validate_clone_workspace()
    result = {
        "passed": True,
        "phase": "Phase 13Q",
        "baseline_tag": audit.get("baseline_tag"),
        "clone_head": audit.get("clone_head"),
        "replay_mode": audit.get("replay_mode"),
        "recipient_python": audit.get("recipient_python"),
        "health_status": audit.get("health_status"),
        "demo_status": audit.get("demo_status"),
        "verifier_passed": audit.get("verifier_passed"),
        "audit_path": str(AUDIT_PATH),
        "fresh_clone_dir": str(CLONE_DIR),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
