from typing import Any

from factory.quality_assurance.kernel import DIMENSION_WEIGHTS, HARD_GATES, evaluate_acceptance


def measures(met: int = 990, total: int = 1000) -> dict[str, Any]:
    return {
        "dimensions": {name: {"met": met, "total": total} for name in DIMENSION_WEIGHTS},
        "hard_gates": {
            name: {"met": 1, "total": 1, "evidence_ids": [f"EV-{name}"]} for name in HARD_GATES
        },
    }


def test_threshold_is_non_compensable_and_not_rounded_up() -> None:
    accepted = evaluate_acceptance(measures())
    assert accepted["near_production_candidate"] is True
    assert accepted["production_ready"] is False
    low = measures()
    low["dimensions"]["architecture_and_engineering"] = {"met": 989999, "total": 1000000}
    rejected = evaluate_acceptance(low)
    assert rejected["dimension_scores"]["architecture_and_engineering"] == 98.9999
    assert rejected["near_production_candidate"] is False
