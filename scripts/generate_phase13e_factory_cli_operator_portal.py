#!/usr/bin/env python3
"""Generate Phase 13E factory CLI operator portal."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
ROOT_COMMAND = "factoryctl"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORTAL_PATH = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "audit_portal"
    / "factory_cli_operator_portal.html"
)
COMMANDS_DOC = PROJECT_ROOT / "docs" / "phase13e" / "factory_cli_operator_commands.json"


def load_commands() -> list[dict[str, str]]:
    data = json.loads(COMMANDS_DOC.read_text(encoding="utf-8"))
    return list(data["commands"])


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    rows: list[str] = []
    for item in load_commands():
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(item['command'])}</code></td>"
            f"<td>{html.escape(item['purpose'])}</td>"
            f"<td>{html.escape(item['risk_level'])}</td>"
            "</tr>"
        )

    html_text = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Phase 13E Factory CLI Operator Portal</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; color: #17202a; }}
    h1, h2 {{ color: #1f4e79; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ccd1d1; padding: 0.6rem; text-align: left; vertical-align: top; }}
    th {{ background: #eef3f8; }}
    code {{ background: #f4f6f7; padding: 0.1rem 0.25rem; border-radius: 0.2rem; }}
    .truth {{ border-left: 4px solid #1f4e79; background: #f8fbfd; padding: 1rem; margin: 1rem 0; }}
  </style>
</head>
<body>
  <h1>Phase 13E Factory CLI Operator Portal</h1>
  <p><strong>App ID:</strong> {app_id}</p>
  <p><strong>Run ID:</strong> {run_id}</p>
  <p><strong>Generated at UTC:</strong> {generated_at}</p>
  <p><strong>Root command:</strong> <code>./{root_command}</code></p>
  <div class=\"truth\"><strong>Truth boundary:</strong> Phase 13E adds an operator command surface only. It does not activate LangGraph/OpenAI execution. Default execution remains local deterministic, while external adapters remain detected and policy-gated.</div>
  <h2>Operator Commands</h2>
  <table>
    <thead><tr><th>Command</th><th>Purpose</th><th>Risk level</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
""".format(
        app_id=html.escape(APP_ID),
        run_id=html.escape(RUN_ID),
        generated_at=html.escape(generated_at),
        root_command=html.escape(ROOT_COMMAND),
        rows="\n".join(rows),
    )
    PORTAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTAL_PATH.write_text(html_text, encoding="utf-8")
    print(PORTAL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
