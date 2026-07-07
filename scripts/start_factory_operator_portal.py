#!/usr/bin/env python3
"""Start the local Factory Operator Portal.

The Phase 13AW portal is read-only. It displays status and evidence metadata,
but does not execute arbitrary commands or mutate protected targets.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402

from scripts.build_local_operator_portal_status import (  # noqa: E402
    build_local_operator_portal_status,
)


def _html_escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _status_card(title: str, body: str) -> str:
    return f"""
    <section class="card">
      <h2>{_html_escape(title)}</h2>
      <p>{_html_escape(body)}</p>
    </section>
    """


def render_dashboard(status: dict[str, Any]) -> str:
    """Render a simple local dashboard."""

    health = status["factory_health"]
    evidence = status["evidence_summary"]
    safe_commands = status["safe_command_catalog"]

    command_rows = "\n".join(
        f"<tr><td>{_html_escape(command['command_id'])}</td>"
        f"<td><code>{_html_escape(command['command'])}</code></td>"
        f"<td>{_html_escape(command['execution_enabled_in_portal'])}</td></tr>"
        for command in safe_commands
    )

    cards = "\n".join(
        [
            _status_card("Portal Status", str(health["portal_status"])),
            _status_card("Current Branch", str(health["current_branch"])),
            _status_card("Latest Tag", str(health["latest_tag"])),
            _status_card(
                "Evidence Summary",
                f"all_required_evidence_present={evidence['all_required_evidence_present']}",
            ),
            _status_card(
                "Self-Healing",
                f"worktree_auto_repair_enabled={status['self_healing_summary']['worktree_auto_repair_enabled']}",
            ),
            _status_card(
                "Agentic Threat Tests",
                f"live_provider_calls_enabled={status['agentic_threat_summary']['live_provider_calls_enabled']}",
            ),
        ]
    )

    status_json = json.dumps(status, indent=2, sort_keys=True)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Factory Operator Portal</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f7f7f7; color: #1f2937; }}
    header {{ margin-bottom: 1.5rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
    .card {{ background: white; border: 1px solid #ddd; border-radius: 10px; padding: 1rem; }}
    code, pre {{ background: #111827; color: #f9fafb; padding: 0.15rem 0.3rem; border-radius: 4px; }}
    pre {{ overflow: auto; padding: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    .warning {{ background: #fff7ed; border: 1px solid #fed7aa; padding: 1rem; border-radius: 10px; }}
  </style>
</head>
<body>
  <header>
    <h1>Factory Operator Portal</h1>
    <p>Local read-only dashboard for governed application engineering.</p>
  </header>
  <div class="warning">
    Portal command execution is disabled in Phase 13AW. Run commands manually in terminal after review.
  </div>
  <main>
    <div class="grid">{cards}</div>
    <h2>Safe Command Catalog</h2>
    <table>
      <thead><tr><th>ID</th><th>Command</th><th>Portal Execution Enabled</th></tr></thead>
      <tbody>{command_rows}</tbody>
    </table>
    <h2>Status JSON</h2>
    <pre>{_html_escape(status_json)}</pre>
  </main>
</body>
</html>
"""


def create_app(project_root: Path | None = None) -> FastAPI:
    """Create the read-only FastAPI portal app."""

    root = (project_root or Path.cwd()).resolve()
    app = FastAPI(title="Factory Operator Portal", version="phase13aw")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "read-only", "phase": "13AW"}

    @app.get("/api/status")
    def api_status() -> dict[str, Any]:
        return build_local_operator_portal_status(root)

    @app.get("/api/evidence")
    def api_evidence() -> dict[str, Any]:
        status = build_local_operator_portal_status(root)
        evidence_summary = status.get("evidence_summary")
        if isinstance(evidence_summary, dict):
            return evidence_summary
        return {"all_required_evidence_present": False, "items": {}}

    @app.get("/api/safe-commands")
    def api_safe_commands() -> list[dict[str, object]]:
        status = build_local_operator_portal_status(root)
        safe_commands = status.get("safe_command_catalog")
        if not isinstance(safe_commands, list):
            return []

        typed_commands: list[dict[str, object]] = []
        for command in safe_commands:
            if isinstance(command, dict):
                typed_commands.append(dict(command))
        return typed_commands

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return render_dashboard(build_local_operator_portal_status(root))

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local Factory Operator Portal.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    if args.host != "127.0.0.1":
        print("ERROR: Phase 13AW portal only allows host 127.0.0.1.", file=sys.stderr)
        return 1

    import uvicorn

    uvicorn.run(create_app(args.project_root), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
