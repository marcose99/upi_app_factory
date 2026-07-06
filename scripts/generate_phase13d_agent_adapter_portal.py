#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
REPORT = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_adapter_execution_report.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_agent_adapter_portal.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def status_card(item: dict[str, object]) -> str:
    return (
        "<article class='card'><h3>" + esc(item["adapter_name"]) + "</h3>"
        "<p>Status: <strong>" + esc(item["status"]) + "</strong></p>"
        "<p>Human approval: <strong>" + esc(item["requires_human_approval"]) + "</strong></p>"
        "<p>Network: <strong>" + esc(item["requires_network"]) + "</strong></p>"
        "<p>" + esc(item["reason"]) + "</p></article>"
    )


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    capabilities = "".join(status_card(item) for item in report["capabilities"])
    execution = report["default_adapter_execution"]
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Agent Adapter Portal</title>"
        "<style>body{margin:0;font-family:Arial,sans-serif;background:#0e1420;color:#eef3ff}"
        "header{padding:30px;background:linear-gradient(135deg,#1f2a44,#173b4f)}main{padding:24px;display:grid;gap:22px}"
        "section{background:#172033;border:1px solid #33415c;border-radius:18px;padding:20px}"
        ".grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}"
        ".card{background:#101827;border:1px solid #2f3d59;border-radius:14px;padding:14px}.card p{color:#aebbd7}"
        ".notice{border-left:5px solid #ffcc66;padding-left:14px;color:#ffe4aa}"
        "</style></head><body><header><h1>Governed Agent Adapter Portal</h1>"
        f"<p>Run: {esc(report['run_id'])}</p></header><main>"
        "<section><h2>Default Adapter Execution</h2>"
        f"<p>Adapter: <strong>{esc(execution['adapter_name'])}</strong></p>"
        f"<p>Status: <strong>{esc(execution['status'])}</strong></p>"
        f"<p>Message: {esc(execution['message'])}</p>"
        "<p class='notice'>Only local deterministic adapter execution is enabled by default. "
        "LangGraph/OpenAI execution remains human-approval and policy gated.</p></section>"
        f"<section><h2>Adapter Capability Cards</h2><div class='grid'>{capabilities}</div></section>"
        "</main></body></html>"
    )
    PORTAL.parent.mkdir(parents=True, exist_ok=True)
    PORTAL.write_text(html_text, encoding="utf-8")
    print(PORTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
