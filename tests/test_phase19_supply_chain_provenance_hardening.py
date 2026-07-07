from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_phase19_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase19_supply_chain_provenance_hardening.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase19_tmp_provenance_is_readiness_only(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    inventory = tmp_path / "inventory.json"
    provenance = tmp_path / "provenance.json"
    gates = tmp_path / "gates.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase19_supply_chain_provenance_hardening.py",
            "--audit-out",
            str(audit),
            "--inventory-out",
            str(inventory),
            "--provenance-out",
            str(provenance),
            "--gate-out",
            str(gates),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit_data = json.loads(audit.read_text(encoding="utf-8"))
    provenance_data = json.loads(provenance.read_text(encoding="utf-8"))
    assert audit_data["formal_supply_chain_certification_claimed"] is False
    assert audit_data["registry_push_performed"] is False
    assert provenance_data["attestation_status"] == "readiness_only_not_formal_attestation"
