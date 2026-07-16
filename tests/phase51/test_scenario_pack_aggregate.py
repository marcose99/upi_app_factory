from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.portfolio import (
    PortfolioError,
    PortfolioScenarioRunner,
    Scenario,
    ScenarioPack,
)
from tests.phase51.conftest import PortfolioFixture, free_port, mock_app, registration


def test_scenario_pack_runs_required_categories_and_writes_results(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="scenario_app",
            app_root=mock_app(tmp_path, "scenario_app", "scenario"),
        )
    )
    port = free_port()
    ports.append(port)
    status = supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="scenario_runtime_001",
        port=port,
    )

    result = PortfolioScenarioRunner(store=store).run_for_status(status, parallel=True)

    assert result["decision"] == "GO"
    assert {item["category"] for item in result["results"]} >= {
        "positive",
        "negative",
        "boundary",
        "replay",
        "timeout",
        "security",
    }
    assert store.scenarios_path("scenario_runtime_001").is_file()


def test_scenario_pack_rejects_missing_capabilities_before_execution(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, supervisor, _ = portfolio
    version = catalogue.register(
        registration(
            app_id="capability_app",
            app_root=mock_app(tmp_path, "capability_app", "capability"),
            capabilities=(),
        )
    )
    binding = supervisor.binding(version=version, run_id="capability_runtime_001", port=18052)
    status = store.read_status("capability_runtime_001", binding, version)
    pack = ScenarioPack(
        pack_id="requires_echo",
        version="1.0.0",
        scenarios=(
            Scenario(
                "echo_required",
                "positive",
                "GET",
                "/health",
                None,
                200,
                {"status": "ok"},
                ("echo",),
            ),
        ),
    )

    with pytest.raises(PortfolioError, match="capabilities missing: echo"):
        PortfolioScenarioRunner(store=store, pack=pack).run_for_status(status)


def test_aggregate_execution_reports_portfolio_decision(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, supervisor, ports = portfolio
    statuses = []
    for app_id, label in (("aggregate_alpha", "alpha"), ("aggregate_beta", "beta")):
        version = catalogue.register(
            registration(
                app_id=app_id,
                app_root=mock_app(tmp_path, app_id, label),
            )
        )
        port = free_port()
        ports.append(port)
        statuses.append(
            supervisor.start(
                app_id=version.app_id,
                version_id=version.version_id,
                run_id=f"{app_id}_rt01",
                port=port,
            )
        )

    aggregate = PortfolioScenarioRunner(store=store).run_portfolio(statuses, parallel=True)

    assert aggregate["execution_mode"] == "parallel"
    assert aggregate["decision"] == "GO"
    assert [item["app_id"] for item in aggregate["applications"]] == [
        "aggregate_alpha",
        "aggregate_beta",
    ]
