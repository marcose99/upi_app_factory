#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
FACTORY_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
SNAPSHOT = FACTORY_ROOT / "generation_runs" / RUN_ID / "factory_progress_observability_snapshot.json"
PORTAL = FACTORY_ROOT / "audit_portal" / "factory_generation_progress_portal.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def progress_card(row: dict[str, Any]) -> str:
    value = clamp(row["progress"])
    return (
        "<article class='card'>"
        f"<h3>{esc(row['phase'])}</h3><p>{esc(row['status'])}</p>"
        "<div class='bar-shell'>"
        f"<div class='bar-fill' style='width:{value}%'></div>"
        "</div>"
        f"<small>{value}%</small>"
        "</article>"
    )


def bar_chart(rows: list[dict[str, Any]], label_key: str) -> str:
    max_value = max([int(row["value"]) for row in rows] + [1])
    html_rows = []
    for row in rows:
        value = int(row["value"])
        width = max(5, int(value / max_value * 100))
        html_rows.append(
            "<div class='chart-row'>"
            f"<span>{esc(row[label_key])}</span>"
            "<div class='chart-bar-shell'>"
            f"<div class='chart-bar' style='width:{width}%'></div>"
            "</div>"
            f"<strong>{value}</strong>"
            "</div>"
        )
    return "".join(html_rows)


def donut(title: str, value: int, note: str) -> str:
    value = clamp(value)
    return (
        "<article class='card donut-card'>"
        f"<div class='donut' style='--p:{value}'><span>{value}%</span></div>"
        f"<h3>{esc(title)}</h3><p>{esc(note)}</p>"
        "</article>"
    )


def metric_cards(metrics: dict[str, Any]) -> str:
    return "".join(
        "<article class='card metric'><span>"
        + esc(key.replace("_", " ").title())
        + "</span><strong>"
        + esc(value)
        + "</strong></article>"
        for key, value in metrics.items()
    )


def maturity_svg() -> str:
    return (
        "<svg viewBox='0 0 520 190' class='trend' role='img'>"
        "<polyline points='20,150 90,125 160,102 230,76 300,58 370,44 500,38' "
        "fill='none' stroke='currentColor' stroke-width='5' stroke-linecap='round'/>"
        "<circle cx='20' cy='150' r='6'/><circle cx='90' cy='125' r='6'/>"
        "<circle cx='160' cy='102' r='6'/><circle cx='230' cy='76' r='6'/>"
        "<circle cx='300' cy='58' r='6'/><circle cx='370' cy='44' r='6'/>"
        "<circle cx='500' cy='38' r='6'/>"
        "<text x='15' y='180'>11C</text><text x='85' y='180'>11D</text>"
        "<text x='155' y='180'>12A</text><text x='225' y='180'>12B</text>"
        "<text x='295' y='180'>13A</text><text x='365' y='180'>13B</text>"
        "<text x='462' y='180'>13C+</text></svg>"
    )


def render(snapshot: dict[str, Any]) -> str:
    progress = "".join(progress_card(row) for row in snapshot["progress_steps"])
    avg_progress = int(sum(int(row["progress"]) for row in snapshot["progress_steps"]) / len(snapshot["progress_steps"]))
    portal_progress = next(row["progress"] for row in snapshot["progress_steps"] if row["phase"] == "Final portal cockpit")
    validation = bar_chart(snapshot["validation_chart"], "category")
    observability = bar_chart(snapshot["observability_chart"], "signal")
    metrics = metric_cards(snapshot["metrics"])
    style = (
        ":root{--bg:#0e1420;--panel:#172033;--panel2:#101827;--line:#33415c;"
        "--text:#eef3ff;--muted:#aebbd7;--accent:#79a8ff;--accent2:#65d6ad;--warn:#ffcc66}"
        "body{margin:0;font-family:Arial,sans-serif;background:radial-gradient(circle at top,#17233b,#0e1420 55%);color:var(--text)}"
        "header{padding:34px;background:linear-gradient(135deg,#1f2a44,#173b4f)}"
        "main{padding:24px;display:grid;gap:24px}section{background:rgba(23,32,51,.92);border:1px solid var(--line);border-radius:20px;padding:22px}"
        ".grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}"
        ".card{background:var(--panel2);border:1px solid #2f3d59;border-radius:16px;padding:15px}"
        ".card p,.card small,.metric span{color:var(--muted)}.bar-shell,.chart-bar-shell{height:11px;background:#29344d;border-radius:99px;overflow:hidden;margin:10px 0}"
        ".bar-fill,.chart-bar{height:100%;background:linear-gradient(90deg,var(--accent2),var(--accent));animation:pulse 1.8s ease-in-out infinite}"
        ".chart-row{display:grid;grid-template-columns:210px 1fr 48px;gap:12px;align-items:center;margin:12px 0}.chart-row span{color:var(--muted)}"
        ".metric strong{display:block;margin-top:8px;font-size:18px}.notice{border-left:5px solid var(--warn);padding-left:14px;color:#ffe4aa}"
        ".donut{--p:0;width:132px;height:132px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--accent2) calc(var(--p)*1%),#29344d 0);margin:auto;position:relative}"
        ".donut:after{content:'';position:absolute;width:86px;height:86px;border-radius:50%;background:var(--panel2)}.donut span{position:relative;z-index:1;font-size:24px;font-weight:800}.donut-card{text-align:center}"
        ".trend{width:100%;height:220px;color:var(--accent2)}.trend text{fill:var(--muted);font-size:14px}.trend circle{fill:var(--accent)}"
        "@keyframes pulse{0%{filter:brightness(.86)}50%{filter:brightness(1.25)}100%{filter:brightness(.86)}}"
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Factory Generation Progress Portal</title>"
        f"<style>{style}</style></head><body><header><h1>Factory Progress Portal</h1>"
        "<p>Charts • Graphs • Observability • Validation Metrics • Generation Progress</p>"
        f"<p>Run: {esc(snapshot['run_id'])}</p></header><main>"
        "<section><h2>Executive Progress Summary</h2>"
        f"<p>Runtime mode: <strong>{esc(snapshot['runtime_mode'])}</strong></p>"
        f"<p>Validation state: <strong>{esc(snapshot['validation_state'])}</strong></p>"
        f"<p>LangGraph runtime: <strong>{esc(snapshot['langgraph_runtime_status'])}</strong></p>"
        "<p class='notice'>Current Phase 13B is deterministic scripted generation. The portal must not falsely claim active LangChain/LangGraph agent execution until the real agent runtime phase exists.</p></section>"
        f"<section><h2>Completion Gauges</h2><div class='grid'>{donut('Factory progress', avg_progress, 'Average progress across major phases')}{donut('Portal cockpit', int(portal_progress), 'Current portal maturity')}</div></section>"
        f"<section><h2>Factory Phase Progress</h2><div class='grid'>{progress}</div></section>"
        f"<section><h2>Validation Bar Chart</h2>{validation}</section>"
        f"<section><h2>Observability Readiness Chart</h2>{observability}</section>"
        f"<section><h2>Factory Maturity Trend</h2>{maturity_svg()}</section>"
        f"<section><h2>Application Generation Metrics</h2><div class='grid'>{metrics}</div></section>"
        "<section><h2>Agent Runtime Status</h2><p>Current: deterministic scripted baseline. Next: real governed agent runtime with state, handoffs, tools, traces, validators, audit, remediation, and live progress snapshots.</p></section>"
        "</main></body></html>"
    )


def main() -> int:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    PORTAL.parent.mkdir(parents=True, exist_ok=True)
    PORTAL.write_text(render(snapshot), encoding="utf-8")
    print(PORTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
