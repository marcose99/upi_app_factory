from factory.validators.validate_phase1_foundation import validate


def test_phase1_foundation_contract_passes() -> None:
    result = validate()
    assert result.passed, result.errors
