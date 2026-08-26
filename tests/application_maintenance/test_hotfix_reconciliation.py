from factory.application_maintenance import ChangeKind, ChangeRecord, ChangeType, MaintenanceLedger, RepairLocus


def _hotfix(reconciliation: tuple[str, ...] = ()) -> ChangeRecord:
    return ChangeRecord("HOT-1", "app_one", ChangeType.EMERGENCY_HOTFIX, ChangeKind.DEFECT,
                        RepairLocus.TEMPORARY_HOTFIX, ("INC-1",), ("CAP-1",), ("SRC-1",),
                        ("TEST-1",), None, True, reconciliation)


def test_direct_hotfix_cannot_pass_reconciliation_or_drift_gate_unreconciled() -> None:
    ledger = MaintenanceLedger("app_one", [_hotfix()])
    assert ledger.gates()["HOTFIX_RECONCILIATION_GATE"]["status"] == "FAIL"
    assert ledger.gates()["GENERATED_SOURCE_DRIFT_GATE"]["change_ids"] == ["HOT-1"]
    assert _hotfix().to_dict()["reconciliation_status"] == "PENDING_EXTERNAL_AUTHORITY"


def test_canonicalization_fact_closes_hotfix_obligation_but_not_release_lineage() -> None:
    ledger = MaintenanceLedger("app_one", [_hotfix(("EVOLUTION-1", "REGEN-PROOF-1"))])
    assert ledger.gates()["HOTFIX_RECONCILIATION_GATE"]["status"] == "PROVEN"
    assert ledger.gates()["RELEASE_LINEAGE_GATE"]["status"] == "FAIL"
