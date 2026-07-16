from __future__ import annotations

from html import escape
from typing import Any


def render_runtime_view(*, status: dict[str, Any], events: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"<tr><td>{escape(str(event.get('sequence')))}</td><td>{escape(str(event.get('event_type')))}</td><td>{escape(str(event.get('recorded_at_utc')))}</td></tr>"
        for event in events[-25:]
    )
    binding = status.get("binding", {})
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>UPI App Factory Runtime Operations</title>
  <link rel="stylesheet" href="/operator-ui/runtime.css">
</head>
<body>
  <main class="runtime-shell">
    <h1>Runtime Operations</h1>
    <section class="runtime-grid">
      <div><span>State</span><strong>{escape(str(status.get("state")))}</strong></div>
      <div><span>Run</span><strong>{escape(str(binding.get("run_id")))}</strong></div>
      <div><span>Port</span><strong>{escape(str(binding.get("port")))}</strong></div>
      <div><span>Mock Safe Local</span><strong>{escape(str(status.get("mock_safe_local")))}</strong></div>
      <div><span>Real Payment Calls</span><strong>{escape(str(status.get("real_payment_calls")))}</strong></div>
      <div><span>Certification</span><strong>{escape(str(status.get("certification_posture")))}</strong></div>
    </section>
    <section>
      <h2>Recent Events</h2>
      <table><thead><tr><th>Seq</th><th>Event</th><th>Recorded</th></tr></thead><tbody>{rows}</tbody></table>
    </section>
  </main>
  <script src="/operator-ui/runtime.js"></script>
</body>
</html>
"""
