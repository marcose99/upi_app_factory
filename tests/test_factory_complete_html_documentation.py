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
    assert subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts/build_operator_portal_exhaustive_ui_manifest.py"), "--project-root", str(PROJECT_ROOT), "--output", str(ui_manifest)], cwd=Path("/tmp")).returncode == 0
    assert subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts/build_factory_debug_plan.py"), "--project-root", str(PROJECT_ROOT), "--json-out", str(debug_plan), "--text-out", str(tmp_path / "debug.md")], cwd=Path("/tmp")).returncode == 0
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
        cwd=Path("/tmp"),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    html = html_out.read_text(encoding="utf-8")
    assert "<script" not in html
    assert "href=\"http" not in html
    assert html.count("<svg") >= 5
    assert "<title" in html and "<desc" in html
    assert html == (PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.html").read_text(encoding="utf-8")
    assert json.loads(manifest_out.read_text(encoding="utf-8")) == json.loads((PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(encoding="utf-8"))
