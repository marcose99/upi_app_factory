from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.portfolio import (
    PolicyContract,
    PortfolioError,
    QuotaContract,
    RuntimeState,
    VersionState,
)
from tests.phase51.conftest import PortfolioFixture, mock_app, registration


def test_contracts_accept_only_local_mock_loopback_portfolios(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    version = catalogue.register(
        registration(
            app_id="contract_app",
            app_root=mock_app(tmp_path, "contract_app", "contract"),
            quota=QuotaContract(cpu_units=2, memory_mb=512, max_processes=1, max_restarts=2),
        )
    )

    assert version.policy.local_only is True
    assert version.policy.loopback_only is True
    assert version.policy.mock_only is True
    assert version.policy.default_runtime_llm_calls == 0
    assert version.policy.real_payment_calls == "disabled"


def test_contracts_reject_live_payment_public_or_llm_policy(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    with pytest.raises(PortfolioError, match="live payments"):
        catalogue.register(
            registration(
                app_id="unsafe_policy",
                app_root=mock_app(tmp_path, "unsafe_policy", "unsafe"),
                policy=PolicyContract(real_payment_calls="enabled"),
            )
        )
    with pytest.raises(PortfolioError, match="certification"):
        catalogue.register(
            registration(
                app_id="public_policy",
                app_root=mock_app(tmp_path, "public_policy", "public"),
                policy=PolicyContract(public_targets_allowed=True),
            )
        )


def test_contracts_enforce_state_transition_tables(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, _ = portfolio
    version = catalogue.register(
        registration(
            app_id="state_app",
            app_root=mock_app(tmp_path, "state_app", "state"),
        )
    )
    binding = supervisor.binding(version=version, run_id="state_runtime_001", port=18051)
    status = supervisor.store.read_status("state_runtime_001", binding, version)

    starting = supervisor.store.transition_status(status, RuntimeState.STARTING)
    ready = supervisor.store.transition_status(starting, RuntimeState.READY)
    with pytest.raises(PortfolioError, match="invalid runtime transition"):
        supervisor.store.transition_status(ready, RuntimeState.STARTING)

    catalogue.transition_version(
        app_id="state_app",
        version_id="v1",
        target=VersionState.QUARANTINED,
    )
    with pytest.raises(PortfolioError, match="invalid version transition"):
        catalogue.transition_version(
            app_id="state_app",
            version_id="v1",
            target=VersionState.ACTIVE,
        )
