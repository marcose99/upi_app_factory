from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from factory.application_engineering.portfolio import (
    LOCAL_APPROVAL_TOKEN,
    PORTFOLIO_APPROVAL_TOKEN_ENV,
    PortfolioError,
    PortfolioStore,
    approval_secret,
    approve_action,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GENERATED_FILE_COUNT = 78


def test_portfolio_approval_scope_expiry_and_replay(tmp_path: Path) -> None:
    store = PortfolioStore(project_root=PROJECT_ROOT, state_root=tmp_path / "portfolio")
    approval = approve_action(
        store=store,
        action="start",
        scope="runtime_001",
        actor="operator",
        token=LOCAL_APPROVAL_TOKEN,
        nonce="nonce-001",
    )

    assert approval["expires_at_utc"]
    store.consume_approval(action="start", scope="runtime_001", nonce="nonce-001")
    with pytest.raises(PortfolioError, match="replay"):
        store.consume_approval(action="start", scope="runtime_001", nonce="nonce-001")
    with pytest.raises(PortfolioError, match="scope"):
        store.consume_approval(action="start", scope="runtime_002", nonce="nonce-001")

    data = json.loads(store.approvals_path.read_text(encoding="utf-8"))
    data["approvals"].append(
        {
            "action": "restart",
            "scope": "runtime_001",
            "nonce": "expired-001",
            "actor": "operator",
            "approved_at_utc": datetime(2026, 7, 26, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (datetime.now(timezone.utc) - timedelta(seconds=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "token_sha256": "expired",
            "consumed": False,
        }
    )
    store.atomic_write_json(store.approvals_path, data)
    with pytest.raises(PortfolioError, match="expired"):
        store.consume_approval(action="restart", scope="runtime_001", nonce="expired-001")

    data["approvals"].append(
        {
            "action": "stop",
            "scope": "runtime_001",
            "nonce": "tampered-001",
            "actor": "operator",
            "approved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (datetime.now(timezone.utc) + timedelta(minutes=5)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "token_sha256": "tampered",
            "consumed": False,
        }
    )
    store.atomic_write_json(store.approvals_path, data)
    with pytest.raises(PortfolioError, match="digest"):
        store.consume_approval(action="stop", scope="runtime_001", nonce="tampered-001")


def test_portfolio_approval_secret_fails_closed_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PORTFOLIO_APPROVAL_TOKEN_ENV, raising=False)
    with pytest.raises(PortfolioError, match=PORTFOLIO_APPROVAL_TOKEN_ENV):
        approval_secret()
    monkeypatch.setenv(PORTFOLIO_APPROVAL_TOKEN_ENV, LOCAL_APPROVAL_TOKEN)
    assert approval_secret() == LOCAL_APPROVAL_TOKEN


def test_wave_f_validation_proves_fresh_control_plane_generated_output() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase71_82_wave_f_control_plane.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["generated_file_count"] == EXPECTED_GENERATED_FILE_COUNT
    assert payload["two_build_comparison"]["status"] == "passed"
    assert payload["control_plane_policy"]["approval_expiry_required"] is True
    assert payload["control_plane_policy"]["portfolio_assessment_mode"] == "recommendation_only"
    assert payload["official_certification_claimed"] is False
