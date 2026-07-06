#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, TypedDict, cast

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
# Keep the replay clone outside the repository tree so repository-level
# full pytest does not recursively collect the clone's tests/conftest.py.
REPLAY_ROOT = (
    PROJECT_ROOT.parent
    / "upi_dispute_resolution_factory_phase13p_replay_workspace"
    / "fresh_clone_replay_workspace"
)
CLONE_DIR = REPLAY_ROOT / "repo_clone"
AUDIT_PATH = ARTIFACT_DIR / "fresh_clone_handover_replay_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "fresh_clone_handover_replay_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "fresh_clone_handover_replay_report.md"
PACK_RELATIVE = pathlib.Path(
    "workspace/factory_generated/upi_dispute_resolution/operator_handoff/"
    "phase13o_local_runnable_pack"
)


class CommandResult(TypedDict):
    command: list[str]
    cwd: str
    return_code: int
    output_preview: str


class ReplayStep(TypedDict):
    name: str
    status: str
    detail: str


class ReplayState(TypedDict):
    clone_source: str
    clone_head: str
    baseline_tag: str
    replay_python: str
    replay_mode: str
    operator_pack_dir: str
    commands: list[CommandResult]
    steps: list[ReplayStep]
    health_status: str
    demo_status: str
    verifier_passed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def add_step(steps: list[ReplayStep], name: str, status: str, detail: str) -> None:
    steps.append({"name": name, "status": status, "detail": detail})


def command_output(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def run_required(
    command: list[str],
    cwd: pathlib.Path,
    commands: list[CommandResult],
    *,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    commands.append(
        {
            "command": command,
            "cwd": str(cwd),
            "return_code": result.returncode,
            "output_preview": output[:4000],
        }
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {command}\n{output}"
        )
    return result.stdout


def get_clone_source() -> str:
    configured = os.environ.get("PHASE13P_CLONE_SOURCE", "").strip()
    if configured:
        return configured
    result = command_output(["git", "config", "--get", "remote.origin.url"], PROJECT_ROOT)
    source = result.stdout.strip()
    if source:
        return source
    return str(PROJECT_ROOT)


def replay_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(CLONE_DIR / "src"),
            str(CLONE_DIR / "scripts"),
            str(CLONE_DIR),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["MYPYPATH"] = ""
    env["PYTHON_BIN"] = sys.executable
    return env


def parse_json_output(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise RuntimeError("Expected command to produce a JSON object.")
    return cast(dict[str, Any], payload)


def run_replay() -> ReplayState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if REPLAY_ROOT.exists():
        shutil.rmtree(REPLAY_ROOT)
    REPLAY_ROOT.mkdir(parents=True, exist_ok=True)

    commands: list[CommandResult] = []
    steps: list[ReplayStep] = []
    clone_source = get_clone_source()
    add_step(steps, "resolve_clone_source", "completed", clone_source)

    run_required(["git", "clone", clone_source, str(CLONE_DIR)], REPLAY_ROOT, commands)
    run_required(["git", "fetch", "--tags"], CLONE_DIR, commands)
    run_required(["git", "checkout", "--detach", BASELINE_TAG], CLONE_DIR, commands)
    clone_head = run_required(["git", "rev-parse", "HEAD"], CLONE_DIR, commands).strip()
    add_step(
        steps,
        "fresh_clone_checkout",
        "completed",
        f"Checked out {BASELINE_TAG} at {clone_head}",
    )

    env = replay_env()
    run_required(
        [sys.executable, "scripts/run_phase13o_local_runnable_operator_packaging.py"],
        CLONE_DIR,
        commands,
        env=env,
    )
    validation_output = run_required(
        [sys.executable, "scripts/validate_phase13o_local_runnable_operator_packaging.py"],
        CLONE_DIR,
        commands,
        env=env,
    )
    validation = parse_json_output(validation_output)
    add_step(
        steps,
        "regenerate_operator_pack_from_clone",
        "completed",
        "Phase 13O packager and validator passed inside fresh clone.",
    )

    pack_dir = CLONE_DIR / PACK_RELATIVE
    health = parse_json_output(
        run_required([sys.executable, "health_check.py"], pack_dir, commands, env=env)
    )
    demo = parse_json_output(
        run_required([sys.executable, "run_local_demo.py"], pack_dir, commands, env=env)
    )
    verifier = parse_json_output(
        run_required([sys.executable, "verify_operator_pack.py"], pack_dir, commands, env=env)
    )
    run_required(["bash", "run_operator_demo.sh"], pack_dir, commands, env=env)
    add_step(
        steps,
        "operator_handover_replay",
        "completed",
        "Health, demo, verifier, and one-command operator demo passed.",
    )

    if health.get("status") != "ok":
        raise RuntimeError("Fresh-clone health check was not ok.")
    if demo.get("status") != "RESOLVED":
        raise RuntimeError("Fresh-clone local demo did not resolve a dispute.")
    if verifier.get("passed") is not True:
        raise RuntimeError("Fresh-clone verifier did not pass.")
    if validation.get("passed") is not True:
        raise RuntimeError("Fresh-clone Phase 13O validation did not pass.")

    return {
        "clone_source": clone_source,
        "clone_head": clone_head,
        "baseline_tag": BASELINE_TAG,
        "replay_python": sys.executable,
        "replay_mode": "fresh_clone_reuse_current_python_environment",
        "operator_pack_dir": str(pack_dir),
        "commands": commands,
        "steps": steps,
        "health_status": str(health.get("status")),
        "demo_status": str(demo.get("status")),
        "verifier_passed": bool(verifier.get("passed")),
    }


def write_audit(state: ReplayState) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": "Phase 13P",
        "run_id": "phase13p_fresh_clone_handover_replay_001",
        "generated_at_utc": utc_now(),
        "baseline_tag": state["baseline_tag"],
        "clone_source": state["clone_source"],
        "clone_head": state["clone_head"],
        "replay_python": state["replay_python"],
        "replay_mode": state["replay_mode"],
        "operator_pack_dir": state["operator_pack_dir"],
        "health_status": state["health_status"],
        "demo_status": state["demo_status"],
        "verifier_passed": state["verifier_passed"],
        "commands": state["commands"],
        "steps": state["steps"],
        "passed": True,
        "truth_boundary": (
            "Fresh clone handover replay proves the generated local operator pack "
            "can be regenerated and run from the finalized tag. Primary UPI "
            "dispute lifecycle logic remains local and runnable; external "
            "ecosystem interfaces remain simulated mocks only."
        ),
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        "# Phase 13P Fresh Clone Handover Replay\n\n"
        "Status: `completed`\n\n"
        f"Baseline tag: `{state['baseline_tag']}`\n\n"
        f"Clone source: `{state['clone_source']}`\n\n"
        f"Clone HEAD: `{state['clone_head']}`\n\n"
        f"Replay mode: `{state['replay_mode']}`\n\n"
        "The replay regenerated the Phase 13O operator pack from a clean clone "
        "and ran health, lifecycle demo, verifier, and one-command handover demo.\n",
        encoding="utf-8",
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = write_audit(run_replay())
    result = {
        "passed": True,
        "phase": "Phase 13P",
        "baseline_tag": audit["baseline_tag"],
        "clone_head": audit["clone_head"],
        "replay_mode": audit["replay_mode"],
        "health_status": audit["health_status"],
        "demo_status": audit["demo_status"],
        "verifier_passed": audit["verifier_passed"],
        "operator_pack_dir": audit["operator_pack_dir"],
        "audit_path": relative(AUDIT_PATH),
    }
    if not args.quiet:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
