from __future__ import annotations

from pathlib import Path

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioComparator,
    VersionState,
    approve_action,
)
from tests.phase51.conftest import PortfolioFixture, mock_app, registration


def test_version_comparison_recommends_local_promotion_and_never_production(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    left = catalogue.register(
        registration(
            app_id="compare_app",
            version_id="v1",
            app_root=mock_app(tmp_path, "compare_v1", "v1"),
            manifest={"openapi": {"paths": {"/health": {}}}},
        )
    )
    right = catalogue.register(
        registration(
            app_id="compare_app",
            version_id="v2",
            app_root=mock_app(tmp_path, "compare_v2", "v2"),
            manifest={"openapi": {"paths": {"/health": {}, "/scenario/echo": {}}}},
        )
    )

    comparison = PortfolioComparator().compare(
        left,
        right,
        right_scenarios={"decision": "GO", "passed": True},
    )

    assert comparison["openapi_changes"]["added_paths"] == ["/scenario/echo"]
    assert comparison["promotion_recommendation"]["decision"] == "promote_locally"
    assert comparison["promotion_recommendation"]["production_deployment"] == "not_allowed"
    assert comparison["rollback_plan"]["type"] == "non_destructive"


def test_quarantine_and_retire_follow_approved_lifecycle(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, _, _ = portfolio
    catalogue.register(
        registration(
            app_id="lifecycle_app",
            app_root=mock_app(tmp_path, "lifecycle_app", "lifecycle"),
        )
    )
    approval = approve_action(
        store=store,
        action="quarantine",
        scope="lifecycle_app:v1",
        actor="tester",
        token=LOCAL_APPROVAL_TOKEN,
        nonce="nonce_lifecycle_quarantine",
    )
    store.consume_approval(action="quarantine", scope="lifecycle_app:v1", nonce=approval["nonce"])
    quarantined = catalogue.transition_version(
        app_id="lifecycle_app",
        version_id="v1",
        target=VersionState.QUARANTINED,
    )
    retired = catalogue.transition_version(
        app_id="lifecycle_app",
        version_id="v1",
        target=VersionState.RETIRED,
    )

    assert quarantined.state == VersionState.QUARANTINED
    assert retired.state == VersionState.RETIRED
