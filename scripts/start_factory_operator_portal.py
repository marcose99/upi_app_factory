#!/usr/bin/env python3
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

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from scripts.build_guided_requirement_intake_preview import build_requirement_intake_preview
from scripts.build_local_operator_portal_status import build_local_operator_portal_status
from scripts.build_operator_portal_dashboard_panels import build_operator_portal_dashboard_panels


def _html_escape(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _style() -> str:
    return """
    body { font-family: system-ui, sans-serif; margin: 2rem; background: #f7f7f7; color: #1f2937; }
    header { margin-bottom: 1.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
    .card { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 1rem; }
    code, pre { background: #111827; color: #f9fafb; padding: 0.15rem 0.3rem; border-radius: 4px; }
    pre { overflow: auto; padding: 1rem; }
    table { width: 100%; border-collapse: collapse; background: white; margin-top: 1rem; }
    th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
    .warning { background: #fff7ed; border: 1px solid #fed7aa; padding: 1rem; border-radius: 10px; }
    """


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_html_escape(title)}</title>
  <style>{_style()}</style>
</head>
<body>
  <header>
    <h1>{_html_escape(title)}</h1>
    <p><a href="/">Home</a> · <a href="/requirements">Requirements</a> · <a href="/dashboards">Dashboards</a></p>
  </header>
  <div class="warning">Portal command execution is disabled. Portal execution remains disabled. Dashboards are read-only.</div>
  {body}
</body>
</html>"""


def _status_card(title: str, body: str) -> str:
    return f'<section class="card"><h2>{_html_escape(title)}</h2><p>{_html_escape(body)}</p></section>'


def _panel_cards(status: dict[str, object]) -> str:
    panels = status.get("panels")
    if not isinstance(panels, list):
        return "<p>No panels available.</p>"
    cards: list[str] = []
    for item in panels:
        if not isinstance(item, dict):
            continue
        panel_id = str(item.get("panel_id", "unknown"))
        title = str(item.get("title", panel_id))
        summary = str(item.get("summary", ""))
        state = str(item.get("status", "UNKNOWN"))
        cards.append(_status_card(title, f"{state}: {summary}"))
    return '<div class="grid">' + "\n".join(cards) + "</div>"


def _panel_detail(status: dict[str, object], panel_id: str) -> str:
    panels = status.get("panels")
    if not isinstance(panels, list):
        return "<p>No panels available.</p>"
    for item in panels:
        if isinstance(item, dict) and item.get("panel_id") == panel_id:
            return "<pre>" + _html_escape(json.dumps(item, indent=2, sort_keys=True)) + "</pre>"
    return f"<p>Panel not found: {_html_escape(panel_id)}</p>"


def render_dashboard(status: dict[str, Any]) -> str:
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
            _status_card("Evidence Summary", f"all_required_evidence_present={evidence['all_required_evidence_present']}"),
            _status_card("Requirement Intake", "Preview-only guided requirement intake is available at /requirements"),
            _status_card("Dashboards", "Evidence and governance dashboards are available at /dashboards"),
        ]
    )
    body = f"""
  <main>
    <div class="grid">{cards}</div>
    <h2>Safe Command Catalog</h2>
    <table>
      <thead><tr><th>ID</th><th>Command</th><th>Portal Execution Enabled</th></tr></thead>
      <tbody>{command_rows}</tbody>
    </table>
    <h2>Status JSON</h2>
    <pre>{_html_escape(json.dumps(status, indent=2, sort_keys=True))}</pre>
  </main>
"""
    return _page("Factory Operator Portal", body)


def render_requirement_intake_page() -> str:
    body = """
  <h2>Guided Requirement Intake</h2>
  <p>Phase 13AX is preview-only. It does not write requirement packages or trigger application engineering.</p>
  <form id="requirementForm">
    <label>Business Domain</label><input name="business_domain" value="UPI dispute resolution">
    <label>Application Name</label><input name="application_name" value="upi_dispute_resolution">
    <label>Capabilities</label><textarea name="capabilities">case intake, dispute triage, evidence tracking, SLA escalation</textarea>
    <label>Regulatory Constraints</label><textarea name="regulatory_constraints">NPCI UPI process traceability, RBI-aligned audit evidence, PII handling</textarea>
    <label>Mock Ecosystem</label><textarea name="mock_ecosystem">mock bank rails, mock NPCI switch, mock notification provider</textarea>
    <label>Data Sensitivity</label><select name="data_sensitivity"><option>regulated payment PII</option><option>internal test data</option><option>public demo data</option></select>
    <label>LLM Mode</label><select name="llm_mode"><option>offline/replay</option><option>dry-run/live-gated</option><option>live human-approved</option></select>
    <label>Approval Mode</label><select name="approval_mode"><option>human approval required</option><option>preview only</option></select>
    <button type="submit">Preview governed requirement package</button>
  </form>
  <h2>Preview JSON</h2><pre id="preview">Submit the form to generate a preview.</pre>
  <script>
    document.getElementById("requirementForm").addEventListener("submit", async function(event) {
      event.preventDefault();
      const formData = new FormData(event.target);
      const payload = Object.fromEntries(formData.entries());
      const response = await fetch("/api/requirements/preview", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
      });
      document.getElementById("preview").textContent = JSON.stringify(await response.json(), null, 2);
    });
  </script>
"""
    return _page("Guided Requirement Intake", body)


def render_dashboards(status: dict[str, object]) -> str:
    body = (
        "<h2>Evidence and Governance Dashboards</h2>"
        + _panel_cards(status)
        + '<h2>Dashboard JSON</h2><pre>'
        + _html_escape(json.dumps(status, indent=2, sort_keys=True))
        + "</pre>"
    )
    return _page("Factory Governance Dashboards", body)


def render_dashboard_panel(status: dict[str, object], panel_id: str, title: str) -> str:
    return _page(title, _panel_detail(status, panel_id))


def create_app(project_root: Path | None = None) -> FastAPI:
    root = (project_root or Path.cwd()).resolve()
    app = FastAPI(title="Factory Operator Portal", version="phase13ay")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "read-only", "phase": "13AY"}

    @app.get("/api/status")
    async def api_status() -> dict[str, Any]:
        return build_local_operator_portal_status(root)

    @app.get("/api/evidence")
    async def api_evidence() -> dict[str, Any]:
        status = build_local_operator_portal_status(root)
        evidence_summary = status.get("evidence_summary")
        if isinstance(evidence_summary, dict):
            return evidence_summary
        return {"all_required_evidence_present": False, "items": {}}

    @app.get("/api/safe-commands")
    async def api_safe_commands() -> list[dict[str, object]]:
        status = build_local_operator_portal_status(root)
        safe_commands = status.get("safe_command_catalog")
        if not isinstance(safe_commands, list):
            return []
        typed_commands: list[dict[str, object]] = []
        for command in safe_commands:
            if isinstance(command, dict):
                typed_commands.append(dict(command))
        return typed_commands

    @app.get("/api/dashboards")
    async def api_dashboards() -> dict[str, object]:
        return build_operator_portal_dashboard_panels(root)

    @app.get("/requirements", response_class=HTMLResponse)
    async def requirement_intake_page() -> str:
        return render_requirement_intake_page()

    @app.post("/api/requirements/preview")
    async def api_requirement_preview(payload: dict[str, Any]) -> dict[str, object]:
        preview = build_requirement_intake_preview(payload)
        return preview.to_dict()

    @app.get("/dashboards", response_class=HTMLResponse)
    async def dashboards_page() -> str:
        return render_dashboards(build_operator_portal_dashboard_panels(root))

    @app.get("/dashboards/evidence", response_class=HTMLResponse)
    async def evidence_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "evidence_audit", "Evidence and Audit Dashboard")

    @app.get("/dashboards/standards", response_class=HTMLResponse)
    async def standards_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "standards_controls", "Standards Controls Dashboard")

    @app.get("/dashboards/self-healing", response_class=HTMLResponse)
    async def self_healing_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "self_healing", "Self-Healing Dashboard")

    @app.get("/dashboards/threats", response_class=HTMLResponse)
    async def threats_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "agentic_threats", "Agentic Threat Dashboard")

    @app.get("/dashboards/handover", response_class=HTMLResponse)
    async def handover_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "handover_replay", "Handover Replay Dashboard")

    @app.get("/dashboards/generated-app", response_class=HTMLResponse)
    async def generated_app_dashboard() -> str:
        return render_dashboard_panel(build_operator_portal_dashboard_panels(root), "generated_application", "Generated Application Dashboard")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return render_dashboard(build_local_operator_portal_status(root))

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local Factory Operator Portal.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        print("ERROR: Portal only allows host 127.0.0.1.", file=sys.stderr)
        return 1
    import uvicorn
    uvicorn.run(create_app(args.project_root), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
