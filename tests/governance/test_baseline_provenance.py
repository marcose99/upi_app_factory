from factory.validators.validate_baseline_provenance import validate


def test_baseline_provenance_is_proven_and_preserved() -> None:
    result = validate()
    assert result.passed, result.errors
