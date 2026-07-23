#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA_VERSION = "upi-app-factory.factory-documentation.v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {"path": relative, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _diagram(title: str, desc: str, labels: list[str]) -> str:
    width = 760
    step = width // max(1, len(labels))
    nodes = []
    edges = []
    for index, label in enumerate(labels):
        x = 25 + index * step
        nodes.append(
            f'<rect x="{x}" y="34" width="{max(110, step - 25)}" height="58" rx="6"/>'
            f'<text x="{x + 12}" y="68">{escape(label)}</text>'
        )
        if index:
            edges.append(f'<path d="M{x - 24} 63 H{x - 4}" marker-end="url(#{escape(title).replace(" ", "-")}-arrow)"/>')
    return (
        f'<svg role="img" viewBox="0 0 {width} 128" aria-labelledby="{escape(title)}-title {escape(title)}-desc">'
        f'<title id="{escape(title)}-title">{escape(title)}</title>'
        f'<desc id="{escape(title)}-desc">{escape(desc)}</desc>'
        f'<defs><marker id="{escape(title).replace(" ", "-")}-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L8,3 z"/></marker></defs>'
        f'{"".join(edges)}{"".join(nodes)}</svg>'
    )


def _list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def build_documentation(root: Path, ui_manifest: dict[str, Any], debug_plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    source_paths = [
        "factory/operator_portal/local_web_api.py",
        "factory/operator_portal/debug_plan_api.py",
        "factory/operator_portal/documentation_api.py",
        "factory/operator_portal/web_ui/app.py",
        "factory/operator_portal/web_ui/static/index.html",
        "factory/operator_portal/web_ui/static/app.js",
        "factory/operator_portal/browser_intake_orchestration.py",
        "factory/debugging/debug_plan.py",
        "factory/operator_portal/portfolio_api.py",
        "factory/operator_portal/runtime_api.py",
        "scripts/run_portal_requirements_driven_application_engineering.py",
        "scripts/build_factory_debug_plan.py",
        "scripts/validate_debug_plan.py",
        "scripts/build_operator_portal_exhaustive_ui_manifest.py",
        "scripts/build_factory_complete_documentation.py",
        "start_factory.sh",
        "stop_factory.sh",
        "config/factory_runtime.env.example",
    ]
    missing = [path for path in source_paths if not (root / path).is_file()]
    if missing:
        raise ValueError("documentation source inputs missing: " + ", ".join(missing))
    trace_sources = [_source(root, path) for path in source_paths]

    controls = ui_manifest.get("controls", [])
    routes = ui_manifest.get("routes", [])
    if not controls or not routes:
        raise ValueError("UI manifest must expose controls and routes")
    source_files = debug_plan.get("source_files", [])
    if not source_files:
        raise ValueError("debug plan must expose source files")

    controls_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('id', '')))}</td>"
        f"<td>{escape(str(item.get('action') or item.get('link') or ''))}</td>"
        f"<td>{escape(str(item.get('contract', {}).get('method', '')))}</td>"
        f"<td>{escape(str(item.get('contract', {}).get('route', '')))}</td>"
        f"<td>{escape(', '.join(item.get('executed_behaviors', [])))}</td>"
        "</tr>"
        for item in controls
    )
    route_items = [f"{item.get('method')} {item.get('route')}" for item in routes]
    source_items = [f"{item['path']} {item['sha256']}" for item in source_files]
    diagrams = [
        _diagram("System Context", "Operator, portal, local workspace, and generated applications.", ["Operator", "Portal UI", "FastAPI API", "Workspace", "Generated App"]),
        _diagram("Component Architecture", "Portal components and supporting services.", ["Web UI", "Debug Plan", "Docs API", "Runtime API", "Portfolio"]),
        _diagram("Agent Task Ownership", "Repository agent artifacts and governed tasks.", ["Requirements", "Planning", "Engineering", "Validation", "Evidence"]),
        _diagram("Engineering Sequence", "Browser run lifecycle from validation to catalogue.", ["Validate", "Plan", "Approve", "Execute", "Publish"]),
        _diagram("Portal State Control Flow", "Controls follow run and runtime state.", ["DRAFT", "PLAN_READY", "APPROVED", "SUCCEEDED"]),
        _diagram("Diagnostic Decision Flow", "Debugging signals lead to safe local actions.", ["Symptom", "Evidence", "Validate", "Rollback", "Escalate"]),
    ]
    css = (
        "body{font-family:Arial,sans-serif;margin:0;color:#172026;background:#f7f8fa}"
        "header,section{padding:24px 32px}header{background:#12343b;color:white}"
        "h1,h2{margin:0 0 12px}table{border-collapse:collapse;width:100%;background:white}"
        "td,th{border:1px solid #cfd8dc;padding:8px;text-align:left;vertical-align:top}"
        "code{background:#eef2f3;padding:2px 4px}svg{width:100%;max-width:900px;margin:10px 0;background:white;border:1px solid #cfd8dc}"
        "svg rect{fill:#e9f3ef;stroke:#245b4f}svg path{stroke:#245b4f;stroke-width:2}svg text{font-size:13px;fill:#172026}"
    )
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>UPI App Factory Complete Guide</title><style>"
        + css
        + "</style></head><body><header><h1>UPI App Factory Complete Guide</h1>"
        "<p>Self-contained local operator guide generated from repository source, UI manifest, and debug plan evidence.</p></header>"
        "<section><h2>Purpose, Scope, Trust Boundaries, and Configuration</h2>"
        "<p>UPI App Factory provides deterministic local application engineering through an operator portal. Scope is local, mocked or simulated payment ecosystems only, with no certification claim.</p>"
        + _list(["Loopback operator portal", "Repository workspace artifacts", "Generated mock-safe applications", "Real payment calls disabled", "Runtime LLM calls zero"])
        + "<p>Configuration is provided by <code>config/factory_runtime.env.example</code>: host, port, state root, and log level.</p></section>"
        "<section><h2>Diagrams</h2>" + "".join(diagrams) + "</section>"
        "<section><h2>Components, APIs, and Flows</h2>"
        "<p>The portal API, web UI, portfolio API, runtime API, debug-plan API, documentation API, and deterministic generator are traced in the manifest.</p>"
        "<h3>Routes</h3>" + _list(route_items)
        + "<h3>Debug Plan Source Files</h3>" + _list(source_items[:40]) + "</section>"
        "<section><h2>Agents and Task Ownership</h2>"
        "<p>Source-derived agent prompt files and lifecycle tools define requirements analysis, architecture, implementation, validation, documentation, release readiness, governance review, and mock ecosystem tasks.</p>"
        + _list(["Inputs: requirements and local policy files", "Outputs: source, tests, evidence, manifests", "Tools: deterministic Python builders and validators", "Approvals: run-scoped human approval only", "Failure behavior: fail closed with evidence"])
        + "</section>"
        "<section><h2>Operator Portal Inventory</h2>"
        "<table><thead><tr><th>Control</th><th>Action</th><th>Method</th><th>Route</th><th>Executed Behavior</th></tr></thead><tbody>"
        + controls_rows
        + "</tbody></table></section>"
        "<section><h2>Debugging, Observability, Security, Rollback, Evidence, and Escalation</h2>"
        "<p>Factory and generated-application debugging procedures are defined by the debug plan. Logs follow structured JSON fields including trace, request, correlation, run, app, version, duration, and outcome fields. Secret and PII redaction remains active.</p>"
        + _list([str(uri) for uri in debug_plan.get("observability", {}).get("standards", [])])
        + "<p>Rollback is local artifact cleanup or process stop only; deployment, merge, tag, push, live providers, and certification claims are outside this guide.</p></section>"
        "<section><h2>Start, Stop, Usage, and Glossary</h2>"
        "<p>Start with <code>./start_factory.sh</code>; stop with <code>./stop_factory.sh</code>. Defaults bind to loopback and write PID/log files under XDG state.</p>"
        + _list(["Run: approved browser application engineering instance", "Plan hash: canonical SHA-256 over debug plan content", "GO: local validation-derived generated application decision", "Mock-safe: no live payment provider calls"])
        + "</section></body></html>\n"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": "1970-01-01T00:00:00Z",
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "source_traceability": trace_sources,
        "ui_manifest_sha256": hashlib.sha256(json.dumps(ui_manifest, sort_keys=True).encode("utf-8")).hexdigest(),
        "debug_plan_sha256": debug_plan.get("plan_sha256"),
        "controls_traced": len(controls),
        "routes_traced": len(routes),
        "diagrams": [
            "system context",
            "component architecture",
            "agent/task ownership",
            "engineering sequence",
            "portal state/control flow",
            "diagnostic decision flow",
        ],
    }
    return html, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--ui-manifest", type=Path, required=True)
    parser.add_argument("--debug-plan", type=Path, required=True)
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    html, manifest = build_documentation(root, _load_json(args.ui_manifest), _load_json(args.debug_plan))
    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(html, encoding="utf-8")
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
