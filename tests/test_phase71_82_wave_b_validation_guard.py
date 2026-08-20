from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_GENERATED_ROOT = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
)
TEMPLATE_MANIFEST_PATH = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/template_manifest.v1.json"
)
EXPECTED_GENERATED_FILE_COUNT = len(
    json.loads(TEMPLATE_MANIFEST_PATH.read_text(encoding="utf-8"))["template_files"]
)
WAVE_B_REPORT = (
    PROJECT_ROOT / "docs/enterprise_engineering/phase71_82_v63/WAVE_B_REPORT.md"
)


def bytecode_artifacts(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    artifacts: dict[str, str] = {}
    for path in root.rglob("*"):
        if (
            path.name in {"__pycache__", ".pytest_cache"}
            or path.suffix in {".pyc", ".pyo"}
        ):
            relative_path = path.relative_to(root).as_posix()
            if path.is_file():
                artifacts[relative_path] = (
                    f"file:{path.stat().st_size}:"
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
                )
            else:
                artifacts[relative_path] = "dir"
    return artifacts


def test_wave_b_report_does_not_record_source_mutating_compileall_command() -> None:
    report = WAVE_B_REPORT.read_text(encoding="utf-8")

    assert "python -m compileall -q factory/templates/mock_dispute_app" not in report
    assert "--workspace-root workspace/regeneration_runs" not in report
    assert "validate_phase71_82_wave_b_generated_output.py" in report
    assert "PYTHONPYCACHEPREFIX" in report


def test_wave_b_validation_script_does_not_mutate_source_tree_bytecode() -> None:
    before = bytecode_artifacts(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase71_82_wave_b_generated_output.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    after = bytecode_artifacts(PROJECT_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["generated_file_count"] == EXPECTED_GENERATED_FILE_COUNT
    assert payload["compiled_roots"] == ["fresh temporary generated output"]
    assert after == before


def test_pytest_validation_does_not_mutate_source_tree_bytecode() -> None:
    before = bytecode_artifacts(PROJECT_ROOT)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase71_82_wave_b_validation_guard.py::"
            "test_wave_b_report_does_not_record_source_mutating_compileall_command",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    after = bytecode_artifacts(PROJECT_ROOT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert after == before
