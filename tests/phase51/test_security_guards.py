from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PortfolioError,
    RuntimeState,
    build_runtime_process_environment,
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


def test_runtime_process_environment_removes_secret_like_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_keys = {
        "UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN",
        "UPI_APP_FACTORY_PORTAL_APPROVAL_TOKEN",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "DB_PASSWORD",
        "mixed_Private_Key",
    }
    for key in secret_keys:
        monkeypatch.setenv(key, f"secret-value-for-{key}")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    monkeypatch.setenv("UPI_DISPUTE_SQLITE_PATH", str(tmp_path / "disputes.sqlite3"))
    monkeypatch.setenv("PYTHONPATH", "/safe/prior")

    app_root = tmp_path / "app"
    env = build_runtime_process_environment(app_root=app_root)

    for key in secret_keys:
        assert key not in env
    assert env["TOKENIZERS_PARALLELISM"] == "false"
    assert env["UPI_DISPUTE_SQLITE_PATH"] == str(tmp_path / "disputes.sqlite3")
    assert env["PYTHONPATH"] == f"{app_root}{os.pathsep}/safe/prior"
    assert env["UPI_APP_FACTORY_PORTFOLIO_MODE"] == "local"
    assert env["UPI_APP_FACTORY_EXTERNAL_ECOSYSTEM_MODE"] == "mock"
    assert env["UPI_APP_FACTORY_ENABLE_LIVE_PROVIDER_CALLS"] == "false"
    assert env["UPI_APP_FACTORY_DEFAULT_RUNTIME_LLM_CALLS"] == "0"
    assert env["REAL_PAYMENT_CALLS"] == "disabled"
    assert env["FACTORY_LLM_ENABLED"] == "0"


def test_portfolio_start_launches_runtime_with_sanitized_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, supervisor, ports = portfolio
    secret_keys = {
        "UPI_APP_FACTORY_PORTFOLIO_APPROVAL_TOKEN",
        "UPI_APP_FACTORY_PORTAL_APPROVAL_TOKEN",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "DB_PASSWORD",
    }
    for key in secret_keys:
        monkeypatch.setenv(key, f"secret-value-for-{key}")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "true")
    monkeypatch.setenv("UPI_DISPUTE_SQLITE_PATH", str(tmp_path / "disputes.sqlite3"))

    version = catalogue.register(
        registration(
            app_id="env_guard_app",
            app_root=mock_app(tmp_path, "env_guard_app", "env-guard"),
        )
    )
    port = free_port()
    ports.append(port)
    captured: dict[str, Any] = {}

    class FakeProcess:
        pid = 424242
        returncode: int | None = None

        def __init__(self, *_args: object, **kwargs: object) -> None:
            captured["env"] = kwargs["env"]

        def poll(self) -> int | None:
            return None

    def ready_health(_binding: object) -> dict[str, Any]:
        return {"status": "ok"}

    def process_start_time(_pid: int) -> str:
        return "fake-start-time"

    def port_in_use(_port: int) -> bool:
        return False

    def sockets_are_available() -> bool:
        return True

    monkeypatch.setattr(
        "factory.application_engineering.portfolio.sockets_available",
        sockets_are_available,
    )
    monkeypatch.setattr("factory.application_engineering.portfolio.subprocess.Popen", FakeProcess)
    monkeypatch.setattr(supervisor, "_health", ready_health)
    monkeypatch.setattr(supervisor, "_process_start_time", process_start_time)
    monkeypatch.setattr(supervisor, "_port_in_use", port_in_use)

    status = supervisor.start(
        app_id=version.app_id,
        version_id=version.version_id,
        run_id="env_guard_runtime_001",
        port=port,
    )

    launched_env = cast(dict[str, str], captured["env"])
    assert status.state == RuntimeState.READY
    for key in secret_keys:
        assert key not in launched_env
    assert launched_env["TOKENIZERS_PARALLELISM"] == "true"
    assert launched_env["UPI_DISPUTE_SQLITE_PATH"] == str(tmp_path / "disputes.sqlite3")
    assert launched_env["UPI_APP_FACTORY_EXTERNAL_ECOSYSTEM_MODE"] == "mock"
    assert launched_env["REAL_PAYMENT_CALLS"] == "disabled"
    assert launched_env["FACTORY_LLM_ENABLED"] == "0"


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
