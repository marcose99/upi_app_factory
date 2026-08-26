from factory.application_maintenance import ChangeKind, ChangeRecord, ChangeType, MaintenanceLedger, RepairLocus


def test_change_lifecycle_is_fact_bound_and_distinguishes_defect_from_requirement() -> None:
    ledger = MaintenanceLedger("app_one")
    ledger.add(ChangeRecord("CHG-1", "app_one", ChangeType.BUG_FIX, ChangeKind.DEFECT,
                            RepairLocus.APPLICATION_EVOLUTION_SPEC, ("REQ-1",), ("CAP-1",),
                            ("SRC-1",), ("TEST-1",), "REL-1"))
    ledger.add(ChangeRecord("CHG-2", "app_one", ChangeType.ENHANCEMENT, ChangeKind.NEW_REQUIREMENT,
                            RepairLocus.REQUIREMENT_BASELINE, ("REQ-2",), ("CAP-2",),
                            ("SRC-2",), ("TEST-2",), "REL-1"))
    rows = ledger.documents()["change_ledger"]["changes"]
    assert [row["change_kind"] for row in rows] == ["DEFECT", "NEW_REQUIREMENT"]
    assert all(value["status"] == "PROVEN" for value in ledger.gates().values())


def test_all_governed_change_categories_are_available() -> None:
    assert len(ChangeType) == 11
    assert {item.value for item in RepairLocus} == {
        "REQUIREMENT_BASELINE", "FACTORY_SYSTEMIC_CAPABILITY", "APPLICATION_EVOLUTION_SPEC",
        "CONFIGURATION_CONTRACT", "DEPENDENCY_CONTRACT", "DATA_OPERATION", "TEMPORARY_HOTFIX",
    }
