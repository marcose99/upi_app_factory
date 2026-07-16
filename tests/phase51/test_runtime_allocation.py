from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.portfolio import PortfolioError, QuotaContract, RuntimeState
from tests.phase51.conftest import PortfolioFixture, free_port, mock_app, port_open, registration


def test_runtime_allocation_detects_port_collision_and_stop_all_cleans_ports(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, ports = portfolio
    alpha = catalogue.register(
        registration(
            app_id="runtime_alpha",
            app_root=mock_app(tmp_path, "runtime_alpha", "alpha"),
            quota=QuotaContract(max_concurrent_runtimes=2),
        )
    )
    beta = catalogue.register(
        registration(
            app_id="runtime_beta",
            app_root=mock_app(tmp_path, "runtime_beta", "beta"),
            quota=QuotaContract(max_concurrent_runtimes=2),
        )
    )
    alpha_port = free_port()
    beta_port = free_port()
    ports.extend([alpha_port, beta_port])

    first = supervisor.start(
        app_id=alpha.app_id,
        version_id=alpha.version_id,
        run_id="runtime_alpha_001",
        port=alpha_port,
    )
    second = supervisor.start(
        app_id=beta.app_id,
        version_id=beta.version_id,
        run_id="runtime_beta_001",
        port=beta_port,
    )
    assert first.state == RuntimeState.READY
    assert second.binding.host == "127.0.0.1"

    with pytest.raises(PortfolioError, match="port"):
        supervisor.start(
            app_id=alpha.app_id,
            version_id=alpha.version_id,
            run_id="runtime_alpha_002",
            port=beta_port,
        )

    stopped = supervisor.stop_all()
    assert stopped["count"] >= 2
    assert not port_open(alpha_port)
    assert not port_open(beta_port)


def test_runtime_allocation_enforces_concurrency_and_restart_quotas(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="quota_app",
            app_root=mock_app(tmp_path, "quota_app", "quota"),
            quota=QuotaContract(max_concurrent_runtimes=1, max_restarts=0),
        )
    )
    port = free_port()
    ports.append(port)
    supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="quota_runtime_001",
        port=port,
    )

    with pytest.raises(PortfolioError, match="concurrency"):
        supervisor.start(
            app_id=version.app_id,
            version_id=version.version_id,
            run_id="quota_runtime_002",
            port=free_port(),
        )
    with pytest.raises(PortfolioError, match="restart quota"):
        supervisor.restart(
            app_id=version.app_id,
            version_id=version.version_id,
            run_id="quota_runtime_001",
            port=port,
        )
