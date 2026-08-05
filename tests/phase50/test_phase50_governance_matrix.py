from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "operator_portal" / "phase50_governance_matrix.json"


def test_phase50_governance_matrix_covers_current_runtime_test_inventory() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    phase50_tests = sorted((ROOT / "tests" / "phase50").glob("test_*.py"))
    referenced_files = set()

    assert payload["schema_version"] == "phase50-governance-matrix.v1"
    assert len(payload["controls"]) >= 10
    for control in payload["controls"]:
        assert control["tests"]
        for test_ref in control["tests"]:
            relative = str(test_ref).split("::", 1)[0]
            referenced_files.add(relative)
            assert (ROOT / relative).is_file(), test_ref

    assert {
        path.relative_to(ROOT).as_posix()
        for path in phase50_tests
        if path.name != "test_phase50_governance_matrix.py"
    }.issubset(referenced_files)
