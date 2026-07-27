from __future__ import annotations

from factory.operator_portal.runtime_scenarios import scenario_catalog


def test_scenario_catalog_has_required_categories_and_exact_expectations() -> None:
    catalog = scenario_catalog()
    categories = set(catalog["categories"])
    assert {"positive", "negative", "boundary", "idempotency", "resilience", "timeout", "security"}.issubset(categories)
    for scenario in catalog["scenarios"]:
        assert isinstance(scenario["expected"]["status"], int)
        assert scenario["expected"]["json"]


def test_scenario_catalog_uses_current_strict_generated_api_contract() -> None:
    catalog = scenario_catalog()
    post_scenarios = [
        scenario
        for scenario in catalog["scenarios"]
        if scenario["method"] == "POST" and scenario["endpoint"] == "/disputes"
    ]

    assert post_scenarios
    for scenario in post_scenarios:
        payload = scenario["payload"]
        if scenario["expected"]["status"] == 201:
            assert {"transaction_ref", "customer_upi", "reason"}.issubset(payload)
        assert "client_request_id" not in payload
        assert "amount_paise" not in payload
    replay = next(scenario for scenario in post_scenarios if scenario["id"] == "idempotency_replay")
    assert replay["expected"]["json"]["replay_status"] == 201
