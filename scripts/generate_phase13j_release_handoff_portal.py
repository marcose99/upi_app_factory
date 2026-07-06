#!/usr/bin/env python3
from __future__ import annotations

import html
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
APP_WORKSPACE = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID
PHASE_DIR = APP_WORKSPACE / "lifecycle_artifacts" / "phase13j"
PORTAL_DIR = APP_WORKSPACE / "audit_portal"
MANIFEST_PATH = PHASE_DIR / "release_handoff_bundle_manifest.json"
PORTAL_PATH = PORTAL_DIR / "factory_release_handoff_bundle_portal.html"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def status_text(value: bool) -> str:
    return "OK" if value else "MISSING"


def main() -> None:
    manifest = load_manifest()
    PORTAL_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for entry in manifest["required_release_files"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(entry['path'])}</td>"
            f"<td>{status_text(bool(entry['exists']))}</td>"
            f"<td><code>{html.escape(str(entry.get('sha256') or ''))}</code></td>"
            "</tr>"
        )
    command_items = "".join(
        f"<li><code>{html.escape(command)}</code></li>"
        for command in manifest["operator_commands"]
    )
    error_items = "".join(
        f"<li>{html.escape(error)}</li>" for error in manifest.get("errors", [])
    ) or "<li>None</li>"

    content = f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>Factory Release Handoff Bundle</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.45rem; text-align: left; vertical-align: top; }}
th {{ background: #f2f2f2; }}
code {{ white-space: pre-wrap; }}
.pass {{ color: #146c2e; font-weight: bold; }}
.fail {{ color: #9f1239; font-weight: bold; }}
</style>
</head>
<body>
<h1>Factory Release Handoff Bundle</h1>
<p><strong>Phase:</strong> {html.escape(manifest['phase'])}</p>
<p><strong>Baseline tag:</strong> <code>{html.escape(manifest['baseline_tag'])}</code></p>
<p><strong>Status:</strong> <span class=\"{'pass' if manifest['passed'] else 'fail'}\">{status_text(bool(manifest['passed']))}</span></p>
<h2>Truth boundary</h2>
<p>{html.escape(manifest['truth_boundary'])}</p>
<h2>Operator commands</h2>
<ul>{command_items}</ul>
<h2>Required release files</h2>
<table>
<thead><tr><th>Path</th><th>Status</th><th>SHA-256</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<h2>Errors</h2>
<ul>{error_items}</ul>
</body>
</html>
"""
    PORTAL_PATH.write_text(content, encoding="utf-8")
    print(PORTAL_PATH)


if __name__ == "__main__":
    main()
