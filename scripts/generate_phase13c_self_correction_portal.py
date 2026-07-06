#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
WORKSPACE_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID
REPORT = WORKSPACE_ROOT / "generation_runs" / RUN_ID / "self_correction" / "self_correction_decisions.json"
PORTAL = WORKSPACE_ROOT / "audit_portal" / "factory_self_correction_portal.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def bar(label: str, value: int, total: int) -> str:
    width = max(4, int((value / max(total, 1)) * 100))
    return (
        "<div class='bar-row'><span>" + esc(label) + "</span>"
        "<div class='bar-shell'><div class='bar-fill' style='width:" + str(width) + "%'></div></div>"
        "<strong>" + str(value) + "</strong></div>"
    )


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    summary = report["summary"]
    total = int(summary["total_decisions"])
    rows = (
        bar("Auto remediate", int(summary["auto_remediate"]), total)
        + bar("Human approval required", int(summary["human_approval_required"]), total)
        + bar("Blocked", int(summary["blocked"]), total)
        + bar("Plan only", int(summary["plan_only"]), total)
        + bar("Untriaged", int(summary["untriaged"]), total)
    )
    decision_cards = "".join(
        "<article class='card'><h3>" + esc(item["finding_id"]) + "</h3>"
        "<p>Severity: <strong>" + esc(item["severity"]) + "</strong></p>"
        "<p>Category: <strong>" + esc(item["category"]) + "</strong></p>"
        "<p>Decision: <strong>" + esc(item["action"]) + "</strong></p>"
        "<p>" + esc(item["reason"]) + "</p></article>"
        for item in report["decisions"]
    )
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Self-Correction Portal</title>"
        "<style>body{margin:0;font-family:Arial,sans-serif;background:#0e1420;color:#eef3ff}"
        "header{padding:30px;background:linear-gradient(135deg,#1f2a44,#173b4f)}main{padding:24px;display:grid;gap:22px}"
        "section{background:#172033;border:1px solid #33415c;border-radius:18px;padding:20px}"
        ".grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}"
        ".card{background:#101827;border:1px solid #2f3d59;border-radius:14px;padding:14px}.card p{color:#aebbd7}"
        ".bar-row{display:grid;grid-template-columns:220px 1fr 44px;gap:12px;align-items:center;margin:12px 0}"
        ".bar-shell{height:12px;background:#29344d;border-radius:99px;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,#65d6ad,#79a8ff);animation:pulse 1.8s infinite}"
        ".notice{border-left:5px solid #ffcc66;padding-left:14px;color:#ffe4aa}@keyframes pulse{0%{filter:brightness(.86)}50%{filter:brightness(1.25)}100%{filter:brightness(.86)}}"
        "</style></head><body><header><h1>Governed Self-Correction Portal</h1>"
        "<p>Every warning/error is triaged, decisioned, and ledgered.</p></header><main>"
        "<section><h2>Coverage Summary</h2>"
        f"<p>Total decisions: <strong>{total}</strong></p>"
        f"<p>Untriaged: <strong>{esc(summary['untriaged'])}</strong></p>"
        "<p class='notice'>Low-risk issues may be auto-remediated. Protected operations require human approval. Blocked categories cannot be bypassed.</p>"
        + rows
        + "</section><section><h2>Finding Decisions</h2><div class='grid'>"
        + decision_cards
        + "</div></section></main></body></html>"
    )
    PORTAL.parent.mkdir(parents=True, exist_ok=True)
    PORTAL.write_text(html_text, encoding="utf-8")
    print(PORTAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
