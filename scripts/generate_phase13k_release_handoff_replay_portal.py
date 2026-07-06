#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path

APP_ID = "upi_dispute_resolution"
ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13k" / "release_handoff_replay_audit.json"
PORTAL_FILE = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_release_handoff_replay_verification_portal.html"


def row(label: str, value: object) -> str:
    return f"<tr><th>{html.escape(label)}</th><td><pre>{html.escape(str(value))}</pre></td></tr>"


def main() -> int:
    data = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    checksum_rows = "\n".join(
        f"<tr><td>{html.escape(item['path'])}</td><td>{html.escape(str(item['exists']))}</td><td>{html.escape(str(item['matches']))}</td><td>{html.escape(item.get('scope', ''))}</td></tr>"
        for item in data.get("checksum_entries", [])
    )
    command_rows = "\n".join(
        f"<tr><td>{html.escape(item['command'])}</td><td>{html.escape(str(item['passed']))}</td><td>{html.escape(str(item['exit_code']))}</td></tr>"
        for item in data.get("operator_smoke_checks", [])
    )
    errors = data.get("errors", [])
    error_html = "".join(f"<li>{html.escape(str(error))}</li>" for error in errors) or "<li>None</li>"
    html_doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Phase 13K Release Handoff Replay Verification</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    .pass {{ color: #0a6b2b; font-weight: bold; }}
    .fail {{ color: #9b1c1c; font-weight: bold; }}
    pre {{ white-space: pre-wrap; margin: 0; }}
  </style>
</head>
<body>
  <h1>Phase 13K Release Handoff Replay Verification</h1>
  <p class=\"{'pass' if data.get('passed') else 'fail'}\">Passed: {html.escape(str(data.get('passed')))}</p>
  <table>
    {row('Phase', data.get('phase'))}
    {row('App ID', data.get('app_id'))}
    {row('Baseline tag', data.get('baseline_tag'))}
    {row('Baseline tag present', data.get('baseline_tag_present'))}
    {row('Bundle directory', data.get('bundle_directory'))}
    {row('Checksum scope', data.get('checksum_scope'))}
    {row('Truth boundary', data.get('truth_boundary'))}
  </table>
  <h2>Checksum replay</h2>
  <table><tr><th>Path</th><th>Exists</th><th>Matches</th><th>Scope</th></tr>{checksum_rows}</table>
  <h2>Operator smoke replay</h2>
  <table><tr><th>Command</th><th>Passed</th><th>Exit code</th></tr>{command_rows}</table>
  <h2>Errors</h2>
  <ul>{error_html}</ul>
</body>
</html>
"""
    PORTAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_FILE.write_text(html_doc, encoding="utf-8")
    print(PORTAL_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
