from __future__ import annotations

from pathlib import Path
import shutil

from scripts import run_portal_requirements_driven_application_engineering as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    root = PROJECT_ROOT / "workspace" / "factory_generated" / "post_r9_5" / tmp_path.name / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_generated_test_execution_is_isolated_from_repository_root_conftest(
    tmp_path: Path,
) -> None:
    app_root = _contained_test_root(tmp_path, "generated_runner")
    tests_root = app_root / "tests"
    tests_root.mkdir(parents=True)
    (tests_root / "test_smoke.py").write_text(
        "def test_smoke() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    report = adapter._execute_generated_tests(
        app_root=app_root,
        app_id="upi_dispute_resolution",
        version_id="v_test",
        run_id="portal_test",
        requirements_sha256="0" * 64,
    )

    assert report["exit_code"] == 0
    assert report["go_gate"] == "GO"
    assert report["counts"]["passed"] == 1
    assert report["tests_executed"]["all"] == ["tests/test_smoke.py"]
    assert f"--rootdir={app_root}" in report["argv"]
    assert f"--confcutdir={app_root}" in report["argv"]
