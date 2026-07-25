from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_static_factory_documentation_is_offline_and_deterministic(tmp_path: Path) -> None:
    ui_manifest = tmp_path / "ui.json"
    debug_plan = tmp_path / "debug.json"
    html_out = tmp_path / "guide.html"
    manifest_out = tmp_path / "guide.manifest.json"
    assert subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts/build_operator_portal_exhaustive_ui_manifest.py"), "--project-root", str(PROJECT_ROOT), "--output", str(ui_manifest)], cwd=tmp_path).returncode == 0
    assert subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts/build_factory_debug_plan.py"), "--project-root", str(PROJECT_ROOT), "--json-out", str(debug_plan), "--text-out", str(tmp_path / "debug.md")], cwd=tmp_path).returncode == 0
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/build_factory_complete_documentation.py"),
            "--project-root",
            str(PROJECT_ROOT),
            "--ui-manifest",
            str(ui_manifest),
            "--debug-plan",
            str(debug_plan),
            "--html-out",
            str(html_out),
            "--manifest-out",
            str(manifest_out),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    html = html_out.read_text(encoding="utf-8")
    assert "<script" not in html
    assert "href=\"http" not in html
    assert "iframe" not in html.lower()
    assert html.count("<svg") >= 8
    assert html.count("role=\"img\"") >= 8
    assert html.count("<title") >= 8 and html.count("<desc") >= 8
    assert "data-claim-id=" in html
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "data-reduced-motion-policy=" in html
    for animation in [
        "request-flow-pulse",
        "approval-gate-swing",
        "state-transition-step",
        "evidence-propagation-dash",
        "recovery-loop-rotate",
    ]:
        assert animation in html
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert manifest["reduced_motion_policy"]["css_media_query"] == "@media (prefers-reduced-motion: reduce)"
    assert manifest["reduced_motion_policy"]["html_marker"] == "data-reduced-motion-policy"
    for claim in manifest["claim_evidence"]:
        assert f'data-claim-id="{claim["claim_id"]}"' in html
    assert html == (PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.html").read_text(encoding="utf-8")
    assert manifest == json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
