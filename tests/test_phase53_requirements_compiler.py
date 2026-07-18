from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from factory.application_engineering.requirements_compiler import (
    compile_requirements,
    has_blocking_diagnostics,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/phase53/failed_debit_requirements.md"


def test_failed_debit_fixture_compiles_to_canonical_ir() -> None:
    ir = compile_requirements([FIXTURE], ROOT)

    assert ir["ir_version"] == "requirements-ir/v1"
    assert ir["application"]["app_id"] == "upi_app_factory"
    assert ir["application"]["product_name"] == "UPI App Factory"
    assert ir["application"]["real_payment_calls"] == "disabled"
    assert len(ir["requirements"]["commands"]) >= 4
    assert len(ir["requirements"]["apis"]) >= 5
    assert len(ir["traceability"]) >= 35
    assert not has_blocking_diagnostics(ir), ir["diagnostics"]
    assert len(ir["canonical_hash"]) == 64


def test_compiler_reports_duplicates_and_unsupported_dependencies(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        """---
app_id: wrong_app
product_name: UPI App Factory
repository_id: upi_app_factory
real_payment_calls: disabled
---

## Actors
- id: ACT-001; name: One; description: ok
- id: ACT-001; name: Duplicate; description: ok

## Dependencies
- id: DEP-001; name: PostgreSQL; description: unsupported
""",
        encoding="utf-8",
    )

    ir = compile_requirements([bad], ROOT)
    codes = {item["code"] for item in ir["diagnostics"]}

    assert has_blocking_diagnostics(ir)
    assert "REQ_DUPLICATE_ID" in codes
    assert "REQ_UNSUPPORTED_DEPENDENCY" in codes
    assert "REQ_INVALID_APP_ID" in codes


def test_legacy_simple_requirements_import_has_traceability(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.md"
    legacy.write_text("REQ-001: Keep fictional data only.\n", encoding="utf-8")

    ir = compile_requirements([legacy], ROOT)

    imported = [item for item in ir["requirements"]["evidence"] if item["id"] == "REQ-001"]
    assert imported
    assert imported[0]["compatibility_import"] is True
    assert imported[0]["source"]["line"] == 1


def test_phase53_cli_compile_validate_and_explain(tmp_path: Path) -> None:
    output = tmp_path / "requirements_ir.json"
    module = "factory.application_engineering.requirements_compiler"

    compile_result = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
            "compile",
            "--input",
            str(FIXTURE),
            "--project-root",
            str(ROOT),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    assert output.is_file()

    validate_result = subprocess.run(
        [sys.executable, "-m", module, "validate", "--input", str(FIXTURE), "--project-root", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr
    assert "Requirements compiler validation passed" in validate_result.stdout

    explain_result = subprocess.run(
        [sys.executable, "-m", module, "explain", "--input", str(FIXTURE), "--project-root", str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert explain_result.returncode == 0, explain_result.stdout + explain_result.stderr
    assert "Traceability rows" in explain_result.stdout
