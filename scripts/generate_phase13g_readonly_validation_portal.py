from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID
AUDIT_PATH = WORKSPACE / "lifecycle_artifacts" / "phase13g" / "readonly_validation_audit.json"
PORTAL_PATH = WORKSPACE / "audit_portal" / "factory_readonly_validation_drift_guardrails_portal.html"


def badge(value: bool) -> str:
    return "PASS" if value else "FAIL"


def main() -> int:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    rows = []
    for command in audit.get("commands_checked", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(command.get('name', '')))}</td>"
            f"<td>{html.escape(str(command.get('purpose', '')))}</td>"
            f"<td>{html.escape(str(command.get('returncode', '')))}</td>"
            f"<td>{html.escape(str(command.get('allowed_tracked_drift_detected', [])))}</td>"
            f"<td>{html.escape(str(command.get('allowed_tracked_drift_restored', [])))}</td>"
            f"<td>{html.escape(str(command.get('unexpected_tracked_after_restore', [])))}</td>"
            "</tr>"
        )

    result = audit.get("guardrail_result", {})
    html_doc = "\n".join([
        '<!doctype html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8">',
        '<title>FactoryFromNothing Phase 13G Read-only Validation Drift Guardrails</title>',
        '<style>',
        'body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}',
        'h1, h2 {{ color: #1f2937; }}',
        '.card {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 1rem; margin: 1rem 0; background: #f9fafb; }}',
        '.pass {{ color: #047857; font-weight: bold; }}',
        '.fail {{ color: #b91c1c; font-weight: bold; }}',
        'table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}',
        'th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; vertical-align: top; font-size: 0.92rem; }}',
        'th {{ background: #e5e7eb; }}',
        'code {{ background: #eef2ff; padding: 0.15rem 0.3rem; border-radius: 4px; }}',
        '</style>',
        '</head>',
        '<body>',
        '<h1>Phase 13G: Read-only Validation Drift Guardrails</h1>',
        '<div class="card">',
        '  <p><strong>Status:</strong> <span class="{status_class}">{status}</span></p>',
        '  <p><strong>Commands executed:</strong> {commands_executed}</p>',
        '  <p><strong>Drift events detected/restored:</strong> {drift_events}</p>',
        '  <p><strong>Unexpected tracked drift after restore:</strong> <code>{unexpected_tracked}</code></p>',
        '</div>',
        '<h2>Commands checked</h2>',
        '<table>',
        '<thead>',
        '<tr>',
        '<th>Name</th>',
        '<th>Purpose</th>',
        '<th>Return code</th>',
        '<th>Allowed drift detected</th>',
        '<th>Allowed drift restored</th>',
        '<th>Unexpected drift after restore</th>',
        '</tr>',
        '</thead>',
        '<tbody>',
        '{rows}',
        '</tbody>',
        '</table>',
        '<h2>Truth boundary</h2>',
        '<p>{truth_boundary}</p>',
        '</body>',
        '</html>',
    ]).format(
        status=badge(bool(audit.get("passed"))),
        status_class="pass" if audit.get("passed") else "fail",
        commands_executed=html.escape(str(result.get("commands_executed", ""))),
        drift_events=html.escape(str(result.get("drift_events_detected", ""))),
        unexpected_tracked=html.escape(str(result.get("unexpected_tracked_after_restore", []))),
        rows="\n".join(rows),
        truth_boundary=html.escape(str(audit.get("truth_boundary", ""))),
    )

    PORTAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_PATH.write_text(html_doc, encoding="utf-8")
    print(PORTAL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
