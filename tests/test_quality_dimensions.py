from scripts.validate_quality_dimensions import validate


def test_quality_dimensions_are_complete() -> None:
    assert validate() == []
