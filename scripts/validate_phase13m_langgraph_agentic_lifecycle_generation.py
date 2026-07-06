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
GEN_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13m_dispute_lifecycle"
)
PACKAGE_NAME = "phase13m_dispute_lifecycle_app"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13m"
)
AUDIT_PATH = ARTIFACT_DIR / "langgraph_agentic_lifecycle_audit.json"


def one_line(text: str) -> str:
    return " ".join(text.split())


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.exists():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def require_file(relative_path: str) -> pathlib.Path:
    path = GEN_APP_DIR / relative_path
    if not path.is_file():
        raise AssertionError(f"Missing generated file: {path}")
    return path


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=GEN_APP_DIR,
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


def validate_content() -> None:
    required = [
        "README.md",
        f"{PACKAGE_NAME}/__init__.py",
        f"{PACKAGE_NAME}/domain.py",
        f"{PACKAGE_NAME}/external_mocks.py",
        f"{PACKAGE_NAME}/service.py",
        f"{PACKAGE_NAME}/api.py",
        "checks/dispute_lifecycle_checks.py",
        "scripts/run_demo.py",
    ]
    for relative_path in required:
        require_file(relative_path)

    readme = one_line(require_file("README.md").read_text(encoding="utf-8"))
    service = require_file(f"{PACKAGE_NAME}/service.py").read_text(encoding="utf-8")
    domain = require_file(f"{PACKAGE_NAME}/domain.py").read_text(
        encoding="utf-8"
    )
    mocks = require_file(f"{PACKAGE_NAME}/external_mocks.py").read_text(
        encoding="utf-8"
    )
    checks = require_file("checks/dispute_lifecycle_checks.py").read_text(
        encoding="utf-8"
    )

    if "real LangGraph StateGraph" not in readme:
        raise AssertionError(
            "README does not document real LangGraph StateGraph orchestration."
        )
    if "local runnable UPI dispute-resolution lifecycle slice" not in readme:
        raise AssertionError("README does not describe the local runnable lifecycle slice.")
    boundary_sources = "\n".join([readme, service, domain, mocks])
    if "simulated mocks only" not in boundary_sources:
        raise AssertionError("Generated application does not preserve mock boundary wording.")
    if "performs no real rail call" not in mocks:
        raise AssertionError("Mock client does not declare no real rail call.")
    if PACKAGE_NAME not in checks:
        raise AssertionError("Generated checks do not import the isolated package.")


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != "Phase 13M":
        raise AssertionError("Audit phase is not Phase 13M.")
    if audit.get("orchestration_framework") != "langgraph":
        raise AssertionError("Audit does not record LangGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit does not record StateGraph graph type.")
    if audit.get("generated_package") != PACKAGE_NAME:
        raise AssertionError("Audit does not record the isolated generated package.")
    if audit.get("adapter_mode") != "local_langgraph_deterministic":
        raise AssertionError("Phase 13M must use local LangGraph deterministic mode.")
    validation = audit.get("validation", {})
    if (
        not isinstance(validation, dict)
        or validation.get("generated_checks_passed") is not True
    ):
        raise AssertionError("Audit does not show generated lifecycle checks passed.")
    nodes = audit.get("graph_nodes", [])
    if not isinstance(nodes, list) or len(nodes) < 7:
        raise AssertionError("Audit does not capture the expected LangGraph nodes.")
    conditional_edges = audit.get("conditional_edges", [])
    if not any("self_correction_agent" in str(edge) for edge in conditional_edges):
        raise AssertionError("Audit does not capture the self-correction route.")
    boundary = str(audit.get("truth_boundary", ""))
    for term in ["local and runnable", "simulated mocks only"]:
        if term not in boundary:
            raise AssertionError(f"Missing truth-boundary term: {term}")


def validate_runtime() -> tuple[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{GEN_APP_DIR}:{env.get('PYTHONPATH', '')}"
    demo = run_command([sys.executable, "scripts/run_demo.py"], env=env)
    checks = run_command(
        [sys.executable, "-m", "pytest", "-q", "checks/dispute_lifecycle_checks.py"],
        env=env,
    )
    return demo, checks


def main() -> None:
    audit = load_audit()
    validate_content()
    validate_audit(audit)
    demo, checks = validate_runtime()
    result = {
        "passed": True,
        "phase": "Phase 13M",
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "generated_application_dir": str(GEN_APP_DIR),
        "generated_package": PACKAGE_NAME,
        "audit_path": str(AUDIT_PATH),
        "demo_output_preview": demo[:1000],
        "pytest_output": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
