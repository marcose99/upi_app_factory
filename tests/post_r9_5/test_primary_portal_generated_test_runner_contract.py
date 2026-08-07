from __future__ import annotations

from pathlib import Path
import shutil

from scripts import run_portal_requirements_driven_application_engineering as adapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _contained_test_root(tmp_path: Path, name: str) -> Path:
    root = PROJECT_ROOT / "workspace" / "tmp" / "post_r9_5" / tmp_path.name / name
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
    assert f"--rootdir={PROJECT_ROOT}" in report["argv"]
    assert f"--rootdir={app_root}" not in report["argv"]
    prohibited_confcut_option = "".join(("--", "conf", "cut", "dir"))
    assert not any(argument.startswith(prohibited_confcut_option) for argument in report["argv"])
    assert report["cwd"] == str(app_root)


def test_generated_test_execution_uses_root_conftest_with_portable_imports(
    tmp_path: Path,
) -> None:
    app_root = _contained_test_root(tmp_path, "generated_import_runner")
    tests_root = app_root / "tests"
    tests_root.mkdir(parents=True)
    (tests_root / "test_portable_import.py").write_text(
        "import os\n\n"
        "from factory.exact_v2_traceability import CANONICAL_APPLICATION_ID\n\n"
        "def test_portable_import() -> None:\n"
        "    assert os.environ['UPI_APP_FACTORY_ROOT_CONFTEST_ACTIVE'] == '1'\n"
        "    assert CANONICAL_APPLICATION_ID == 'upi_failed_debit_no_credit'\n",
        encoding="utf-8",
    )

    report = adapter._execute_generated_tests(
        app_root=app_root,
        app_id="upi_dispute_resolution",
        version_id="v_test",
        run_id="portable_import_test",
        requirements_sha256="0" * 64,
    )

    assert report["exit_code"] == 0
    assert report["go_gate"] == "GO"
    assert report["counts"]["passed"] == 1
    assert report["tests_executed"]["all"] == ["tests/test_portable_import.py"]
