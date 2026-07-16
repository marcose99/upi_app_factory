from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioError,
    normalize_runtime_url,
    approve_action,
)
from tests.phase51.conftest import PortfolioFixture, free_port, mock_app, registration


def test_ssrf_and_redirect_targets_are_rejected() -> None:
    with pytest.raises(PortfolioError, match="loopback"):
        normalize_runtime_url(
            base_url="http://169.254.169.254:80",
            method="GET",
            endpoint="/health",
            owned_port=80,
        )
    with pytest.raises(PortfolioError, match="allow-listed"):
        normalize_runtime_url(
            base_url="http://127.0.0.1:18051",
            method="DELETE",
            endpoint="/health",
            owned_port=18051,
        )
    with pytest.raises(PortfolioError, match="escaped"):
        normalize_runtime_url(
            base_url="http://127.0.0.1:18051",
            method="GET",
            endpoint="//evil.test/health",
            owned_port=18051,
        )


def test_approval_replay_and_wrong_scope_are_fail_closed(portfolio: PortfolioFixture) -> None:
    store, _, _, _ = portfolio
    approval = approve_action(
        store=store,
        action="start",
        scope="secure_runtime_001",
        actor="tester",
        token=LOCAL_APPROVAL_TOKEN,
        nonce="nonce_secure_start",
    )
    store.consume_approval(action="start", scope="secure_runtime_001", nonce=approval["nonce"])

    with pytest.raises(PortfolioError, match="replay"):
        store.consume_approval(action="start", scope="secure_runtime_001", nonce=approval["nonce"])
    with pytest.raises(PortfolioError, match="scope"):
        store.consume_approval(action="start", scope="other_runtime_001", nonce=approval["nonce"])
    assert LOCAL_APPROVAL_TOKEN not in store.approvals_path.read_text(encoding="utf-8")


def test_stale_ownership_binding_blocks_confused_deputy_status(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, supervisor, ports = portfolio
    version = catalogue.register(
        registration(
            app_id="ownership_app",
            app_root=mock_app(tmp_path, "ownership_app", "ownership"),
        )
    )
    port = free_port()
    ports.append(port)
    supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="ownership_runtime_001",
        port=port,
    )

    status_path = store.status_path("ownership_runtime_001")
    original = status_path.read_text(encoding="utf-8")
    status_path.write_text(original.replace(version.identity_sha256, "f" * 64), encoding="utf-8")
    try:
        with pytest.raises(PortfolioError, match="stale ownership"):
            supervisor.status(
                app_id=version.app_id,
                version_id=version.version_id,
                run_id="ownership_runtime_001",
                port=port,
            )
    finally:
        status_path.write_text(original, encoding="utf-8")


def test_application_registration_rejects_arbitrary_filesystem_roots(
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    with pytest.raises(PortfolioError, match="arbitrary filesystem"):
        catalogue.register(registration(app_id="root_escape", app_root=Path("/")))
