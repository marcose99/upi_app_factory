#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "operator_handoff"
    / "phase13o_local_runnable_pack"
)
PHASE13M_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13m_dispute_lifecycle"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13o"
)
AUDIT_PATH = ARTIFACT_DIR / "local_runnable_operator_pack_audit.json"
REQUIRED_FILES = [
    "README.md",
    "HANDOVER.md",
    "operator_runtime.py",
    "health_check.py",
    "run_local_demo.py",
    "verify_operator_pack.py",
    "run_http_server.py",
    "run_operator_demo.sh",
    "local_runtime_manifest.json",
]


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def require_file(relative_path: str) -> pathlib.Path:
    path = PACK_DIR / relative_path
    if not path.is_file():
        raise AssertionError(f"Missing operator pack file: {path}")
    return path


def run_command(command: list[str]) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(PHASE13M_APP_DIR),
            str(PACK_DIR),
            str(PROJECT_ROOT / "src"),
            str(PROJECT_ROOT / "scripts"),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        command,
        cwd=PACK_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Command failed:\n"
            f"command={command}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result.stdout


def validate_files() -> None:
    for relative_path in REQUIRED_FILES:
        require_file(relative_path)
    readme = require_file("README.md").read_text(encoding="utf-8")
    handover = require_file("HANDOVER.md").read_text(encoding="utf-8")
    manifest = json.loads(require_file("local_runtime_manifest.json").read_text(encoding="utf-8"))
    expected_phrases = [
        "./run_operator_demo.sh",
        "python3 health_check.py",
        "python3 run_local_demo.py",
        "python3 verify_operator_pack.py",
        "run_http_server.py",
        "simulated mock boundaries only",
    ]
    combined = readme + "\n" + handover
    for phrase in expected_phrases:
        if phrase not in combined:
            raise AssertionError(f"Missing operator documentation phrase: {phrase}")
    if manifest.get("requires_real_payment_rails") is not False:
        raise AssertionError("Manifest must not require real payment rails.")
    if manifest.get("requires_kubernetes") is not False:
        raise AssertionError("Manifest must not require Kubernetes.")


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != "Phase 13O":
        raise AssertionError("Audit phase is not Phase 13O.")
    if audit.get("orchestration_framework") not in {"langgraph", "stdlib_state_graph"}:
        raise AssertionError("Audit does not record a governed StateGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit does not record StateGraph graph type.")
    validation = audit.get("validation", {})
    if not isinstance(validation, dict) or not all(validation.values()):
        raise AssertionError("Audit validation flags are not all true.")
    nodes = audit.get("graph_nodes", [])
    for required in [
        "generated_app_proof_agent",
        "operator_pack_agent",
        "smoke_verification_agent",
        "governance_evidence_agent",
    ]:
        if required not in nodes:
            raise AssertionError(f"Missing graph node: {required}")
    boundary = str(audit.get("truth_boundary", ""))
    if "local and runnable" not in boundary or "simulated mocks only" not in boundary:
        raise AssertionError("Audit truth boundary is incomplete.")


def validate_runtime() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    health = json.loads(run_command([sys.executable, "health_check.py"]))
    demo = json.loads(run_command([sys.executable, "run_local_demo.py"]))
    verifier = json.loads(run_command([sys.executable, "verify_operator_pack.py"]))
    shell_output = run_command(["bash", "run_operator_demo.sh"])
    if health.get("status") != "ok":
        raise AssertionError("Health check did not return ok.")
    if demo.get("status") != "RESOLVED":
        raise AssertionError("Local demo did not resolve the dispute case.")
    if verifier.get("passed") is not True:
        raise AssertionError("Operator verifier did not pass.")
    if "RESOLVED" not in shell_output:
        raise AssertionError("One-command demo output did not include RESOLVED.")
    return health, demo, verifier, shell_output


def main() -> None:
    audit = load_audit()
    validate_files()
    validate_audit(audit)
    health, demo, verifier, shell_output = validate_runtime()
    result = {
        "passed": True,
        "phase": "Phase 13O",
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "operator_pack_dir": str(PACK_DIR),
        "audit_path": str(AUDIT_PATH),
        "health_status": health.get("status"),
        "demo_status": demo.get("status"),
        "verifier_passed": verifier.get("passed"),
        "one_command_output_preview": shell_output[:1000],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
