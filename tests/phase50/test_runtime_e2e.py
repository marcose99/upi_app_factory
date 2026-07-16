from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_phase50_browser_runtime_controls_are_present() -> None:
    html = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js").read_text(encoding="utf-8")
    for label in [
        "Runtime Operations",
        "Launch Local Runtime",
        "Discover OpenAPI",
        "Run Scenarios",
        "Stop Runtime",
        "Runtime Evidence",
    ]:
        assert label in html
    for endpoint in [
        "/operator-portal/api/runtime/runs/",
        "/approvals",
        "/start",
        "/openapi",
        "/scenarios",
        "/evidence",
        "/stop",
    ]:
        assert endpoint in script
