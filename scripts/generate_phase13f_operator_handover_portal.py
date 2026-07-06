#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13f" / "operator_handover_audit.json"
PORTAL_FILE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_operator_handover_closure_portal.html"


def badge(value: bool) -> str:
    label = "PASS" if value else "FAIL"
    klass = "pass" if value else "fail"
    return f'<span class="badge {klass}">{label}</span>'


def main() -> int:
    if not AUDIT_FILE.exists():
        raise FileNotFoundError(f"Missing Phase 13F audit file: {AUDIT_FILE}")
    audit = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    PORTAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    doc_rows = []
    for doc in audit.get("required_handover_documents", []):
        status = "MISSING" if doc in audit.get("missing_documents", []) else "OK"
        klass = "fail" if status == "MISSING" else "pass"
        doc_rows.append(
            "<tr>"
            f"<td>{html.escape(doc)}</td>"
            f"<td><span class='badge {klass}'>{status}</span></td>"
            "</tr>"
        )

    missing_lines = audit.get("missing_output_lines", [])
    missing_html = "".join(f"<li>{html.escape(line)}</li>" for line in missing_lines) or "<li>None</li>"
    generated_at = datetime.now(timezone.utc).isoformat()

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Phase 13F Operator Handover Closure</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.55rem; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .badge {{ border-radius: 999px; padding: 0.2rem 0.55rem; font-weight: 700; font-size: 0.85rem; }}
    .pass {{ background: #e7f7ec; color: #136c2e; }}
    .fail {{ background: #fdecec; color: #9f1d1d; }}
    .card {{ border: 1px solid #ddd; border-radius: 0.6rem; padding: 1rem; margin: 1rem 0; }}
    code {{ background: #f5f5f5; padding: 0.1rem 0.25rem; border-radius: 0.2rem; }}
  </style>
</head>
<body>
  <h1>Phase 13F Operator Handover Closure</h1>
  <div class="card">
    <p><strong>Application:</strong> {html.escape(audit.get('app_id', APP_ID))}</p>
    <p><strong>Run ID:</strong> {html.escape(audit.get('run_id', RUN_ID))}</p>
    <p><strong>Status:</strong> {badge(bool(audit.get('passed')))}</p>
    <p><strong>Generated at UTC:</strong> {html.escape(generated_at)}</p>
  </div>
  <h2>Required handover documents</h2>
  <table>
    <thead><tr><th>Document</th><th>Status</th></tr></thead>
    <tbody>{''.join(doc_rows)}</tbody>
  </table>
  <h2>factoryctl handover missing lines</h2>
  <ul>{missing_html}</ul>
  <h2>Truth boundary</h2>
  <p>{html.escape(audit.get('truth_boundary', ''))}</p>
</body>
</html>
"""
    PORTAL_FILE.write_text(page, encoding="utf-8")
    print(PORTAL_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
