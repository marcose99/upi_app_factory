from __future__ import annotations

from pathlib import Path

from scripts.build_operator_portal_exhaustive_ui_manifest import build_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_debug_plan_controls_are_visible_and_covered() -> None:
    html = (PROJECT_ROOT / "factory/operator_portal/web_ui/static/index.html").read_text(encoding="utf-8")
    assert "data-action=\"view-factory-debug-plan\"" in html
    assert "data-link=\"download-factory-debug-plan\"" in html
    manifest = build_manifest(PROJECT_ROOT)
    actions = {item.get("action") for item in manifest["controls"]}
    links = {item.get("link") for item in manifest["controls"]}
    assert "view-factory-debug-plan" in actions
    assert "download-factory-debug-plan" in links
    assert manifest["gaps"]["missing_routes"] == []
