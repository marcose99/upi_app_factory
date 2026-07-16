from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.portfolio import (
    PortfolioError,
    PortfolioScenarioRunner,
    Scenario,
)
from tests.phase51.conftest import (
    PortfolioFixture,
    free_port,
    mock_app,
    port_open,
    registration,
    wait_for_ports_closed,
)


def test_crash_storm_readiness_timeout_stops_runtime_and_leaves_no_open_port(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="crash_app",
            app_root=mock_app(tmp_path, "crash_app", "crash", crash_health=True),
        )
    )
    port = free_port()
    ports.append(port)

    with pytest.raises(PortfolioError, match="readiness timed out"):
        supervisor.start(
            app_id=version.app_id,
            version_id=version.version_id,
            run_id="crash_runtime_001",
            port=port,
            readiness_timeout=0.5,
        )

    wait_for_ports_closed([port])
    assert not port_open(port)


def test_scenario_budget_release_prevents_starvation_after_rejected_payload(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="starvation_app",
            app_root=mock_app(tmp_path, "starvation_app", "starvation"),
        )
    )
    port = free_port()
    ports.append(port)
    status = supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="starvation_runtime_001",
        port=port,
    )
    runner = PortfolioScenarioRunner(store=store)
    huge = Scenario(
        "too_large",
        "negative",
        "POST",
        "/scenario/echo",
        {"blob": "x" * (70 * 1024)},
        200,
        {},
    )

    with pytest.raises(PortfolioError, match="payload exceeded"):
        runner.run_one(status=status, scenario=huge)

    healthy = Scenario(
        "health_after_error",
        "positive",
        "GET",
        "/health",
        None,
        200,
        {"status": "ok"},
    )
    assert runner.run_one(status=status, scenario=healthy)["passed"] is True


def test_stop_all_ignores_absent_runtime_directory_and_preserves_no_orphan_guarantee(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="cleanup_app",
            app_root=mock_app(tmp_path, "cleanup_app", "cleanup"),
        )
    )
    port = free_port()
    ports.append(port)
    supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="cleanup_runtime_001",
        port=port,
    )

    stopped = supervisor.stop_all()

    assert stopped["status"] == "stopped"
    assert all(
        item.get("health", {}).get("orphan_detected") is False
        for item in stopped["runtimes"]
        if item.get("state") == "STOPPED"
    )
    wait_for_ports_closed([port])
    assert not port_open(port)
