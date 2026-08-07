from __future__ import annotations

import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROW_RE = re.compile(
    r"(<td>[^<]+</td><td>)[0-9a-f]{64}(</td><td>)\d+(</td>)"
)
REPOSITORY_COUNT_METRIC_RE = re.compile(
    r"(<strong>)\d+(</strong>Repository (?:Python|Test) Files</div>)"
)
PROMPT_COUNT_METRIC_RE = re.compile(
    r"(<strong>)\d+(</strong>Prompt Markdown Files</div>)"
)
SOURCE_TRACE_COUNT_METRIC_RE = re.compile(
    r"(<strong>)\d+(</strong>Source Files Traced</div>)"
)
VOLATILE_TECHNICAL_INVENTORY_COUNTS = {
    "repository_python_files",
    "repository_test_files",
    "prompt_markdown_files",
    "source_files_traced",
}


def _phase_frozen_html(text: str) -> str:
    normalized = SOURCE_ROW_RE.sub(r"\1SOURCE_SHA256\2SOURCE_SIZE\3", text)
    normalized = REPOSITORY_COUNT_METRIC_RE.sub(r"\1REPOSITORY_COUNT\2", normalized)
    normalized = PROMPT_COUNT_METRIC_RE.sub(r"\1PROMPT_COUNT\2", normalized)
    return SOURCE_TRACE_COUNT_METRIC_RE.sub(r"\1SOURCE_TRACE_COUNT\2", normalized)


def _phase_frozen_manifest(manifest: dict[str, object]) -> dict[str, object]:
    normalized = deepcopy(manifest)
    normalized["debug_plan_sha256"] = "DEBUG_PLAN_SHA256"
    normalized["html_sha256"] = "HTML_SHA256"
    technical_inventory = normalized.get("technical_inventory")
    if isinstance(technical_inventory, dict):
        for key in VOLATILE_TECHNICAL_INVENTORY_COUNTS:
            if key in technical_inventory:
                technical_inventory[key] = "VOLATILE_REPOSITORY_COUNT"
    _freeze_source_facts(normalized)
    return normalized


def _freeze_source_facts(value: object) -> None:
    if isinstance(value, dict):
        if "path" in value or "locator" in value:
            if "sha256" in value:
                value["sha256"] = "SOURCE_SHA256"
            if "size_bytes" in value:
                value["size_bytes"] = "SOURCE_SIZE"
        for item in value.values():
            _freeze_source_facts(item)
    elif isinstance(value, list):
        for item in value:
            _freeze_source_facts(item)


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
    tracked_html = (PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.html").read_text(
        encoding="utf-8"
    )
    tracked_manifest = json.loads(
        (PROJECT_ROOT / "docs/factory/UPI_APP_FACTORY_COMPLETE_GUIDE.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert _phase_frozen_html(html) == _phase_frozen_html(tracked_html)
    assert _phase_frozen_manifest(manifest) == _phase_frozen_manifest(tracked_manifest)
