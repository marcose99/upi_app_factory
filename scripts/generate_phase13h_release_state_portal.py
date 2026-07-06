#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
SNAPSHOT = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13h" / "release_state_snapshot.json"
OUT = ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_release_state_lineage_portal.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def main() -> int:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = "\n".join(
        f"<tr><td>{esc(item['phase'])}</td><td>{esc(item['tag'])}</td><td>{esc(item['capability'])}</td><td>{esc('OK' if item['tag_present'] else 'MISSING')}</td></tr>"
        for item in payload["release_lineage"]
    )
    commands = "\n".join(f"<li><code>{esc(command)}</code></li>" for command in payload["operator_commands"])
    files = "\n".join(
        f"<tr><td>{esc(path)}</td><td>{esc('OK' if present else 'MISSING')}</td></tr>"
        for path, present in sorted(payload["required_files"].items())
    )
    status = "PASSED" if payload.get("passed") else "FAILED"
    html_text = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Factory Release-State Lineage</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f6f6f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Factory Release-State Lineage</h1>
  <p><strong>Phase:</strong> {esc(payload['phase'])}</p>
  <p><strong>Application:</strong> {esc(payload['app_id'])}</p>
  <p><strong>Status:</strong> {esc(status)}</p>
  <p><strong>Baseline tag:</strong> {esc(payload['baseline_tag'])}</p>
  <h2>Release lineage</h2>
  <table>
    <thead><tr><th>Phase</th><th>Tag</th><th>Capability</th><th>Tag status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Operator commands</h2>
  <ul>{commands}</ul>
  <h2>Required files</h2>
  <table>
    <thead><tr><th>Path</th><th>Status</th></tr></thead>
    <tbody>{files}</tbody>
  </table>
  <h2>Truth boundary</h2>
  <p>{esc(payload['truth_boundary'])}</p>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_text, encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
