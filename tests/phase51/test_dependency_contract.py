from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from factory.validators.dependency_contract import parse_exact_lock, validate_dependency_contract


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATHS = (
    Path("requirements/ci-lock.txt"),
    Path("requirements/bootstrap-lock.txt"),
    Path("requirements/recipient-lock.txt"),
    Path("requirements-recipient.txt"),
    Path("pyproject.toml"),
    Path("run_factory.sh"),
    Path("Dockerfile"),
)


def _copy_contract_files(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in CONTRACT_PATHS:
        source = PROJECT_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def test_repository_dependency_contract_passes() -> None:
    payload = validate_dependency_contract(PROJECT_ROOT)
    assert payload["passed"] is True, payload["errors"]
    assert payload["errors"] == []
    assert payload["setuptools_version"] == "83.0.0"


def test_dependency_contract_cli_passes_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_dependency_contract.py"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert '"passed": true' in result.stdout


def test_exact_lock_parser_rejects_ranges_and_duplicates(tmp_path: Path) -> None:
    lock = tmp_path / "bad-lock.txt"
    lock.write_text(
        "fastapi>=0.110\n"
        "httpx==0.28.1\n"
        "HTTPX==0.28.1\n",
        encoding="utf-8",
    )
    errors: list[str] = []
    parse_exact_lock(lock, errors)
    assert any("exact pin" in error for error in errors)
    assert any("duplicate dependency name: httpx" in error for error in errors)


def test_dependency_contract_rejects_recipient_wrapper_drift(tmp_path: Path) -> None:
    root = _copy_contract_files(tmp_path)
    recipient_entry = root / "requirements-recipient.txt"
    recipient_entry.write_text(
        recipient_entry.read_text(encoding="utf-8") + "fastapi>=0.110\n",
        encoding="utf-8",
    )
    payload = validate_dependency_contract(root)
    assert payload["passed"] is False
    assert any("must contain only" in error for error in payload["errors"])


def test_dependency_contract_rejects_ci_recipient_version_drift(tmp_path: Path) -> None:
    root = _copy_contract_files(tmp_path)
    recipient_lock = root / "requirements" / "recipient-lock.txt"
    recipient_lock.write_text(
        recipient_lock.read_text(encoding="utf-8").replace(
            "fastapi==0.139.0",
            "fastapi==0.138.0",
        ),
        encoding="utf-8",
    )
    payload = validate_dependency_contract(root)
    assert payload["passed"] is False
    assert any("CI/recipient lock version mismatch for fastapi" in error for error in payload["errors"])
