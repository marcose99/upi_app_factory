from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.build_portal_control_coverage_manifest import build_manifest, main


ROOT = Path(__file__).resolve().parents[1]


def test_portal_control_coverage_manifest_is_source_complete(tmp_path: Path) -> None:
    output = tmp_path / "portal_control_coverage.json"

    assert main(["--repo-root", str(ROOT), "--output", str(output)]) == 0
    payload = cast(dict[str, Any], json.loads(output.read_text(encoding="utf-8")))
    direct = build_manifest(ROOT)

    assert payload == direct
    assert payload["schema_version"] == "1.0"
    assert payload["status"] == "PASSED"
    assert payload["coverage_basis"] == "behavioral-interaction"
    assert payload["visible_controls_discovered"] >= 33
    assert payload["interaction_covered"] == len(payload["control_entries"])
    assert payload["uncovered_controls"] == []
    assert payload["unbound_controls"] == []
    assert payload["duplicate_control_ids"] == []
    assert len({entry["control_id"] for entry in payload["control_entries"]}) == len(
        payload["control_entries"]
    )
    assert payload["test_files"] == ["tests/test_portal_control_coverage.py"]
    assert all(entry["coverage_status"] == "COVERED" for entry in payload["control_entries"])
