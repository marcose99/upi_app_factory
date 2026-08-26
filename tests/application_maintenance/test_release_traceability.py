from factory.application_maintenance import ChangeKind, ChangeRecord, ChangeType, MaintenanceLedger, RepairLocus


def test_release_lineage_never_conflates_unreleased_with_released() -> None:
    record = ChangeRecord("CHG-1", "app_one", ChangeType.DATA_CORRECTION, ChangeKind.DEFECT,
                          RepairLocus.DATA_OPERATION, ("REQ-1",), ("DATA-1",), ("OP-1",), ("TEST-1",))
    docs = MaintenanceLedger("app_one", [record]).documents()
    assert docs["release_lineage"]["entries"] == [
        {"change_id": "CHG-1", "release_id": None, "release_status": "NOT_RELEASED"}
    ]
    assert docs["requirements_to_release_maintenance"]["document_digest"] != docs["release_lineage"]["document_digest"]


def test_systemic_repairs_project_factory_learning_entry() -> None:
    record = ChangeRecord("DEF-1", "app_one", ChangeType.BUG_FIX, ChangeKind.DEFECT,
                          RepairLocus.FACTORY_SYSTEMIC_CAPABILITY, ("REQ-1",), ("CAP-1",),
                          ("SRC-1",), ("TEST-1",), "REL-1", False, (), "FACTORY-CAP-7")
    entry = MaintenanceLedger("app_one", [record]).documents()["factory_learning_ledger"]["entries"][0]
    assert entry["factory_capability_id"] == "FACTORY-CAP-7"
    assert entry["requalification_status"] == "NOT_YET_MEASURED"
