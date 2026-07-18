from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from factory.application_engineering.multi_domain_profiles import (
    OBLIGATION_CATEGORIES,
    Phase70Error,
    build_phase70_profiles,
    compose_reference_application,
    validate_phase70_portfolio,
)
from upi_factory.capstone.phase70 import run_phase70_validation


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_ROOT = ROOT / "tests" / "fixtures" / "phase68_70"
GOVERNANCE_PATH = ROOT / "factory_governance" / "phase68_70" / "phase70_profile_governance.json"


def test_phase70_profiles_cover_required_portfolio_contract() -> None:
    profiles = build_phase70_profiles()

    assert [profile.profile_id for profile in profiles] == [
        "upi_failed_debit_no_credit",
        "upi_reversal_refund_tracking",
        "upi_duplicate_debit",
        "merchant_qr_acquirer_dispute",
        "fraud_mule_account_triage",
        "card_authorization_chargeback",
    ]
    for profile in profiles:
        profile.validate()
        payload = profile.as_dict()
        assert payload["certification_posture"] == "certification-ready-not-certified"
        assert payload["real_payment_calls"] == "disabled"
        assert payload["runtime_llm_calls_default"] == 0
        assert len(payload["stable_profile_sha256"]) == 64
        assert {item["category"] for item in payload["test_obligations"]} == set(OBLIGATION_CATEGORIES)
        assert all(port["live_calls"] == "disabled" for port in payload["ports"])


def test_reference_app_composition_writes_only_to_runtime_root(tmp_path: Path) -> None:
    profile = build_phase70_profiles()[0]
    manifest = compose_reference_application(profile, tmp_path, ROOT)

    app_root = tmp_path / profile.profile_id
    assert manifest["tracked_output"] is False
    assert (app_root / "evidence" / "profile_contract.json").is_file()
    assert (app_root / "tests" / "test_contract.py").is_file()
    assert all(not Path(item["path"]).is_absolute() for item in manifest["file_manifest"])


def test_phase70_validator_builds_temporary_reference_portfolio(tmp_path: Path) -> None:
    result = validate_phase70_portfolio(
        project_root=ROOT,
        requirements_root=REQUIREMENTS_ROOT,
        governance_path=GOVERNANCE_PATH,
        runtime_root=tmp_path / "runtime",
    )

    assert result["status"] == "PASS"
    assert result["profile_count"] == 6
    assert result["fictional_data_only"] is True
    assert result["official_certification_claimed"] is False
    assert result["phase56_reuse_manifest"]["composer_profile"] == "local-deep-v1"
    assert result["obligation_counts"] == {category: 6 for category in OBLIGATION_CATEGORIES}
    assert len(result["reference_app_manifests"]) == 6


def test_phase70_governance_hash_tamper_is_rejected(tmp_path: Path) -> None:
    governance = json.loads(GOVERNANCE_PATH.read_text(encoding="utf-8"))
    governance["profiles"][0]["stable_profile_sha256"] = "0" * 64
    tampered = tmp_path / "governance.json"
    tampered.write_text(json.dumps(governance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(Phase70Error, match="governance profile hashes"):
        validate_phase70_portfolio(
            project_root=ROOT,
            requirements_root=REQUIREMENTS_ROOT,
            governance_path=tampered,
            runtime_root=tmp_path / "runtime",
        )


def test_phase70_capstone_entrypoint_uses_ephemeral_runtime() -> None:
    result = run_phase70_validation(project_root=ROOT)

    assert result["status"] == "PASS"
    assert result["profile_count"] == 6
    assert result["production_readiness_claimed"] is False


def test_phase70_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase70_multi_domain_application_engineering.py"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["profile_count"] == 6
