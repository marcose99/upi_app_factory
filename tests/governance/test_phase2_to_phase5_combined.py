from factory.validators.validate_phase2_to_phase5_combined import validate


def test_phase2_to_phase5_combined_validator_passes() -> None:
    result = validate()
    assert result.passed, result.errors
