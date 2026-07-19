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
        "/operator-portal/api/portfolio/catalogue",
        "/operator-portal/api/portfolio/approvals",
        "/operator-portal/api/portfolio/runtime/start",
        "/operator-portal/api/portfolio/runtime/openapi",
        "/operator-portal/api/portfolio/scenarios",
        "/operator-portal/api/portfolio/evidence",
        "/operator-portal/api/portfolio/runtime/stop",
    ]:
        assert endpoint in script
    assert 'id="runtime-version-selector"' in html
    assert "/operator-portal/api/runtime/runs/" not in script
