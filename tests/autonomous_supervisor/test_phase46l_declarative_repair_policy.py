from __future__ import annotations

import json
from pathlib import Path

from tools.autonomous_supervisor.catalog import RepairCatalog
from tools.autonomous_supervisor.policy import (
    RepairPolicyEngine,
    RepairRequest,
    decision_to_object,
)


def write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repairs": [
                    {
                        "repair_id": "RUFF_SAFE_FIX",
                        "automatic": True,
                        "eligible_gates": ["Ruff"],
                        "max_attempts": 2,
                        "candidate_scope_required": True,
                        "safe_fix_only": True,
                        "risk": "LOW",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_authorizes_safe_candidate_scoped_repair(
    tmp_path: Path,
) -> None:
    path = tmp_path / "catalog.json"
    write_catalog(path)
    engine = RepairPolicyEngine(RepairCatalog.load(path))
    decision = engine.evaluate(
        RepairRequest(
            gate="Ruff",
            attempt=1,
            candidate_scope_verified=True,
            safe_fix_available=True,
        )
    )
    assert decision.authorized is True
    assert decision.repair_id == "RUFF_SAFE_FIX"
    assert decision_to_object(decision)["risk"] == "LOW"


def test_rejects_unknown_gate(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    write_catalog(path)
    engine = RepairPolicyEngine(RepairCatalog.load(path))
    decision = engine.evaluate(
        RepairRequest(
            gate="MyPy",
            attempt=1,
            candidate_scope_verified=True,
            safe_fix_available=False,
        )
    )
    assert decision.authorized is False
    assert decision.reason == "NO_AUTOMATIC_RULE"


def test_rejects_unverified_scope(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    write_catalog(path)
    engine = RepairPolicyEngine(RepairCatalog.load(path))
    decision = engine.evaluate(
        RepairRequest(
            gate="Ruff",
            attempt=1,
            candidate_scope_verified=False,
            safe_fix_available=True,
        )
    )
    assert decision.authorized is False
    assert decision.reason == "CANDIDATE_SCOPE_NOT_VERIFIED"
