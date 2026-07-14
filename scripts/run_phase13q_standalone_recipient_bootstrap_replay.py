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

from langgraph.graph import END, START, StateGraph

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
REPLAY_ROOT = (
    PROJECT_ROOT.parent
    / "upi_app_factory_phase13q_recipient_bootstrap_workspace"
    / "fresh_clone_bootstrap_workspace"
)
CLONE_DIR = REPLAY_ROOT / "repo_clone"
RECIPIENT_VENV_DIR = CLONE_DIR / ".venv_recipient"
AUDIT_PATH = ARTIFACT_DIR / "standalone_recipient_bootstrap_replay_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "standalone_recipient_bootstrap_replay_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "standalone_recipient_bootstrap_replay_report.md"
PACK_RELATIVE = pathlib.Path(
    "workspace/factory_generated/upi_dispute_resolution/operator_handoff/"
    "phase13o_local_runnable_pack"
)
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements-recipient.txt"


class CommandResult(TypedDict):
    command: list[str]
    cwd: str
    return_code: int
    output_preview: str


class ReplayStep(TypedDict):
    name: str
    status: str
    detail: str


class BootstrapState(TypedDict, total=False):
    run_id: str
    clone_source: str
    clone_head: str
    bootstrap_ref: str
    recipient_python: str
    recipient_venv_dir: str
    workspace_reused: bool
    dependency_install_ran: bool
    operator_pack_dir: str
    commands: list[CommandResult]
    steps: list[ReplayStep]
    health_status: str
    demo_status: str
    verifier_passed: bool
    audit: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def add_step(
    state: BootstrapState,
    name: str,
    status: str,
    detail: str,
) -> list[ReplayStep]:
    steps = list(state.get("steps", []))
    steps.append({"name": name, "status": status, "detail": detail})
    return steps


def run_required(
    command: list[str],
    cwd: pathlib.Path,
    state: BootstrapState,
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
    commands = list(state.get("commands", []))
    commands.append(
        {
            "command": command,
            "cwd": str(cwd),
            "return_code": result.returncode,
            "output_preview": output[:4000],
        }
    )
    state["commands"] = commands
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {command}\n{output}"
        )
    return result.stdout


def get_clone_source() -> str:
    configured = os.environ.get("PHASE13Q_CLONE_SOURCE", "").strip()
    if configured:
        return configured
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    source = result.stdout.strip()
    if source:
        return source
    return str(PROJECT_ROOT)


def venv_python() -> pathlib.Path:
    if os.name == "nt":
        return RECIPIENT_VENV_DIR / "Scripts" / "python.exe"
    return RECIPIENT_VENV_DIR / "bin" / "python"


def recipient_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("MYPYPATH", None)
    env["PYTHONPATH"] = ":".join(
        [
            str(CLONE_DIR / "src"),
            str(CLONE_DIR / "scripts"),
            str(CLONE_DIR),
        ]
    )
    env["PYTHON_BIN"] = str(venv_python())
    return env


def parse_json_output(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    if not isinstance(payload, dict):
        raise RuntimeError("Expected command to produce a JSON object.")
    return cast(dict[str, Any], payload)


def force_clean_requested() -> bool:
    return os.environ.get("PHASE13Q_FORCE_CLEAN", "0") == "1"


def clone_checkout_agent(state: BootstrapState) -> BootstrapState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if force_clean_requested() and REPLAY_ROOT.exists():
        shutil.rmtree(REPLAY_ROOT)

    REPLAY_ROOT.mkdir(parents=True, exist_ok=True)
    workspace_reused = CLONE_DIR.exists()
    clone_source = get_clone_source()
    updated: BootstrapState = {
        **state,
        "clone_source": clone_source,
        "workspace_reused": workspace_reused,
    }

    if not CLONE_DIR.exists():
        run_required(["git", "clone", clone_source, str(CLONE_DIR)], REPLAY_ROOT, updated)
    run_required(["git", "fetch", "--tags"], CLONE_DIR, updated)
    run_required(["git", "checkout", "--detach", BASELINE_TAG], CLONE_DIR, updated)
    clone_head = run_required(["git", "rev-parse", "HEAD"], CLONE_DIR, updated).strip()

    target_requirements = CLONE_DIR / "requirements-recipient.txt"
    target_requirements.write_text(
        REQUIREMENTS_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    return {
        **updated,
        "clone_head": clone_head,
        "bootstrap_ref": BASELINE_TAG,
        "steps": add_step(
            updated,
            "clone_checkout_agent",
            "completed",
            f"Checked out {BASELINE_TAG} at {clone_head} and staged recipient requirements.",
        ),
    }


def dependency_bootstrap_agent(state: BootstrapState) -> BootstrapState:
    py = venv_python()
    updated: BootstrapState = {**state, "recipient_venv_dir": str(RECIPIENT_VENV_DIR)}
    if not py.exists():
        run_required([sys.executable, "-m", "venv", str(RECIPIENT_VENV_DIR)], CLONE_DIR, updated)

    probe = subprocess.run(
        [str(py), "-c", "import langgraph, pytest"],
        cwd=CLONE_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    dependency_install_ran = False
    if probe.returncode != 0:
        run_required(
            [str(py), "-m", "pip", "install", "-r", "requirements-recipient.txt"],
            CLONE_DIR,
            updated,
        )
        dependency_install_ran = True

    langgraph_version = run_required(
        [
            str(py),
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('langgraph'))",
        ],
        CLONE_DIR,
        updated,
    ).strip()
    pytest_version = run_required(
        [
            str(py),
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('pytest'))",
        ],
        CLONE_DIR,
        updated,
    ).strip()

    return {
        **updated,
        "recipient_python": str(py),
        "dependency_install_ran": dependency_install_ran,
        "steps": add_step(
            updated,
            "dependency_bootstrap_agent",
            "completed",
            f"Recipient venv ready with langgraph={langgraph_version}, pytest={pytest_version}.",
        ),
    }


def operator_pack_replay_agent(state: BootstrapState) -> BootstrapState:
    env = recipient_env()
    py = str(venv_python())
    updated: BootstrapState = {**state}
    run_required(
        [py, "scripts/run_phase13o_local_runnable_operator_packaging.py"],
        CLONE_DIR,
        updated,
        env=env,
    )
    validation = parse_json_output(
        run_required(
            [py, "scripts/validate_phase13o_local_runnable_operator_packaging.py"],
            CLONE_DIR,
            updated,
            env=env,
        )
    )
    if validation.get("passed") is not True:
        raise RuntimeError("Phase 13O validation inside recipient venv did not pass.")
    return {
        **updated,
        "operator_pack_dir": str(CLONE_DIR / PACK_RELATIVE),
        "steps": add_step(
            updated,
            "operator_pack_replay_agent",
            "completed",
            "Phase 13O operator pack regenerated and validated inside recipient venv.",
        ),
    }


def operator_demo_replay_agent(state: BootstrapState) -> BootstrapState:
    env = recipient_env()
    py = str(venv_python())
    pack_dir = CLONE_DIR / PACK_RELATIVE
    updated: BootstrapState = {**state}
    health = parse_json_output(
        run_required([py, "health_check.py"], pack_dir, updated, env=env)
    )
    demo = parse_json_output(
        run_required([py, "run_local_demo.py"], pack_dir, updated, env=env)
    )
    verifier = parse_json_output(
        run_required([py, "verify_operator_pack.py"], pack_dir, updated, env=env)
    )
    run_required(["bash", "run_operator_demo.sh"], pack_dir, updated, env=env)

    if health.get("status") != "ok":
        raise RuntimeError("Recipient health check was not ok.")
    if demo.get("status") != "RESOLVED":
        raise RuntimeError("Recipient local demo did not resolve a dispute.")
    if verifier.get("passed") is not True:
        raise RuntimeError("Recipient verifier did not pass.")

    return {
        **updated,
        "health_status": str(health.get("status")),
        "demo_status": str(demo.get("status")),
        "verifier_passed": bool(verifier.get("passed")),
        "steps": add_step(
            updated,
            "operator_demo_replay_agent",
            "completed",
            "Health, demo, verifier, and one-command demo passed in recipient venv.",
        ),
    }


def governance_evidence_agent(state: BootstrapState) -> BootstrapState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    steps = add_step(
        state,
        "governance_evidence_agent",
        "completed",
        "Standalone recipient bootstrap replay audit, manifest, and report written.",
    )
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": "Phase 13Q",
        "run_id": state["run_id"],
        "generated_at_utc": utc_now(),
        "baseline_tag": state.get("bootstrap_ref"),
        "clone_source": state.get("clone_source"),
        "clone_head": state.get("clone_head"),
        "replay_mode": "fresh_clone_new_recipient_venv",
        "workspace_reused": state.get("workspace_reused"),
        "dependency_install_ran": state.get("dependency_install_ran"),
        "recipient_venv_dir": state.get("recipient_venv_dir"),
        "recipient_python": state.get("recipient_python"),
        "operator_pack_dir": state.get("operator_pack_dir"),
        "health_status": state.get("health_status"),
        "demo_status": state.get("demo_status"),
        "verifier_passed": state.get("verifier_passed"),
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "graph_nodes": [
            "clone_checkout_agent",
            "dependency_bootstrap_agent",
            "operator_pack_replay_agent",
            "operator_demo_replay_agent",
            "governance_evidence_agent",
        ],
        "commands": state.get("commands", []),
        "steps": steps,
        "passed": True,
        "truth_boundary": (
            "Standalone recipient bootstrap replay proves a fresh clone can create "
            "a new recipient virtual environment, install the lightweight runtime, "
            "regenerate the local operator pack, and run the local UPI dispute "
            "lifecycle demo. External ecosystem interfaces remain simulated mocks only."
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
        "# Phase 13Q Standalone Recipient Bootstrap Replay\n\n"
        "Status: `completed`\n\n"
        f"Baseline tag: `{audit['baseline_tag']}`\n\n"
        f"Clone HEAD: `{audit['clone_head']}`\n\n"
        f"Replay mode: `{audit['replay_mode']}`\n\n"
        f"Recipient venv: `{audit['recipient_venv_dir']}`\n\n"
        "The replay created a recipient virtual environment in a fresh clone, "
        "installed lightweight runtime dependencies, regenerated the operator "
        "pack, and ran health/demo/verifier/one-command checks.\n",
        encoding="utf-8",
    )
    return {**state, "steps": steps, "audit": audit}


def build_graph() -> Any:
    graph = StateGraph(BootstrapState)
    graph.add_node("clone_checkout_agent", clone_checkout_agent)
    graph.add_node("dependency_bootstrap_agent", dependency_bootstrap_agent)
    graph.add_node("operator_pack_replay_agent", operator_pack_replay_agent)
    graph.add_node("operator_demo_replay_agent", operator_demo_replay_agent)
    graph.add_node("governance_evidence_agent", governance_evidence_agent)
    graph.add_edge(START, "clone_checkout_agent")
    graph.add_edge("clone_checkout_agent", "dependency_bootstrap_agent")
    graph.add_edge("dependency_bootstrap_agent", "operator_pack_replay_agent")
    graph.add_edge("operator_pack_replay_agent", "operator_demo_replay_agent")
    graph.add_edge("operator_demo_replay_agent", "governance_evidence_agent")
    graph.add_edge("governance_evidence_agent", END)
    return graph.compile()


def run_bootstrap_replay() -> dict[str, Any]:
    app = build_graph()
    final_state = cast(
        BootstrapState,
        app.invoke(
            {
                "run_id": "phase13q_standalone_recipient_bootstrap_replay_001",
                "commands": [],
                "steps": [],
            }
        ),
    )
    audit = final_state.get("audit")
    if not isinstance(audit, dict):
        raise SystemExit("Phase 13Q bootstrap replay did not produce an audit payload.")
    if audit.get("passed") is not True:
        print(json.dumps(audit, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = run_bootstrap_replay()
    result = {
        "passed": True,
        "phase": "Phase 13Q",
        "baseline_tag": audit["baseline_tag"],
        "clone_head": audit["clone_head"],
        "replay_mode": audit["replay_mode"],
        "recipient_python": audit["recipient_python"],
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
