#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13i"
    / "release_readiness_audit.json"
)
PORTAL_PATH = (
    ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "audit_portal"
    / "factory_release_readiness_operator_acceptance_portal.html"
)


def esc(value: object) -> str:
    return html.escape(str(value))


def rows_for_release_lineage(audit: dict[str, Any]) -> str:
    rows = []
    for item in audit["release_lineage"]:
        rows.append(
            "<tr>"
            f"<td>{esc(item['phase'])}</td>"
            f"<td>{esc(item['capability'])}</td>"
            f"<td>{esc(item['tag'])}</td>"
            f"<td>{esc(item['tag_present'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def rows_for_required_files(audit: dict[str, Any]) -> str:
    rows = []
    for path, present in sorted(audit["required_files"].items()):
        rows.append(
            "<tr>"
            f"<td>{esc(path)}</td>"
            f"<td>{esc(present)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def rows_for_smoke_checks(audit: dict[str, Any]) -> str:
    rows = []
    for item in audit["operator_smoke_checks"]:
        rows.append(
            "<tr>"
            f"<td>{esc(item['command'])}</td>"
            f"<td>{esc(item['exit_code'])}</td>"
            f"<td>{esc(item['passed'])}</td>"
            f"<td>{esc(item['handover_missing_entries'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_html(audit: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Phase 13I Release Readiness Operator Acceptance</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #c8c8c8; padding: 0.45rem; text-align: left; }}
    th {{ background: #f2f2f2; }}
    .pass {{ color: #0a6b2b; font-weight: bold; }}
    .boundary {{ background: #f8f8f8; border-left: 4px solid #555; padding: 1rem; }}
  </style>
</head>
<body>
  <h1>Phase 13I — Release Readiness Operator Acceptance</h1>
  <p>Status: <span class=\"pass\">{esc(audit['passed'])}</span></p>
  <p>Baseline tag: <code>{esc(audit['baseline_tag'])}</code></p>
  <div class=\"boundary\">{esc(audit['truth_boundary'])}</div>

  <h2>Release Lineage</h2>
  <table>
    <thead><tr><th>Phase</th><th>Capability</th><th>Tag</th><th>Present</th></tr></thead>
    <tbody>{rows_for_release_lineage(audit)}</tbody>
  </table>

  <h2>Operator Smoke Checks</h2>
  <table>
    <thead><tr><th>Command</th><th>Exit Code</th><th>Passed</th><th>Handover Missing Entries</th></tr></thead>
    <tbody>{rows_for_smoke_checks(audit)}</tbody>
  </table>

  <h2>Required Files</h2>
  <table>
    <thead><tr><th>Path</th><th>Present</th></tr></thead>
    <tbody>{rows_for_required_files(audit)}</tbody>
  </table>
</body>
</html>
"""


def main() -> int:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    PORTAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_PATH.write_text(build_html(audit), encoding="utf-8")
    print(PORTAL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
