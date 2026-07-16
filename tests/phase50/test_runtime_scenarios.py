from __future__ import annotations

from factory.operator_portal.runtime_scenarios import scenario_catalog


def test_scenario_catalog_has_required_categories_and_exact_expectations() -> None:
    catalog = scenario_catalog()
    categories = set(catalog["categories"])
    assert {"positive", "negative", "boundary", "idempotency", "resilience", "timeout", "security"}.issubset(categories)
    for scenario in catalog["scenarios"]:
        assert isinstance(scenario["expected"]["status"], int)
        assert scenario["expected"]["json"]
