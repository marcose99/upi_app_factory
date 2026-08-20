from pathlib import Path

from factory.generators.mock_dispute_app_generator import generate
from factory.validators.validate_regeneration_readiness import validate


def test_regeneration_readiness_contract_passes() -> None:
    result = validate()
    assert result.passed, result.errors


def test_mock_dispute_app_generator_writes_manifest(tmp_path: Path) -> None:
    result = generate(
        run_id="pytest_regeneration",
        workspace_root=tmp_path,
        clean=True,
    )

    assert result.manifest_path.is_file()
    assert len(result.generated_files) >= 8
    assert (result.output_dir / "generated/app/disputes/models.py").is_file()
    assert (result.output_dir / "generated/adapters/mock_upi_switch.py").is_file()
    assert (
        result.output_dir
        / "generated/generated_application/app/application/reconciliation_resolution.py"
    ).is_file()
    assert (
        result.output_dir
        / "generated/generated_application/app/tests/integration/test_reconciliation_reviewed_resolution.py"
    ).is_file()
