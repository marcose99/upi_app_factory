from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from factory.operator_portal.web_ui.app import create_web_ui_app
from scripts.build_operator_portal_exhaustive_ui_manifest import build_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_documentation_controls_are_visible_and_covered() -> None:
    html = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html").read_text(encoding="utf-8")
    assert "data-action=\"view-factory-documentation\"" in html
    assert "data-link=\"download-factory-documentation\"" in html
    manifest = build_manifest(PROJECT_ROOT)
    actions = {item.get("action") for item in manifest["controls"]}
    links = {item.get("link") for item in manifest["controls"]}
    assert "view-factory-documentation" in actions
    assert "download-factory-documentation" in links
    assert manifest["gaps"]["missing_routes"] == []


def test_use_sample_requirements_route_and_control_are_available(tmp_path: Path) -> None:
    html = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/app.js").read_text(encoding="utf-8")
    sample = PROJECT_ROOT / "examples/requirements/01_upi_failed_debit_no_credit.md"

    assert sample.is_file()
    assert "data-action=\"use-sample-requirements\"" in html
    assert "/operator-portal/api/requirements/sample" in script

    client = TestClient(
        create_web_ui_app(
            project_root=PROJECT_ROOT,
            browser_state_root=tmp_path / "runs",
            portfolio_state_root=tmp_path / "portfolio",
            runtime_state_root=tmp_path / "runtime",
        )
    )
    response = client.get("/operator-portal/api/requirements/sample")

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "examples/requirements/01_upi_failed_debit_no_credit.md"
    assert "Failed Debit Requirements" in payload["requirements"]
    assert payload["safety_boundaries"]["live_provider_calls_allowed"] is False
