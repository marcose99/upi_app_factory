from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def test_phase22_runner_generates_local_only_observability_evidence(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    taxonomy = tmp_path / "taxonomy.json"
    lake = tmp_path / "lake.json"
    retention = tmp_path / "retention.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_phase22_enterprise_observability_audit_lake_model.py",
            "--execute-readonly-gates",
            "--audit-out",
            str(audit),
            "--taxonomy-out",
            str(taxonomy),
            "--lake-out",
            str(lake),
            "--retention-out",
            str(retention),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit_data = load_json(audit)
    taxonomy_data = load_json(taxonomy)
    lake_data = load_json(lake)
    assert audit_data["external_telemetry_published"] is False
    assert taxonomy_data["pii_allowed"] is False
    assert lake_data["external_audit_lake_mutation_performed"] is False


def test_phase22_validator_cli_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase22_enterprise_observability_audit_lake_model.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
