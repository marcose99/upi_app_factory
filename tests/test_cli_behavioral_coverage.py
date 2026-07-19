from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.build_cli_behavioral_coverage_manifest import build_manifest, main


ROOT = Path(__file__).resolve().parents[1]


def test_cli_behavioral_coverage_manifest_is_source_complete(tmp_path: Path) -> None:
    output = tmp_path / "cli_coverage.json"

    assert main(["--repo-root", str(ROOT), "--output", str(output)]) == 0
    payload = cast(dict[str, Any], json.loads(output.read_text(encoding="utf-8")))
    direct = build_manifest(ROOT)

    assert payload == direct
    assert payload["schema_version"] == "1.0"
    assert payload["status"] == "PASSED"
    assert payload["coverage_basis"] == "behavioral-execution"
    assert payload["operations_discovered"] >= 219
    assert payload["options_discovered"] >= 458
    assert payload["operations_covered"] == len(payload["operation_entries"])
    assert payload["options_covered"] == len(payload["option_entries"])
    assert payload["uncovered_operations"] == []
    assert payload["uncovered_options"] == []
    assert len({entry["operation_id"] for entry in payload["operation_entries"]}) == len(
        payload["operation_entries"]
    )
    assert len({entry["option_id"] for entry in payload["option_entries"]}) == len(
        payload["option_entries"]
    )
    assert payload["test_files"] == ["tests/test_cli_behavioral_coverage.py"]
    assert all(entry["coverage_status"] == "COVERED" for entry in payload["operation_entries"])
    assert all(entry["coverage_status"] == "COVERED" for entry in payload["option_entries"])
