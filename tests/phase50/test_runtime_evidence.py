from __future__ import annotations

from pathlib import Path

from factory.operator_portal.runtime_evidence import RuntimeEvidenceService
from factory.operator_portal.runtime_store import RuntimeStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_evidence_manifest_derives_no_go_when_gates_missing(tmp_path: Path) -> None:
    store = RuntimeStore(project_root=PROJECT_ROOT, state_root=tmp_path / "runtime")
    store.append_event("phase50_evidence", "test_event", {"message": "safe"})
    manifest = RuntimeEvidenceService(project_root=PROJECT_ROOT, store=store).build_manifest(
        run_id="phase50_evidence"
    )
    assert manifest["decision"] == "NO_GO"
    assert manifest["validation_gates"]["approval_plaintext_absent"] is True
