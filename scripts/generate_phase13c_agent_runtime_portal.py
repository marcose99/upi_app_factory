#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
LEDGER_ROOT = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_runtime_ledgers"
STATE = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "agent_runtime_state_snapshot.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_agent_runtime_portal.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                rows.append(loaded)
    return rows


def bar(label: str, value: int, max_value: int) -> str:
    width = max(5, int((value / max(max_value, 1)) * 100))
    return (
        "<div class='bar-row'><span>"
        + esc(label)
        + "</span><div class='bar-shell'><div class='bar-fill' style='width:"
        + str(width)
        + "%'></div></div><strong>"
        + str(value)
        + "</strong></div>"
    )


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    runtime_events = read_jsonl(LEDGER_ROOT / "runtime_event_ledger.jsonl")
    handoffs = read_jsonl(LEDGER_ROOT / "handoff_ledger.jsonl")
    tools = read_jsonl(LEDGER_ROOT / "tool_execution_ledger.jsonl")
    agents = state.get("completed_agents", [])
    max_agent = max(len(agents), 1)
    agent_cards = "".join(
        "<article class='agent-card'><h3>" + esc(agent) + "</h3><p>dry-run complete</p></article>"
        for agent in agents
    )
    bars = (
        bar("Runtime events", len(runtime_events), max_agent + 2)
        + bar("Agent handoffs", len(handoffs), max_agent)
        + bar("Tool authorizations", len(tools), max(len(tools), 1))
    )
    svg = (
        "<svg viewBox='0 0 720 140' class='flow'>"
        "<defs><marker id='arrow' markerWidth='10' markerHeight='10' refX='6' refY='3' orient='auto'>"
        "<path d='M0,0 L0,6 L7,3 z'></path></marker></defs>"
    )
    x = 30
    for index, agent in enumerate(agents[:7]):
        svg += f"<rect x='{x}' y='45' width='82' height='42' rx='10'></rect>"
        svg += f"<text x='{x + 8}' y='70'>{esc(str(index + 1))}</text>"
        if index < len(agents[:7]) - 1:
            svg += f"<line x1='{x + 86}' y1='66' x2='{x + 122}' y2='66' marker-end='url(#arrow)'></line>"
        x += 104
    svg += "</svg>"
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Agent Runtime Portal</title>"
        "<style>body{margin:0;font-family:Arial,sans-serif;background:#0e1420;color:#eef3ff}"
        "header{padding:30px;background:linear-gradient(135deg,#1f2a44,#173b4f)}main{padding:24px;display:grid;gap:22px}"
        "section{background:#172033;border:1px solid #33415c;border-radius:18px;padding:20px}.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}"
        ".agent-card{background:#101827;border:1px solid #2f3d59;border-radius:14px;padding:14px}.agent-card p{color:#aebbd7}"
        ".bar-row{display:grid;grid-template-columns:190px 1fr 44px;gap:12px;align-items:center;margin:12px 0}.bar-shell{height:12px;background:#29344d;border-radius:99px;overflow:hidden}"
        ".bar-fill{height:100%;background:linear-gradient(90deg,#65d6ad,#79a8ff);animation:pulse 1.8s infinite}.notice{border-left:5px solid #ffcc66;padding-left:14px;color:#ffe4aa}"
        ".flow{width:100%;height:170px;color:#65d6ad}.flow rect{fill:#101827;stroke:#79a8ff}.flow line,.flow path{stroke:#65d6ad;fill:#65d6ad}.flow text{fill:#eef3ff}"
        "@keyframes pulse{0%{filter:brightness(.86)}50%{filter:brightness(1.25)}100%{filter:brightness(.86)}}"
        "</style></head><body><header><h1>Governed Agent Runtime Portal</h1>"
        f"<p>Run: {esc(state['run_id'])}</p></header><main>"
        "<section><h2>Runtime Summary</h2>"
        f"<p>Runtime mode: <strong>{esc(state['runtime_mode'])}</strong></p>"
        f"<p>Agents completed: <strong>{len(agents)}</strong></p>"
        "<p class='notice'>This is a real local runtime foundation and dry-run execution. "
        "LangGraph/OpenAI-agent LLM execution is planned next and is not falsely claimed here.</p></section>"
        f"<section><h2>Agent Sequence Graph</h2>{svg}</section>"
        f"<section><h2>Agent Registry Progress</h2><div class='grid'>{agent_cards}</div></section>"
        f"<section><h2>Runtime Ledger Metrics</h2>{bars}</section>"
        "</main></body></html>"
    )
    PORTAL.parent.mkdir(parents=True, exist_ok=True)
    PORTAL.write_text(html_text, encoding="utf-8")
    print(PORTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
