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
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASE13M_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13m_dispute_lifecycle"
)
PACK_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "operator_handoff"
    / "phase13o_local_runnable_pack"
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
MANIFEST_PATH = ARTIFACT_DIR / "local_runnable_operator_pack_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "local_runnable_operator_pack_report.md"


class Step(TypedDict):
    node: str
    status: str
    detail: str


class CommandResult(TypedDict):
    command: list[str]
    return_code: int
    output_preview: str


class PackagingState(TypedDict, total=False):
    run_id: str
    generated_app_ready: bool
    operator_pack_dir: str
    generated_files: list[str]
    command_results: list[CommandResult]
    steps: list[Step]
    audit: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def add_step(state: PackagingState, node: str, status: str, detail: str) -> list[Step]:
    steps = list(state.get("steps", []))
    steps.append({"node": node, "status": status, "detail": detail})
    return steps


def run_command(command: list[str], cwd: pathlib.Path) -> CommandResult:
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
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout + result.stderr)[:4000]
    return {"command": command, "return_code": result.returncode, "output_preview": output}


def write_file(relative_path: str, content: str, *, executable: bool = False) -> pathlib.Path:
    path = PACK_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)
    return path


def operator_pack_files() -> dict[str, tuple[str, bool]]:
    return {
        "README.md": (
            """# Phase 13O Local Runnable Operator Pack

This pack is the lightweight local handover surface for the generated UPI dispute
lifecycle application. It is intentionally local-first: Python 3.10, the existing
project virtual environment, filesystem evidence, and no Kubernetes or external
payment-network dependencies.

The primary generated UPI dispute lifecycle logic is local and runnable. External
banks, rails, NPCI-style, RBI-style, upstream, and downstream interfaces remain
simulated mock boundaries only.

## One-command demo

```bash
cd workspace/factory_generated/upi_dispute_resolution/operator_handoff/phase13o_local_runnable_pack
./run_operator_demo.sh
```

## Individual commands

```bash
python3 health_check.py
python3 run_local_demo.py
python3 verify_operator_pack.py
python3 run_http_server.py --host 127.0.0.1 --port 8765
```

Then, from another terminal:

```bash
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/demo/dispute-lifecycle
```

## Expected result

The local demo creates a dispute case, validates evidence, receives a simulated
mock investigation response, proposes a customer-credit recommendation, finalizes
resolution, and returns an audit trail.
""",
            False,
        ),
        "HANDOVER.md": (
            """# Operator Handover

## Purpose

This handover pack lets another operator run the generated UPI dispute lifecycle
application locally without needing real UPI rails, banks, NPCI-style services,
RBI-style interfaces, upstream systems, or downstream systems.

## Runtime profile

- Python 3.10
- Existing project `.venv`
- Filesystem evidence
- Generated Phase 13M lifecycle package
- Optional stdlib HTTP demo server

## Acceptance checks

Run:

```bash
./run_operator_demo.sh
```

The check passes only when health, local demo, and operator verification all
succeed.
""",
            False,
        ),
        "operator_runtime.py": (
            """from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[5]
PHASE13M_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
    / "phase13m_dispute_lifecycle"
)
if str(PHASE13M_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE13M_APP_DIR))

from phase13m_dispute_lifecycle_app.api import create_case, progress_case_to_resolution


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "runtime": "local_python_stdlib",
        "generated_app_dir": str(PHASE13M_APP_DIR),
        "boundary_statement": (
            "Primary generated UPI dispute lifecycle logic is local and runnable; "
            "external ecosystem interfaces are simulated mocks only."
        ),
    }


def demo_payload() -> dict[str, Any]:
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return {
        "transaction_id": f"TXN-13O-DEMO-{suffix}",
        "payer_vpa": "payer@upi",
        "payee_vpa": "merchant@upi",
        "amount_paise": 9900,
        "evidence_refs": ["phase13o:operator-demo", "phase13o:customer-note"],
    }


def run_demo_lifecycle() -> dict[str, Any]:
    created = create_case(demo_payload())
    return progress_case_to_resolution(str(created["case_id"]))
""",
            False,
        ),
        "health_check.py": (
            """from __future__ import annotations

import json

from operator_runtime import health

print(json.dumps(health(), indent=2, sort_keys=True))
""",
            False,
        ),
        "run_local_demo.py": (
            """from __future__ import annotations

import json

from operator_runtime import run_demo_lifecycle

print(json.dumps(run_demo_lifecycle(), indent=2, sort_keys=True))
""",
            False,
        ),
        "verify_operator_pack.py": (
            """from __future__ import annotations

import json

from operator_runtime import health, run_demo_lifecycle

health_payload = health()
resolved = run_demo_lifecycle()
errors: list[str] = []

if health_payload.get("status") != "ok":
    errors.append("health_not_ok")
if resolved.get("status") != "RESOLVED":
    errors.append("case_not_resolved")
if not str(resolved.get("mock_investigation_reference", "")).startswith("MOCK-INV-"):
    errors.append("missing_mock_investigation_reference")
if len(resolved.get("audit_trail", [])) < 5:
    errors.append("audit_trail_too_short")
if "simulated mocks only" not in str(resolved.get("boundary_statement", "")):
    errors.append("missing_mock_boundary_statement")

payload = {
    "passed": not errors,
    "errors": errors,
    "health": health_payload,
    "resolved_status": resolved.get("status"),
    "resolution_outcome": resolved.get("resolution_outcome"),
    "audit_event_count": len(resolved.get("audit_trail", [])),
}
print(json.dumps(payload, indent=2, sort_keys=True))
if errors:
    raise SystemExit(1)
""",
            False,
        ),
        "run_http_server.py": (
            """from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from operator_runtime import health, run_demo_lifecycle


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, health())
            return
        self._send(404, {"error": "not_found", "path": self.path})

    def do_POST(self) -> None:
        if self.path == "/demo/dispute-lifecycle":
            self._send(200, run_demo_lifecycle())
            return
        self._send(404, {"error": "not_found", "path": self.path})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Serving Phase 13O local demo on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
""",
            False,
        ),
        "run_operator_demo.sh": (
            """#!/usr/bin/env bash
set -Eeuo pipefail
PYTHON_BIN="${PYTHON_BIN:-python3}"
cd "$(dirname "$0")"
"$PYTHON_BIN" health_check.py
"$PYTHON_BIN" run_local_demo.py
"$PYTHON_BIN" verify_operator_pack.py
""",
            True,
        ),
        "local_runtime_manifest.json": (
            json.dumps(
                {
                    "phase": "Phase 13O",
                    "runtime_profile": "local_python_stdlib",
                    "requires_real_payment_rails": False,
                    "requires_kubernetes": False,
                    "requires_database": False,
                    "operator_commands": [
                        "./run_operator_demo.sh",
                        "python3 health_check.py",
                        "python3 run_local_demo.py",
                        "python3 verify_operator_pack.py",
                        "python3 run_http_server.py --host 127.0.0.1 --port 8765",
                    ],
                    "truth_boundary": (
                        "Primary generated UPI dispute lifecycle logic is local and runnable; "
                        "external ecosystem interfaces are simulated mocks only."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            False,
        ),
    }


def ensure_phase13m_generated(state: PackagingState) -> PackagingState:
    command = [
        sys.executable,
        "scripts/run_phase13m_langgraph_agentic_lifecycle_generation.py",
        "--quiet",
    ]
    result = run_command(command, PROJECT_ROOT)
    if result["return_code"] != 0:
        raise RuntimeError(f"Phase 13M generation failed: {result['output_preview']}")
    return {
        **state,
        "generated_app_ready": True,
        "command_results": list(state.get("command_results", [])) + [result],
        "steps": add_step(
            state,
            "generated_app_proof_agent",
            "completed",
            "Phase 13M generated lifecycle application was regenerated locally.",
        ),
    }


def operator_pack_agent(state: PackagingState) -> PackagingState:
    if PACK_DIR.exists():
        shutil.rmtree(PACK_DIR)
    files = operator_pack_files()
    generated_paths = [
        write_file(path, content, executable=executable)
        for path, (content, executable) in files.items()
    ]
    return {
        **state,
        "operator_pack_dir": relative(PACK_DIR),
        "generated_files": [relative(path) for path in generated_paths],
        "steps": add_step(
            state,
            "operator_pack_agent",
            "completed",
            "Local runnable operator pack, README, health check, demo, HTTP server, and verifier generated.",
        ),
    }


def smoke_verification_agent(state: PackagingState) -> PackagingState:
    commands = [
        [sys.executable, "health_check.py"],
        [sys.executable, "run_local_demo.py"],
        [sys.executable, "verify_operator_pack.py"],
        ["bash", "run_operator_demo.sh"],
    ]
    results = [run_command(command, PACK_DIR) for command in commands]
    if not all(result["return_code"] == 0 for result in results):
        raise RuntimeError("One or more Phase 13O operator smoke commands failed.")
    return {
        **state,
        "command_results": list(state.get("command_results", [])) + results,
        "steps": add_step(
            state,
            "smoke_verification_agent",
            "completed",
            "Health, local demo, verifier, and one-command operator demo passed.",
        ),
    }


def governance_evidence_agent(state: PackagingState) -> PackagingState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    steps = add_step(
        state,
        "governance_evidence_agent",
        "completed",
        "Operator handover audit, manifest, and report written.",
    )
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": "Phase 13O",
        "run_id": state["run_id"],
        "generated_at_utc": utc_now(),
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "adapter_mode": "local_langgraph_deterministic",
        "purpose": "local_runnable_operator_packaging",
        "graph_nodes": [
            "generated_app_proof_agent",
            "operator_pack_agent",
            "smoke_verification_agent",
            "governance_evidence_agent",
        ],
        "operator_pack_dir": state.get("operator_pack_dir"),
        "generated_files": state.get("generated_files", []),
        "command_results": state.get("command_results", []),
        "steps": steps,
        "validation": {
            "health_check_passed": True,
            "local_demo_passed": True,
            "operator_pack_verifier_passed": True,
            "one_command_demo_passed": True,
        },
        "truth_boundary": (
            "Primary generated UPI dispute lifecycle logic is local and runnable; "
            "external banks, rails, NPCI-style, RBI-style, upstream, and "
            "downstream interfaces remain simulated mocks only."
        ),
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "# Phase 13O Local Runnable Operator Pack\n\n"
        "Status: `completed`\n\n"
        f"Run ID: `{state['run_id']}`\n\n"
        "This phase packages the generated UPI dispute lifecycle application into "
        "a lightweight local operator handover pack.\n\n"
        f"Operator pack: `{state.get('operator_pack_dir')}`\n\n"
        "One-command demo: `./run_operator_demo.sh`\n\n"
        f"Truth boundary: {audit['truth_boundary']}\n",
        encoding="utf-8",
    )
    return {**state, "steps": steps, "audit": audit}


def build_graph() -> Any:
    graph = StateGraph(PackagingState)
    graph.add_node("generated_app_proof_agent", ensure_phase13m_generated)
    graph.add_node("operator_pack_agent", operator_pack_agent)
    graph.add_node("smoke_verification_agent", smoke_verification_agent)
    graph.add_node("governance_evidence_agent", governance_evidence_agent)
    graph.add_edge(START, "generated_app_proof_agent")
    graph.add_edge("generated_app_proof_agent", "operator_pack_agent")
    graph.add_edge("operator_pack_agent", "smoke_verification_agent")
    graph.add_edge("smoke_verification_agent", "governance_evidence_agent")
    graph.add_edge("governance_evidence_agent", END)
    return graph.compile()


def run_packaging() -> dict[str, Any]:
    app = build_graph()
    final_state = cast(
        PackagingState,
        app.invoke(
            {
                "run_id": "phase13o_local_runnable_operator_packaging_001",
                "steps": [],
                "command_results": [],
            }
        ),
    )
    audit = final_state.get("audit")
    if not isinstance(audit, dict):
        raise SystemExit("Phase 13O packaging did not produce an audit payload.")
    validation = audit.get("validation", {})
    if not isinstance(validation, dict) or not all(validation.values()):
        print(json.dumps(audit, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = run_packaging()
    result = {
        "passed": True,
        "phase": "Phase 13O",
        "orchestration_framework": audit["orchestration_framework"],
        "graph_type": audit["graph_type"],
        "operator_pack_dir": audit["operator_pack_dir"],
        "audit_path": relative(AUDIT_PATH),
        "one_command_demo": "./run_operator_demo.sh",
        "health_check": "python3 health_check.py",
        "local_demo": "python3 run_local_demo.py",
        "verifier": "python3 verify_operator_pack.py",
    }
    if not args.quiet:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
